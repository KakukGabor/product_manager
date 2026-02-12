# src/gui/text_editor/special_character_dialog.py
import logging
from typing import Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QPushButton, QWidget, QScrollArea, QGroupBox
)
from PySide6.QtCore import Qt, Signal

logger = logging.getLogger(__name__)

SPECIAL_CHARACTERS = [
    {
        "title": "Listajelek",
        "items": [
            ("•", "Kör (Felsorolásjel)"),
            ("◦", "Karika (Felsorolásjel)"),
        ]
    },
    {
        "title": "Címsorok és Általános Figyelemfelkeltés",
        "items": [
            ("✨", "Csillogás (minőség, különlegesség)"),
            ("🏛️", "Klasszikus Épület (szerkezet, stílus, történet)"),
            ("⚜️", "Francia Liliom (elegancia, arisztokrácia)"),
            ("📜", "Tekercs (történet, származás, hitelesség)"),
            ("👑", "Korona (exkluzivitás, királyi darabok)"),
        ]
    },
    {
        "title": "Tulajdonságok és Részletek Leírása",
        "items": [
            ("📏", "Vonalzó (méretek)"),
            ("📐", "Derékszögű Vonalzó (méretek)"),
            ("🔨", "Kalapács (restaurálás, kézműves munka)"),
            ("🎨", "Festőpaletta (szín, felületkezelés)"),
            ("🔍", "Nagyító (aprólékos részletek, faragások)"),
            ("📌", "Rajzszög (lista bevezetése, pl. 'Főbb jellemzők')"),
            ("✅", "Pipa (előnyök, elvégzett munkák listázása)"),
        ]
    },
    {
        "title": "Hangulatteremtés és Történetmesélés",
        "items": [
            ("🕰️", "Ingaóra (történelem, klasszikus hangulat)"),
            ("💎", "Gyémánt (érték, ritkaság)"),
            ("✒️", "Töltőtoll (íróasztalok, szekreterek)"),
            ("🕯️", "Gyertya (korabeli hangulat)"),
            ("📚", "Könyvek (antiquarian stílus, könyvespolcok)"),
        ]
    },
    {
        "title": "Praktikus és Cselekvésre Ösztönző Emojik",
        "items": [
            ("👇", "Lefelé mutató ujj (linkre irányítás)"),
            ("🌐", "Földgömb (weboldal linkje elé)"),
            ("📞", "Telefon (elérhetőség)"),
            ("✉️", "Levél (elérhetőség)"),
            ("📍", "Gombostű (helyszín megjelölése)"),
        ]
    }
]


class SpecialCharacterDialog(QDialog):
    characterSelected = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Speciális Karakterek")
        self.setMinimumSize(500, 400)
        
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        main_layout.addWidget(scroll_area)

        content_widget = QWidget()
        scroll_area.setWidget(content_widget)
        
        content_layout = QVBoxLayout(content_widget)

        for category in SPECIAL_CHARACTERS:
            group_box = QGroupBox(category["title"])
            group_layout = QVBoxLayout(group_box)
            
            for character, description in category["items"]:
                button_text = f"{character}  {description}"
                button = QPushButton(button_text)
                button.setFixedHeight(30)
                button.setStyleSheet("text-align: left; padding-left: 10px; font-size: 10pt;")
                
                # --- JAVÍTÁS ITT ---
                # 1. Az adatot (a karaktert) a gomb "property"-jeként tároljuk.
                button.setProperty("character_data", character)
                # 2. A gomb jelzését egy közös slothoz kötjük, ami nem vár paramétert.
                button.clicked.connect(self._on_character_clicked)
                # --- JAVÍTÁS VÉGE ---
                
                group_layout.addWidget(button)
            
            content_layout.addWidget(group_box)
        
        content_layout.addStretch()

    def _on_character_clicked(self):
        # --- JAVÍTÁS ITT ---
        # 1. Lekérdezzük, hogy melyik gomb küldte a jelzést.
        sender_button = self.sender()
        if not sender_button:
            return

        # 2. Leolvassuk a gombról a korábban rámentett karaktert.
        character = sender_button.property("character_data")
        
        # 3. Kibocsátjuk a signalt a helyes karakterrel, majd bezárjuk a dialógust.
        if character:
            self.characterSelected.emit(character)
            self.close()
        # --- JAVÍTÁS VÉGE ---