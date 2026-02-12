# gui/upload_database_dialog.py
from typing import Dict, Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox, QWidget
)
from PySide6.QtCore import Qt

# A stíluslap megegyezik a szülő dialógus stílusával a konzisztens kinézetért.
DIALOG_STYLESHEET = """
    #uploadDialog {
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
    #contentContainer QCheckBox {
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
    #startButton {
        font-weight: bold;
        background-color: #28a745; /* Zöld, a pozitív akció jelzésére */
        color: white;
        border-color: #218838;
    }
    #startButton:hover {
        background-color: #218838;
    }
"""

class UploadDatabaseDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Adatbázis Feltöltése")
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setFixedSize(400, 200)
        self.setObjectName("uploadDialog")
        self.setStyleSheet(DIALOG_STYLESHEET)
        
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        header_label = QLabel("Adatbázis újraszinkronizálása a szerverre")
        header_label.setObjectName("headerLabel")
        main_layout.addWidget(header_label)

        content_container = QWidget()
        content_container.setObjectName("contentContainer")
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(20, 20, 20, 20)
        
        self.upload_json_checkbox = QCheckBox("Termék adatlapok (.json) feltöltése")
        self.upload_json_checkbox.setChecked(True)
        content_layout.addWidget(self.upload_json_checkbox)

        self.upload_images_checkbox = QCheckBox("Szerkesztett képek ('mixed_') feltöltése")
        self.upload_images_checkbox.setChecked(True)
        content_layout.addWidget(self.upload_images_checkbox)
        
        main_layout.addWidget(content_container)
        main_layout.addStretch(1)

        button_container = QWidget()
        button_container.setObjectName("buttonContainer")
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(15, 8, 15, 8)
        
        self.start_button = QPushButton("Indítás")
        self.start_button.setObjectName("startButton")
        self.cancel_button = QPushButton("Mégse")

        button_layout.addStretch(1)
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.start_button)
        main_layout.addWidget(button_container)

    def _connect_signals(self):
        self.start_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

    def get_upload_options(self) -> Dict[str, bool]:
        """Visszaadja a kiválasztott feltöltési opciókat."""
        return {
            "upload_json": self.upload_json_checkbox.isChecked(),
            "upload_images": self.upload_images_checkbox.isChecked(),
        }