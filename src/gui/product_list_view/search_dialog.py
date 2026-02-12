import logging
from typing import Dict
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QCheckBox, QWidget, QMessageBox
)
from PySide6.QtCore import Qt, Signal, Slot

logger = logging.getLogger(__name__)

DIALOG_STYLESHEET = """
    #searchDialog {
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
    QLabel, QCheckBox {
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
    QPushButton { padding: 8px 20px; border: 1px solid #777; border-radius: 4px; font-size: 10pt; background-color: #F0F0F0; }
    QPushButton:hover { background-color: #E0E0E0; }
    #applyButton { font-weight: bold; background-color: #007bff; color: white; border-color: #0056b3; }
    #applyButton:hover { background-color: #0069d9; }
"""

class SearchDialog(QDialog):
    applySearch = Signal(dict)
    clearSearch = Signal()

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setWindowTitle("Keresés")
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setFixedSize(500, 250)
        self.setObjectName("searchDialog")
        self.setStyleSheet(DIALOG_STYLESHEET)

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self); main_layout.setContentsMargins(0, 0, 0, 0); main_layout.setSpacing(0)
        header_label = QLabel("Keresés szöveg alapján"); header_label.setObjectName("headerLabel"); main_layout.addWidget(header_label)

        form_container = QWidget(); form_layout = QVBoxLayout(form_container); form_layout.setContentsMargins(15, 15, 15, 15); form_layout.setSpacing(10)
        main_layout.addWidget(form_container, 1)

        form_layout.addWidget(QLabel("Keresendő szöveg:"))
        self.search_term_edit = QLineEdit(); self.search_term_edit.setPlaceholderText("Minimum 3 karakter")
        form_layout.addWidget(self.search_term_edit)

        checkbox_layout = QHBoxLayout(); checkbox_layout.setContentsMargins(0, 10, 0, 0)
        self.search_in_title_checkbox = QCheckBox("Keresés a címben"); self.search_in_title_checkbox.setChecked(True)
        self.search_in_desc_checkbox = QCheckBox("Keresés a leírásban")
        checkbox_layout.addWidget(self.search_in_title_checkbox); checkbox_layout.addWidget(self.search_in_desc_checkbox); checkbox_layout.addStretch()
        form_layout.addLayout(checkbox_layout)
        form_layout.addStretch()

        button_container = QWidget(); button_container.setObjectName("buttonContainer"); button_layout = QHBoxLayout(button_container); button_layout.setContentsMargins(15, 8, 15, 8)
        self.apply_button = QPushButton("Keresés"); self.apply_button.setObjectName("applyButton")
        self.clear_button = QPushButton("Törlés")
        self.cancel_button = QPushButton("Mégse")
        button_layout.addWidget(self.apply_button); button_layout.addStretch(1); button_layout.addWidget(self.clear_button); button_layout.addWidget(self.cancel_button)
        main_layout.addWidget(button_container)

    def _connect_signals(self):
        self.apply_button.clicked.connect(self._emit_apply_search)
        self.cancel_button.clicked.connect(self.reject)
        self.clear_button.clicked.connect(self._emit_clear_search)
        self.search_in_title_checkbox.toggled.connect(self._handle_checkbox_logic)
        self.search_in_desc_checkbox.toggled.connect(self._handle_checkbox_logic)

    @Slot()
    def _handle_checkbox_logic(self):
        if not self.search_in_title_checkbox.isChecked() and not self.search_in_desc_checkbox.isChecked():
            sender = self.sender()
            if sender:
                sender.setChecked(True)

    @Slot()
    def _emit_apply_search(self):
        term = self.search_term_edit.text().strip()
        if len(term) < 3:
            QMessageBox.warning(self, "Túl rövid", "A keresendő szövegnek legalább 3 karakter hosszúnak kell lennie.")
            return

        search_criteria = {
            "search_term": term,
            "search_in_title": self.search_in_title_checkbox.isChecked(),
            "search_in_description": self.search_in_desc_checkbox.isChecked()
        }
        self.applySearch.emit(search_criteria)
        self.accept()

    @Slot()
    def _emit_clear_search(self):
        self.clearSearch.emit()
        self.accept()

    def set_current_search(self, filters: Dict):
        self.search_term_edit.setText(filters.get("search_term", ""))
        self.search_in_title_checkbox.setChecked(filters.get("search_in_title", True))
        self.search_in_desc_checkbox.setChecked(filters.get("search_in_description", False))