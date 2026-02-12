# src/gui/image_gallery_widget/image_thumbnail_widget.py
import logging
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QMessageBox, QPushButton, QSizePolicy, QCheckBox, QMenu, QApplication
)
from PySide6.QtGui import QPixmap, QIcon, QContextMenuEvent, QAction
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtCore import Qt, Signal, Slot, QSize
from managers.resource_manager import ResourceManager

logger = logging.getLogger(__name__)

class ImageThumbnailWidget(QWidget):
    imageDeleted = Signal(str, str, str)
    moveUpRequested = Signal(str, str, str)
    moveDownRequested = Signal(str, str, str)
    selectionToggled = Signal(str, bool)

    def __init__(self, image_path: str, tag: str, filename: str, product_id: str, 
                 show_controls: bool = True, show_filename: bool = True, 
                 is_selected: bool = False,
                 resource_manager: ResourceManager = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("imageThumbnailWidget")
        self.resource_manager = resource_manager
        self.image_path = image_path
        self.tag = tag
        self.filename = filename
        self.product_id = product_id
        self._pixmap: Optional[QPixmap] = None
        self._show_controls = show_controls
        self._show_filename = show_filename
        self._is_selected = is_selected

        self._setup_ui()
        self._load_pixmap()

    def _log(self, level: int, message: str, *args, **kwargs):
        logger.log(level, f"[ImageThumbnailWidget] {message}", *args, **kwargs)

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(5)
        main_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(2)
        top_layout.setAlignment(Qt.AlignTop)

        # Ikonok lekérése a ResourceManager-ből
        up_icon_path = self.resource_manager.get_icon_path("arrow_up")
        down_icon_path = self.resource_manager.get_icon_path("arrow_down")
        delete_icon_path = self.resource_manager.get_icon_path("trash")

        # Fel nyíl gomb
        self.move_up_button = QPushButton()
        up_icon = QIcon(up_icon_path) if up_icon_path else QIcon.fromTheme("go-up")
        self.move_up_button.setIcon(up_icon)
        self.move_up_button.setFixedSize(20, 20)
        self.move_up_button.setFlat(True)
        self.move_up_button.setToolTip("Feljebb mozgat")
        self.move_up_button.clicked.connect(lambda: self.moveUpRequested.emit(self.tag, self.filename, self.product_id))
        self.move_up_button.setVisible(self._show_controls)
        top_layout.addWidget(self.move_up_button)

        # Le nyíl gomb
        self.move_down_button = QPushButton()
        down_icon = QIcon(down_icon_path) if down_icon_path else QIcon.fromTheme("go-down")
        self.move_down_button.setIcon(down_icon)
        self.move_down_button.setFixedSize(20, 20)
        self.move_down_button.setFlat(True)
        self.move_down_button.setToolTip("Lejjebb mozgat")
        self.move_down_button.clicked.connect(lambda: self.moveDownRequested.emit(self.tag, self.filename, self.product_id))
        self.move_down_button.setVisible(self._show_controls)
        top_layout.addWidget(self.move_down_button)


        # --- ÚJ: JELÖLŐNÉGYZET LÉTREHOZÁSA ---
        self.select_checkbox = QCheckBox()
        self.select_checkbox.setChecked(self._is_selected)
        self.select_checkbox.setVisible(False) # Alapból rejtett
        self.select_checkbox.setToolTip("Kép kiválasztása posztoláshoz")
        # Stílus: legyen kicsit feltűnőbb, ha ki van jelölve
        self.select_checkbox.setStyleSheet("QCheckBox::indicator { width: 16px; height: 16px; }")
        self.select_checkbox.toggled.connect(lambda checked: self.selectionToggled.emit(self.filename, checked))
        
        top_layout.addWidget(self.select_checkbox)

        top_layout.addStretch()

        # Törlés gomb
        self.delete_button = QPushButton()
        delete_icon = QIcon(delete_icon_path) if delete_icon_path else QIcon.fromTheme("window-close")
        self.delete_button.setIcon(delete_icon)
        self.delete_button.setFixedSize(20, 20)
        self.delete_button.setFlat(True)
        self.delete_button.setToolTip("Kép törlése")
        self.delete_button.clicked.connect(self._confirm_delete)
        self.delete_button.setVisible(self._show_controls)
        top_layout.addWidget(self.delete_button)

        main_layout.addLayout(top_layout)

        self.image_label = QLabel(self)
        self.image_label.setObjectName("thumbnailImageLabel")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.image_label.setMinimumSize(50, 50)
        main_layout.addWidget(self.image_label)

        self.filename_label = QLabel(self.filename, self)
        self.filename_label.setAlignment(Qt.AlignCenter)
        self.filename_label.setWordWrap(True)
        self.filename_label.setVisible(self._show_filename)
        main_layout.addWidget(self.filename_label)

    def _update_scaled_pixmap(self):
        if self._pixmap and not self._pixmap.isNull():
            scaled_pixmap = self._pixmap.scaled(self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.image_label.setPixmap(scaled_pixmap)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_scaled_pixmap()

    def _load_pixmap(self):
        self._pixmap = QPixmap(self.image_path)
        if self._pixmap.isNull():
            self._log(logging.WARNING, f"Nem sikerült betölteni a képet: {self.image_path}")
            self.image_label.setText("Hiba!")
            self.image_label.setAlignment(Qt.AlignCenter)
            self.image_label.setPixmap(QPixmap())
        else:
            self._update_scaled_pixmap()

    def _confirm_delete(self):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Kép törlése")
        msg_box.setText(f"Biztosan törölni szeretné a '{self.filename}' képet?")
        msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)

        yes_button = msg_box.button(QMessageBox.Yes)
        if yes_button: yes_button.setText("Igen")
        no_button = msg_box.button(QMessageBox.No)
        if no_button: no_button.setText("Nem")

        msg_box.setDefaultButton(QMessageBox.No)
        reply = msg_box.exec()

        if reply == QMessageBox.Yes:
            self._log(logging.INFO, f"Kép törlése megerősítve: {self.filename}")
            self.imageDeleted.emit(self.tag, self.filename, self.product_id)

    def set_selection_mode(self, active: bool):
        """Kívülről hívható metódus a jelölőnégyzet megjelenítésére/elrejtésére."""
        self.select_checkbox.setVisible(active)

    def contextMenuEvent(self, event: QContextMenuEvent):
        """
        Ez a metódus automatikusan lefut, amikor a felhasználó jobb gombbal kattint a widgetre.
        """
        context_menu = QMenu(self)
        
        copy_action = QAction("Másolás", self)
        copy_action.triggered.connect(self._copy_image_to_clipboard)
        context_menu.addAction(copy_action)
        
        context_menu.exec(event.globalPos())
    
    @Slot()
    def _copy_image_to_clipboard(self):
        """
        Ez a metódus felelős a kép vágólapra helyezéséért.
        """
        if not self._pixmap or self._pixmap.isNull():
            self._log(logging.WARNING, "Vágólapra másolás sikertelen: a kép (pixmap) nincs betöltve.")
            return

        clipboard = QApplication.clipboard()
        clipboard.setPixmap(self._pixmap)
        
        self._log(logging.INFO, f"A '{self.filename}' kép a vágólapra másolva.")