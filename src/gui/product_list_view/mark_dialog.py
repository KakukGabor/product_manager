# src/gui/product_list_view/mark_dialog.py
import logging
from typing import Dict, Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QRadioButton, QWidget, QButtonGroup
)
from PySide6.QtCore import Qt, Signal

logger = logging.getLogger(__name__)

DIALOG_STYLESHEET = """
    #markDialog {
        background-color: #F0F8FF;
        border: 1px solid #4682B4;
    }
    #headerLabel {
        background-color: #4682B4;
        color: white;
        font-size: 11pt;
        font-weight: bold;
        padding: 8px;
    }
    #contentContainer QRadioButton {
        font-size: 10pt;
        font-weight: bold;
        color: #333;
        padding-top: 5px;
    }
    #buttonContainer {
        background-color: #A0C4FF;
        border-top: 1px solid #8FAADC;
    }
    QPushButton {
        padding: 8px 20px;
        border: 1px solid #777;
        border-radius: 4px;
        font-size: 10pt;
        background-color: #F0F0F0;
    }
    QPushButton:hover {
        background-color: #E0E0E0;
    }
    #applyButton {
        font-weight: bold;
        background-color: #007bff;
        color: white;
        border-color: #0056b3;
    }
    #applyButton:hover {
        background-color: #0069d9;
    }
"""

class MarkDialog(QDialog):
    applyMarking = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Termékek Megjelölése")
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setFixedSize(400, 240)
        self.setObjectName("markDialog")
        self.setStyleSheet(DIALOG_STYLESHEET)
        
        self.option_group = QButtonGroup(self)

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        header_label = QLabel("Megjelölés Státusz Alapján")
        header_label.setObjectName("headerLabel")
        main_layout.addWidget(header_label)

        content_container = QWidget()
        content_container.setObjectName("contentContainer")
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(20, 20, 20, 20)
        
        self.no_marking_radio = QRadioButton("Nincs jelölés")
        self.no_marking_radio.setChecked(True)
        
        self.posted_fb_radio = QRadioButton("Posztolva (Facebook)")
        self.ad_created_fb_radio = QRadioButton("Hirdetés feladva (Facebook)")
        self.inactive_jf_radio = QRadioButton("Inaktív a Jófogáson")

        self.option_group.addButton(self.no_marking_radio)
        self.option_group.addButton(self.posted_fb_radio)
        self.option_group.addButton(self.ad_created_fb_radio)
        self.option_group.addButton(self.inactive_jf_radio)

        content_layout.addWidget(self.no_marking_radio)
        content_layout.addWidget(self.posted_fb_radio)
        content_layout.addWidget(self.ad_created_fb_radio)
        content_layout.addWidget(self.inactive_jf_radio)
        
        content_layout.addStretch(1)
        main_layout.addWidget(content_container)

        button_container = QWidget()
        button_container.setObjectName("buttonContainer")
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(15, 8, 15, 8)
        
        self.apply_button = QPushButton("Alkalmaz")
        self.apply_button.setObjectName("applyButton")
        self.cancel_button = QPushButton("Mégse")
        
        button_layout.addStretch(1)
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.apply_button)
        main_layout.addWidget(button_container)

    def _connect_signals(self):
        self.apply_button.clicked.connect(self._emit_apply_marking)
        self.cancel_button.clicked.connect(self.reject)

    def _emit_apply_marking(self):
        marking_key = "none"
        if self.posted_fb_radio.isChecked():
            marking_key = "posted_fb"
        elif self.ad_created_fb_radio.isChecked():
            marking_key = "ad_created_fb"
        elif self.inactive_jf_radio.isChecked():
            marking_key = "inactive_jf"
        
        self.applyMarking.emit(marking_key)
        self.accept()

    def set_current_marking(self, marking: str):
        """Beállítja a dialógus állapotát a controllerből kapott érték alapján."""
        if marking == "posted_fb":
            self.posted_fb_radio.setChecked(True)
        elif marking == "ad_created_fb":
            self.ad_created_fb_radio.setChecked(True)
        elif marking == "inactive_jf":
            self.inactive_jf_radio.setChecked(True)
        else:
            self.no_marking_radio.setChecked(True)