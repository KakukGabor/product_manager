# src/gui/status_bar/status_bar_widget.py

import logging
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PySide6.QtGui import QPainter, QColor, QPaintEvent
from PySide6.QtCore import Qt, Signal, Slot, QSize

from managers.resource_manager import ResourceManager
from gui.toolbar_widget.two_state_button import TwoStateButton

logger = logging.getLogger(__name__)

# === ÚJ, SAJÁT WIDGET A TÖKÉLETES MEGOLDÁSHOZ ===
class ElidedLabel(QLabel):
    """
    Egy QLabel alosztály, ami garantáltan helyesen vágja le (elide) a túl hosszú szöveget,
    mivel a kirajzolási esemény (paintEvent) során teszi ezt meg, amikor a widget mérete már végleges.
    Ez megoldja az összes időzítési problémát.
    """
    def __init__(self, text: str = "", parent: QWidget = None):
        super().__init__(text, parent)
        self.setMinimumWidth(10) # Adjunk neki egy minimális szélességet

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        metrics = self.fontMetrics()
        
        # A szöveg levágása a widget aktuális szélessége alapján
        elided_text = metrics.elidedText(self.text(), Qt.ElideRight, self.width())

        # A szöveg kirajzolása a levágott formában
        painter.drawText(self.rect(), self.alignment(), elided_text)

# === ÚJ WIDGET VÉGE ===


class StatusBarWidget(QWidget):
    toggleClicked = Signal(bool)
    logMessageFormatted = Signal(str)

    LOG_LEVEL_COLORS = {
        "default": "#333333",
        logging.INFO: "#333333",
        "processing": "#0057B8",
        logging.WARNING: "#FFA500",
        logging.ERROR: "#E74C3C",
        logging.CRITICAL: "#C0392B",
        "ai_user": "#6A0DAD"
    }

    def __init__(self, resource_manager: ResourceManager, parent=None):
        super().__init__(parent)
        self.resource_manager = resource_manager
        
        self.setAutoFillBackground(True)
        self.background_color = QColor("#a6c1f5")
        self.border_color = QColor("#99CCFF")
        
        self.setFixedHeight(30)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 2, 10, 2) # Margók finomhangolása
        main_layout.setSpacing(10)

        # === JAVÍTÁS: A SAJÁT ElidedLabel WIDGET HASZNÁLATA ===
        self._status_label = ElidedLabel("Alkalmazás készenlétben.")
        # A stílust közvetlenül a widgeten állítjuk be, nem a QLineEdit-nek szánt módon
        self._status_label.setStyleSheet("background-color: transparent; border: none; font-weight: normal; padding: 0px;")
        
        main_layout.addWidget(self._status_label, 1) # A stretch faktor itt jelzi, hogy töltse ki a helyet
        
        # A külön addStretch hívás már nem szükséges, mert a widgethez adtuk a stretch faktort.
        # main_layout.addStretch(1) 

        # ... a gomb létrehozása és a többi kód változatlan ...
        icon_off = self.resource_manager.get_icon_path("console_up")
        icon_on = self.resource_manager.get_icon_path("console_down")

        self._log_toggle_button = TwoStateButton(
            item_id="log_toggle",
            icon_off_path=icon_off,
            icon_on_path=icon_on,
            tooltip="Előzmények panel megjelenítése/elrejtése",
            parent=self
        )
        self._log_toggle_button.setFixedSize(QSize(28, 28))
        self._log_toggle_button.set_item_size(QSize(28, 28))
        self._log_toggle_button._internal_button.setStyleSheet("border: none; background-color: transparent;")
        
        def new_update_visuals_without_graying(self_button):
            target_icon_path = self_button._icon_on_path if self_button._is_on else self_button._icon_off_path
            icon = self_button._get_icon_from_ref(self_button, target_icon_path, self_button._item_size * 0.8)
            self_button._internal_button.setIcon(icon)

        self._log_toggle_button._update_visuals = new_update_visuals_without_graying.__get__(self._log_toggle_button, TwoStateButton)
        self._log_toggle_button._update_visuals()

        main_layout.addWidget(self._log_toggle_button)
        self._log_toggle_button.itemClicked.connect(self._on_button_clicked)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.background_color)
        painter.setPen(self.border_color)
        painter.drawLine(0, 0, self.width(), 0)
        # Nem hívjuk a super().paintEvent(event)-et, mert mi magunk rajzolunk mindent.

    @Slot(str)
    def _on_button_clicked(self, button_id: str):
        is_on = self._log_toggle_button._is_on
        self.toggleClicked.emit(is_on)

    @Slot(str, int, object)
    def update_status(self, message: str, level: int, color_override: object):
        html_color = self.LOG_LEVEL_COLORS.get(level, self.LOG_LEVEL_COLORS["default"])

        if isinstance(color_override, str) and color_override:
            html_color = self.LOG_LEVEL_COLORS.get(color_override, color_override)

        # === JAVÍTÁS: A logika egyszerűsítése az új widgethez ===
        if self._status_label:
            # 1. Beállítjuk a teljes, vágatlan szöveget a labelre.
            self._status_label.setText(message)
            # 2. Beállítjuk a szöveg színét a stíluslappal.
            self._status_label.setStyleSheet(f"color: {html_color}; background-color: transparent; border: none; font-weight: normal; padding: 0px;")
            
        # A log panelnek továbbra is a teljes, formázott HTML-t küldjük.
        full_log_message = f"<span style='color: {html_color};'>{message}</span>"
        self.logMessageFormatted.emit(full_log_message)