# src/gui/product_detail_widget/remove_from_markets_dialog.py
import logging
from typing import List, Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox,
    QWidget, QMessageBox, QFrame, QSpacerItem, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, Slot
from models.product_model import Product

logger = logging.getLogger(__name__)

DIALOG_STYLESHEET = """
    #removeDialog {
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
    #listContainer QLabel, #listContainer QCheckBox {
        font-size: 10pt;
        font-weight: bold;
        color: #333;
    }
    QCheckBox:disabled {
        color: #999; /* Szürkézzük a letiltott checkbox szövegét */
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
    #okButton {
        font-weight: bold;
        background-color: #dc3545; /* Piros, a törlési szándék jelzésére */
        color: white;
        border-color: #c82333;
    }
    #okButton:hover {
        background-color: #c82333;
    }
"""

class RemoveFromMarketsDialog(QDialog):
    """
    Felugró ablak a piacterek kiválasztásához, ahonnan a terméket el kell távolítani.
    """
    MARKETPLACES = ["Galéria Savaria", "Jófogás"]

    def __init__(self, product: Product, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.product = product
        self.setWindowTitle("Eltávolítás a Piacterekről")
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        
        # Módosítjuk a fix méretet, mivel a "Mindent kijelöl" már nem igényel helyet.
        self.setFixedSize(450, 200) 
        
        self.setObjectName("removeDialog")
        self.setStyleSheet(DIALOG_STYLESHEET)

        self.marketplace_checkboxes: List[QCheckBox] = []

        self._setup_ui()
        self._connect_signals()
        self._initialize_checkbox_states()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        header_label = QLabel(f"{self.product.title} eltávolítása")
        header_label.setObjectName("headerLabel")
        main_layout.addWidget(header_label)

        list_container = QWidget()
        list_container.setObjectName("listContainer")

        form_layout = QVBoxLayout(list_container)
        form_layout.setContentsMargins(20, 15, 20, 15)
        form_layout.setSpacing(10)
        
        # Eltávolítva: self.select_all_checkbox

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        form_layout.addWidget(line)

        for market_name in self.MARKETPLACES:
            checkbox = QCheckBox(market_name)
            self.marketplace_checkboxes.append(checkbox)
            form_layout.addWidget(checkbox)

        # Helykitöltő a korábbi "Mindent kijelöl" helyére
        form_layout.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Minimum, QSizePolicy.Minimum))

        main_layout.addWidget(list_container)
        main_layout.addStretch(1)

        button_container = QWidget()
        button_container.setObjectName("buttonContainer")
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(15, 8, 15, 8)

        self.ok_button = QPushButton("Termék eltávolítása")
        self.ok_button.setObjectName("okButton")
        self.cancel_button = QPushButton("Mégsem")

        button_layout.addStretch(1)
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.ok_button)
        main_layout.addWidget(button_container)

    def _connect_signals(self):
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)
        # Eltávolítva: self.select_all_checkbox.toggled.connect(self._on_select_all_toggled)
        # Már nincs rá szükség, mert a bejelölés programból történik.

    def _initialize_checkbox_states(self):
        """
        Beállítja a jelölőnégyzetek kezdeti állapotát a termék állapota alapján.
        ÚJ: Kezeli a nem GS-függő termékeket is.
        """
        gs_checkbox = next((cb for cb in self.marketplace_checkboxes if cb.text() == "Galéria Savaria"), None)
        jf_checkbox = next((cb for cb in self.marketplace_checkboxes if cb.text() == "Jófogás"), None)

        ### MÓDOSÍTÁS KEZDETE ###
        if not self.product.is_gs_dependent:
            # ESET 1: A termék NEM GS-függő (tehát csak a Jófogás jöhet szóba)
            if gs_checkbox:
                gs_checkbox.setChecked(False)
                gs_checkbox.setEnabled(False)
                gs_checkbox.setToolTip("Ez a termék nem Galéria Savaria függő, ezért onnan nem távolítható el.")
            if jf_checkbox:
                jf_checkbox.setChecked(True)
                jf_checkbox.setEnabled(True)
        else:
            # ESET 2: A termék GS-függő (a régi logika finomítva)
            if self.product.is_delisted_on_gs:
                # A termék már törölve lett a GS-ről
                if gs_checkbox:
                    gs_checkbox.setChecked(False)
                    gs_checkbox.setEnabled(False)
                    gs_checkbox.setToolTip("Ez a termék már nem található meg a Galéria Savarián.")
                if jf_checkbox:
                    # Ha a GS-ről már lekerült, valószínűleg a Jófogásról is le akarja venni.
                    jf_checkbox.setChecked(True)
                    jf_checkbox.setEnabled(True)
            else:
                # A termék még fent van a GS-en, a felhasználó dönthet.
                if gs_checkbox:
                    gs_checkbox.setChecked(True)
                    gs_checkbox.setEnabled(True)
                if jf_checkbox:
                    jf_checkbox.setChecked(True)
                    jf_checkbox.setEnabled(True)
   
    def get_selected_markets(self) -> List[str]:
        return [cb.text() for cb in self.marketplace_checkboxes if cb.isChecked()]

    def accept(self):
        if not self.get_selected_markets():
            QMessageBox.warning(self, "Hiányzó kiválasztás", "A folytatáshoz legalább egy piacteret ki kell jelölni!")
            return

        super().accept()