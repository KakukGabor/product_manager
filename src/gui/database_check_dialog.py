# gui/database_check_dialog.py

import logging
from typing import Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget
)
from PySide6.QtCore import Qt, Signal, Slot

logger = logging.getLogger(__name__)

# A stíluslap változatlan
DIALOG_STYLESHEET = """
    #checkDialog {
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
    #contentContainer QPushButton {
        font-size: 10pt;
        padding: 10px;
        font-weight: bold;
    }
    #buttonContainer {
        background-color: #A0C4FF;
        border-top: 1px solid #8FAADC;
    }
    QPushButton { padding: 8px 20px; border: 1px solid #777; border-radius: 4px; font-size: 10pt; background-color: #F0F0F0; }
    QPushButton:hover { background-color: #E0E0E0; }
    #runButton { font-weight: bold; background-color: #007bff; color: white; border-color: #0056b3; }
    #runButton:hover { background-color: #0069d9; }
    #uploadDbButton {
        background-color: #FFF3CD; /* Enyhén sárgás kiemelés */
        border-color: #FFE8A1;
    }
    #uploadDbButton:hover {
        background-color: #FDEEAA;
    }
"""

class DatabaseCheckDialog(QDialog):
    checkRequested = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Adatbázis Ellenőrzése")
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        # --- MÓDOSÍTÁS: A dialógus magasabb lesz az új gomb miatt ---
        self.setFixedSize(500, 400)
        self.setObjectName("checkDialog")
        self.setStyleSheet(DIALOG_STYLESHEET)
        
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        header_label = QLabel("Adatbázis Karbantartó Eszközök")
        header_label.setObjectName("headerLabel")
        main_layout.addWidget(header_label)

        content_container = QWidget()
        content_container.setObjectName("contentContainer")
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(20, 20, 20, 20)
        
        self.full_list_button = QPushButton("Teljes adatbázis listázása (riport)")
        content_layout.addWidget(self.full_list_button)

        self.duplicate_id_button = QPushButton("Duplikált ID-k keresése a mappákban")
        content_layout.addWidget(self.duplicate_id_button)

        self.server_duplicate_check_button = QPushButton("Duplikált termékek keresése a szerveren")
        content_layout.addWidget(self.server_duplicate_check_button)

        # --- MÓDOSÍTÁS: Új gomb hozzáadása a harmadik helyre ---
        self.sync_check_button = QPushButton("Szerver-Kliens Szinkronizáció Ellenőrzése")
        content_layout.addWidget(self.sync_check_button)
        
        self.upload_db_button = QPushButton("Adatbázis feltöltése Szerverre")
        self.upload_db_button.setObjectName("uploadDbButton")
        content_layout.addWidget(self.upload_db_button)

        main_layout.addWidget(content_container)
        main_layout.addStretch(1)

        button_container = QWidget()
        button_container.setObjectName("buttonContainer")
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(15, 8, 15, 8)
        
        self.cancel_button = QPushButton("Bezárás")
        button_layout.addStretch(1)
        button_layout.addWidget(self.cancel_button)
        main_layout.addWidget(button_container)

    def _connect_signals(self):
        self.full_list_button.clicked.connect(self._on_full_list_requested)
        self.duplicate_id_button.clicked.connect(self._on_duplicate_id_requested)
        self.server_duplicate_check_button.clicked.connect(self._on_server_duplicate_check_requested)
        self.sync_check_button.clicked.connect(self._on_sync_check_requested)
        self.upload_db_button.clicked.connect(self._on_upload_db_requested)
        self.cancel_button.clicked.connect(self.reject)

    @Slot()
    def _on_full_list_requested(self):
        self.checkRequested.emit("full_list_report")

    @Slot()
    def _on_duplicate_id_requested(self):
        self.checkRequested.emit("duplicate_id_check")

    # --- MÓDOSÍTÁS: Új slot metódus az új gombhoz ---
    @Slot()
    def _on_sync_check_requested(self):
        self.checkRequested.emit("server_client_sync_check")

    @Slot()
    def _on_upload_db_requested(self):
        self.checkRequested.emit("upload_database_to_server")

    @Slot()
    def _on_server_duplicate_check_requested(self):
        self.checkRequested.emit("server_duplicate_id_check")