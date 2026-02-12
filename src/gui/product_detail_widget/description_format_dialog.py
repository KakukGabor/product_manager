# src/gui/product_detail_widget/description_format_dialog.py
import logging
from typing import Dict, Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QRadioButton, QWidget, QButtonGroup
)
from PySide6.QtCore import Qt, Signal

logger = logging.getLogger(__name__)

DIALOG_STYLESHEET = """
    #formatDialog { background-color: #F0F8FF; border: 1px solid #4682B4; }
    #headerLabel { background-color: #4682B4; color: white; font-size: 11pt; font-weight: bold; padding: 8px; }
    #contentContainer QRadioButton { font-size: 10pt; font-weight: bold; color: #333; }
    #bulletCharRadio { font-size: 9pt; font-weight: normal; }
    #buttonContainer { background-color: #A0C4FF; border-top: 1px solid #8FAADC; }
    QPushButton { padding: 8px 20px; border: 1px solid #777; border-radius: 4px; font-size: 10pt; background-color: #F0F0F0; }
    QPushButton:hover { background-color: #E0E0E0; }
    #applyButton { font-weight: bold; background-color: #007bff; color: white; border-color: #0056b3; }
    #applyButton:hover { background-color: #0069d9; }
    #undoButton { font-weight: bold; background-color: #ffc107; color: black; border-color: #e0a800; }
    #undoButton:hover { background-color: #e0a800; }
"""

class DescriptionFormatDialog(QDialog):
    undoRequested = Signal()

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setWindowTitle("Leírás Formázása")
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setFixedSize(450, 270)
        self.setObjectName("formatDialog")
        self.setStyleSheet(DIALOG_STYLESHEET)
        
        self.option_group = QButtonGroup(self)
        self.bullet_char_group = QButtonGroup(self)

        self._setup_ui()
        self._connect_signals()
        
        self._on_main_option_changed()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        header_label = QLabel("Formázási Opciók")
        header_label.setObjectName("headerLabel")
        main_layout.addWidget(header_label)

        content_container = QWidget()
        content_container.setObjectName("contentContainer")
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(20, 20, 20, 20)
        
        self.cleanup_whitespace_radio = QRadioButton("Takarítás (felesleges szóközök és sorok eltávolítása)")
        self.cleanup_whitespace_radio.setChecked(True)
        
        self.unify_lines_radio = QRadioButton("Bekezdés (minden sor összefűzése egy bekezdéssé)")

        self.option_group.addButton(self.cleanup_whitespace_radio)
        self.option_group.addButton(self.unify_lines_radio)

        content_layout.addWidget(self.cleanup_whitespace_radio)
        content_layout.addWidget(self.unify_lines_radio)
        
        bullet_layout = QHBoxLayout()
        self.bullet_points_radio = QRadioButton("Felsorolás")
        self.option_group.addButton(self.bullet_points_radio)
        bullet_layout.addWidget(self.bullet_points_radio)
        bullet_layout.addStretch()

        self.bullet_char_dot_radio = QRadioButton("• (Pötty)")
        self.bullet_char_dot_radio.setObjectName("bulletCharRadio")
        self.bullet_char_dot_radio.setChecked(True)
        self.bullet_char_group.addButton(self.bullet_char_dot_radio)
        bullet_layout.addWidget(self.bullet_char_dot_radio)

        self.bullet_char_circle_radio = QRadioButton("◦ (Karika)")
        self.bullet_char_circle_radio.setObjectName("bulletCharRadio")
        self.bullet_char_group.addButton(self.bullet_char_circle_radio)
        bullet_layout.addWidget(self.bullet_char_circle_radio)

        content_layout.addLayout(bullet_layout)
        content_layout.addStretch(1)
        main_layout.addWidget(content_container)

        button_container = QWidget()
        button_container.setObjectName("buttonContainer")
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(15, 8, 15, 8)
        
        self.undo_button = QPushButton("Visszavonás")
        self.undo_button.setObjectName("undoButton")
        self.apply_button = QPushButton("Alkalmaz")
        self.apply_button.setObjectName("applyButton")
        self.cancel_button = QPushButton("Mégse")
        
        button_layout.addWidget(self.undo_button)
        button_layout.addStretch(1)
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.apply_button)
        main_layout.addWidget(button_container)

    def _connect_signals(self):
        self.apply_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)
        self.undo_button.clicked.connect(self.undoRequested.emit)
        self.option_group.buttonClicked.connect(self._on_main_option_changed)

    def _on_main_option_changed(self):
        is_bullet_selected = self.bullet_points_radio.isChecked()
        self.bullet_char_dot_radio.setEnabled(is_bullet_selected)
        self.bullet_char_circle_radio.setEnabled(is_bullet_selected)

    def get_selected_option(self) -> Optional[Dict]:
        if self.cleanup_whitespace_radio.isChecked():
            return {"format_type": "cleanup_whitespace"}
        if self.unify_lines_radio.isChecked():
            return {"format_type": "unify_lines"}
        if self.bullet_points_radio.isChecked():
            bullet_char = "•" if self.bullet_char_dot_radio.isChecked() else "◦"
            return {"format_type": "bullet_points", "bullet_char": bullet_char}
        return None