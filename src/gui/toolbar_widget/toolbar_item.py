# gui/toolbar_widget/toolbar_item.py

import os
import logging
from typing import Optional

from PySide6.QtWidgets import (
    QApplication, QWidget, QHBoxLayout,
    QSizePolicy, QStyle, QToolButton # QSpacerItem removed as not directly used here
)
from PySide6.QtGui import (
    QMouseEvent, QDrag, QPixmap, QPainter, QIcon, QColor, QPen
)
from PySide6.QtCore import (
    Qt, QMimeData, QPoint, Signal, Slot, QSize, QRect, QEvent, QObject
)

logger = logging.getLogger(__name__)

class ToolbarItem(QWidget):
    """
    Az eszköztár elemek alaposztálya, amely kezeli a drag-and-drop funkciót,
    az azonosítót és a slotfoglalást. Ez az osztály egy konténer a tényleges
    vizuális elemek (pl. QToolButton) számára.
    """
    itemClicked = Signal(str)
    itemDragStarted = Signal(str)

    @staticmethod
    def _get_icon_from_ref(widget: QWidget, icon_ref: str | None, icon_size: QSize) -> QIcon:
        """
        Visszaad egy QIcon-t egy fájlútvonal, beépített Qt ikon
        neve vagy egy speciális kulcsszó (pl. "minus", "plus") alapján.
        """
        if not icon_ref:
            return QIcon()

        if icon_ref == "minus":
            pixmap = QPixmap(icon_size)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(QPen(Qt.black, 3))
            y_center = icon_size.height() // 2
            margin = icon_size.width() // 4
            painter.drawLine(margin, y_center, icon_size.width() - margin, y_center)
            painter.end()
            return QIcon(pixmap)
        elif icon_ref == "plus":
            pixmap = QPixmap(icon_size)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(QPen(Qt.black, 3))
            x_center = icon_size.width() // 2
            y_center = icon_size.height() // 2
            margin = icon_size.width() // 4
            painter.drawLine(margin, y_center, icon_size.width() - margin, y_center)
            painter.drawLine(x_center, margin, x_center, icon_size.height() - margin)
            painter.end()
            return QIcon(pixmap)

        if os.path.exists(icon_ref):
            return QIcon(icon_ref)

        if icon_ref.startswith("SP_"):
            try:
                pixmap_enum = getattr(QStyle, icon_ref)
                return widget.style().standardIcon(pixmap_enum)
            except AttributeError:
                logger.warning(f"Ismeretlen Qt ikon név: {icon_ref}")
                return QIcon()

        return QIcon()

    def __init__(self, item_id: str, slot_occupancy: int = 1, tooltip: str = "", parent: Optional[QWidget] = None):
        super().__init__(parent)
        if slot_occupancy < 1:
            raise ValueError("A slot_occupancy-nak legalább 1-nek kell lennie.")

        self.item_id = item_id
        self.slot_occupancy = slot_occupancy
        self.setToolTip(tooltip)

        self._start_pos = QPoint()
        self._dragging = False
        self._item_size = QSize(0, 0) 

        self.setAcceptDrops(False) 

        self._internal_button = QToolButton(self)
        self._internal_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._internal_button.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self._internal_button.setFocusPolicy(Qt.NoFocus)
        self._internal_button.installEventFilter(self)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._internal_button)

    @Slot()
    def _handle_internal_button_clicked(self):
        """
        Ha a ToolbarItem (az eventFilteren keresztül) explicit módon úgy dönt, hogy kattintási esemény történt,
        akkor meghívódik. 
        """
        self.itemClicked.emit(self.item_id)

    def set_item_size(self, size: QSize):
        """Beállítja az elem fix méretét és a belső gomb ikonjának méretét."""
        self._item_size = size
        self.setFixedSize(size)
        self._internal_button.setIconSize(size * 0.8)

    def setEnabled(self, enabled: bool):
        """Beállítja az elem engedélyezett állapotát, és vizuálisan frissíti."""
        super().setEnabled(enabled)
        self._internal_button.setEnabled(enabled)
        self._update_visuals()

    def _update_visuals(self):
        """
        Absztrakt metódus, amelyet a származtatott osztályoknak kell implementálniuk
        az ikon frissítéséhez az aktuális állapot és engedélyezettség alapján.
        """
        raise NotImplementedError("A _update_visuals() metódust implementálni kell a származtatott osztályban.")

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """
        Eseményszűrő a belső QToolButton eseményeinek elfogására,
        hogy a ToolbarItem kezelhesse a kattintás és a drag-and-drop logikáját.
        """
        if watched == self._internal_button:
            # --- JAVÍTÁS KEZDETE ---
            # Ha a gomb le van tiltva, ne reagáljunk semmilyen egéreseményre.
            if not self.isEnabled():
                return super().eventFilter(watched, event)
            # --- JAVÍTÁS VÉGE ---

            if event.type() == QEvent.MouseButtonPress:
                mouse_event: QMouseEvent = event
                if mouse_event.button() == Qt.LeftButton:
                    self._start_pos = mouse_event.pos()
                    self._dragging = False
                    return True 
                
            elif event.type() == QEvent.MouseMove:
                mouse_event: QMouseEvent = event
                if mouse_event.buttons() == Qt.LeftButton and not self._dragging:
                    distance = (mouse_event.pos() - self._start_pos).manhattanLength()
                    drag_threshold = QApplication.startDragDistance()
                    if distance > drag_threshold:
                        self._start_drag()
                        self._dragging = True
                        return True
                
            elif event.type() == QEvent.MouseButtonRelease:
                mouse_event: QMouseEvent = event
                # --- JAVÍTÁS KEZDETE ---
                # A kattintást csak akkor kezeljük, ha nem drag művelet történt ÉS a gomb engedélyezve van.
                # Bár a legfelső 'if' már szűr, ez a dupla ellenőrzés még biztonságosabbá teszi.
                if not self._dragging and mouse_event.button() == Qt.LeftButton and self.isEnabled():
                # --- JAVÍTÁS VÉGE ---
                    self._handle_internal_button_clicked()
                
                self._dragging = False
                return True

        return super().eventFilter(watched, event)

    def _start_drag(self):
        """Elindítja a drag-and-drop műveletet."""
        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(self.item_id)
        drag.setMimeData(mime_data)

        pixmap = QPixmap(self.size())
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        self.render(painter, QPoint()) 
        painter.end()

        drag.setPixmap(pixmap)
        drag.setHotSpot(QPoint(self.width() // 2, self.height() // 2)) 
        
        self.itemDragStarted.emit(self.item_id)
        drag.exec(Qt.MoveAction | Qt.CopyAction)
        self._dragging = False

    def apply_stylesheet(self, bg_color: QColor, hover_color: QColor, pressed_color: QColor):
        """
        Elkészít egy QSS stíluslapot a megadott színekből és alkalmazza a belső gombon.
        """
        # A .name() metódus a hexadecimális stringet adja vissza (pl. #RRGGBB)
        stylesheet = f"""
            QToolButton {{
                background-color: {bg_color.name()};
                border: 1px solid rgba(0, 0, 0, 40);
                border-radius: 4px;
                padding: 2px;
            }}
            QToolButton:hover {{
                background-color: {hover_color.name()};
            }}
            QToolButton:pressed {{
                background-color: {pressed_color.name()};
            }}
            QToolButton:disabled {{
                background-color: rgba(200, 200, 200, 128);
            }}
        """
        self._internal_button.setStyleSheet(stylesheet)