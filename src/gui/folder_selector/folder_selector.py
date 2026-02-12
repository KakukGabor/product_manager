# gui/folder_selector/folder_selector.py

import os
import sys
from PySide6.QtWidgets import QWidget, QLabel, QLineEdit, QPushButton, QHBoxLayout, QVBoxLayout, QFileDialog, QApplication, QMessageBox
from PySide6.QtCore import Qt, Signal

class PySideFolderSelector(QWidget):
    pathChanged = Signal(str)
    validationStatusChanged = Signal(bool)

    def __init__(self, label_text="Mappa:", initial_path="", parent=None): # icon_path kivéve
        super().__init__(parent)

        self._default_border_style = "QLineEdit { background-color: #606060; color: white; border: 1px solid #606060; font-weight: bold; }"
        self._invalid_border_style = "QLineEdit { background-color: #E03C3C; color: white; border: 1px solid #C00000; font-weight: bold; }" 

        self._setup_ui(label_text) # icon_path kivéve

        self.set_path(initial_path)

    def _setup_ui(self, label_text): # icon_path paraméter KIVÉVE
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.label = QLabel(label_text)
        main_layout.addWidget(self.label)

        entry_button_layout = QHBoxLayout()
        entry_button_layout.setContentsMargins(0, 0, 0, 0)

        self.path_entry = QLineEdit()
        self.path_entry.setStyleSheet(self._default_border_style)
        self.path_entry.setPlaceholderText("Kérlek állítsd be!")
        entry_button_layout.addWidget(self.path_entry)
        
        # Ez a sor okozza a hibát, ha a _validate_path_event nincs definiálva megfelelően.
        self.path_entry.editingFinished.connect(self._validate_path_event) # <--- Itt történik a hívás
        self.path_entry.textChanged.connect(self.pathChanged.emit)

        self.browse_button = QPushButton()
        self.browse_button.setFixedWidth(40)
        self.browse_button.clicked.connect(self._browse_folder_dialog)

        self.browse_button.setText("...")

        entry_button_layout.addWidget(self.browse_button)
        main_layout.addLayout(entry_button_layout)

    def _browse_folder_dialog(self):
        initial_dir = self.get_path()
        if not os.path.isdir(initial_dir):
            initial_dir = os.path.expanduser("~") 
            if sys.platform == "win32" and os.path.exists("D:\\"):
                initial_dir = "D:\\"
            elif sys.platform == "win32" and os.path.exists("C:\\"):
                initial_dir = "C:\\"

        selected_path = QFileDialog.getExistingDirectory(
            self,
            "Mappa kiválasztása",
            initial_dir
        )
        if selected_path:
            self.set_path(selected_path)

    # >>>>>>>>>>>>>>> Ennek a metódusnak ITT KELL LENNIE, az osztályon belül! <<<<<<<<<<<<<<<
    def _validate_path_event(self):
        """Eseménykezelő a szövegmező szerkesztésének befejezésekor."""
        self._validate_path(self.get_path())
    # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>><<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

    # >>>>>>>>>>>>>>> Ennek a metódusnak is ITT KELL LENNIE, az osztályon belül! <<<<<<<<<<<<<<<
    def _validate_path(self, path):
        """Validálja az elérési utat, és beállítja a keret színét."""
        is_valid = path and os.path.isdir(path)

        if not is_valid:
            self.path_entry.setStyleSheet(self._invalid_border_style)
            self.validationStatusChanged.emit(False)
        else:
            self.path_entry.setStyleSheet(self._default_border_style)
            self.validationStatusChanged.emit(True)
        return is_valid
    # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>><<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

    def get_path(self):
        return self.path_entry.text()

    def set_path(self, path):
        self.path_entry.setText(path)
        self._validate_path(path)
