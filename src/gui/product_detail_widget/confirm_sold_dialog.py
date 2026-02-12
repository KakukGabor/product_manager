# src/gui/product_detail_widget/confirm_sold_dialog.py
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox
)

class ConfirmSoldDialog(QDialog):
    """
    Felugró ablak, amely megerősítést kér a termék eladottként való megjelöléséhez,
    és opciót ad a végleges törlésre.
    """
    def __init__(self, product_title: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Eladás megerősítése")
        self.setFixedSize(400, 150)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)

        message_label = QLabel(f"Valóban el lett adva a(z) '{product_title}' termék?", self)
        message_label.setStyleSheet("font-size: 10pt;")
        main_layout.addWidget(message_label)

        self.delete_permanently_checkbox = QCheckBox("Végleges törlés (merevlemezről is)", self)
        self.delete_permanently_checkbox.setChecked(False)
        self.delete_permanently_checkbox.setStyleSheet("font-size: 9pt; color: #CC0000; font-weight: bold;")
        main_layout.addWidget(self.delete_permanently_checkbox)

        main_layout.addStretch()

        button_layout = QHBoxLayout()
        self.yes_button = QPushButton("Igen", self)
        self.yes_button.clicked.connect(self.accept)
        self.yes_button.setStyleSheet("""
            QPushButton { background-color: #4CAF50; color: white; padding: 8px 15px; border: none; border-radius: 4px; font-size: 10pt; }
            QPushButton:hover { background-color: #45a049; }
        """)

        self.no_button = QPushButton("Nem", self)
        self.no_button.clicked.connect(self.reject)
        self.no_button.setStyleSheet("""
            QPushButton { background-color: #f44336; color: white; padding: 8px 15px; border: none; border-radius: 4px; font-size: 10pt; }
            QPushButton:hover { background-color: #da190b; }
        """)

        button_layout.addStretch()
        button_layout.addWidget(self.no_button)
        button_layout.addWidget(self.yes_button)
        main_layout.addLayout(button_layout)

    def should_delete_permanently(self) -> bool:
        return self.delete_permanently_checkbox.isChecked()