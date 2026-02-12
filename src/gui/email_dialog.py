# src/gui/email_dialog.py
import logging
from typing import Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QWidget
)
from PySide6.QtCore import Qt

logger = logging.getLogger(__name__)

DIALOG_STYLESHEET = """
    #emailDialog {
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
    #formContainer QLabel {
        font-size: 10pt;
        font-weight: bold;
        color: #333;
    }
    QLineEdit {
        font-size: 10pt;
        padding: 5px;
        border: 1px solid #B0C4DE;
        border-radius: 4px;
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
    #sendButton {
        font-weight: bold;
        background-color: #007bff;
        color: white;
        border-color: #0056b3;
    }
    #sendButton:hover {
        background-color: #0069d9;
    }
"""

class EmailDialog(QDialog):
    def __init__(self, product_title: str, default_recipient: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Email Küldése")
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setFixedSize(500, 200)
        self.setObjectName("emailDialog")
        self.setStyleSheet(DIALOG_STYLESHEET)

        self._setup_ui(product_title, default_recipient)
        self._connect_signals()

    def _setup_ui(self, product_title: str, default_recipient: str):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        header_label = QLabel(f"'{product_title}' adatlap küldése")
        header_label.setObjectName("headerLabel")
        main_layout.addWidget(header_label)

        form_container = QWidget()
        form_container.setObjectName("formContainer")
        form_layout = QVBoxLayout(form_container)
        form_layout.setContentsMargins(15, 15, 15, 15)
        form_layout.setSpacing(10)

        form_layout.addWidget(QLabel("Címzett email címe:"))
        self.recipient_edit = QLineEdit()
        self.recipient_edit.setText(default_recipient)
        self.recipient_edit.setPlaceholderText("címzett@email.hu")
        form_layout.addWidget(self.recipient_edit)

        form_layout.addStretch()
        main_layout.addWidget(form_container, 1)

        button_container = QWidget()
        button_container.setObjectName("buttonContainer")
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(15, 8, 15, 8)

        self.send_button = QPushButton("Küldés")
        self.send_button.setObjectName("sendButton")
        self.cancel_button = QPushButton("Mégse")

        button_layout.addStretch(1)
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.send_button)
        main_layout.addWidget(button_container)

    def _connect_signals(self):
        self.send_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

    def get_recipient(self) -> str:
        return self.recipient_edit.text().strip()