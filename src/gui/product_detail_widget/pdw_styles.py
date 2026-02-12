# src/gui/product_detail_widget/pdw_styles.py

"""
Ez a fájl a ProductDetailWidget-hez tartozó QSS (Qt Style Sheets) stíluslapot
tartalmazza egy konstansban, a jobb karbantarthatóság és a tisztább kód érdekében.
"""

PRODUCT_DETAIL_STYLESHEET = """
    /* A terméklap teljes fő konténer widgetjének stílusa. */
    #productDetailWidget {
        background-color: #bed2e7; /* Háttérszín alapnézetben */
        border: 1px solid #DDDDDD; /* Halvány keret */
        border-radius: 5px; /* Lekerekített sarkok */
    }
    
    /* A görgethető területen belüli widget, ami a tényleges tartalmat (űrlap elemeket) hordozza. */
    #scrollContentWidget {
        background-color: #bed2e7;
        border: 1px solid #dee7fc;
    }


    /* --- Dinamikus stílusok szerkesztési és új termék módhoz --- */
    /* A fő konténer stílusa, amikor a widget 'Új termék' módban van (világoskék háttér). */
    #productDetailWidget[formMode="new_product"] {
        background-color: #fcfcf0;
        border: 1px solid #00BCD4;
    }
    /* A belső tartalom háttere is megváltozik 'Új termék' módban. */
    #scrollContentWidget[formMode="new_product"] {
        background-color: #fcfcf0;
        border: 1px solid #00BCD4;
    }
    /* A fő konténer stílusa, amikor a widget meglévő terméket szerkeszt (világoskék háttér). */
    #productDetailWidget[formMode="editing_existing"] {
        background-color: #fcfcf0;
        border: 1px solid #00BCD4;
    }
    /* A belső tartalom háttere is megváltozik szerkesztés módban. */
    #scrollContentWidget[formMode="editing_existing"] {
        background-color: #fcfcf0;
        border: 1px solid #00BCD4;
    }


    /* Az összes címke (pl. 'Cím:', 'Leírás:') általános stílusa. */
    QLabel {
        font-size: 10pt;
        color: #333;
    }

    /* Az összes beviteli mező (egysoros szöveg, többsoros szöveg, legördülő lista) alapértelmezett stílusa. */
    QLineEdit, QTextEdit, QComboBox {
        border: 1px solid #ccc;
        border-radius: 4px;
        padding: 5px;
        font-size: 10pt;
        background-color: #fff;
    }

    /* A beviteli mezők stílusa, amikor csak olvasható (nem szerkeszthető) módban vannak. */
    QLineEdit:read-only, QTextEdit:read-only, QComboBox:read-only {
        background-color: #f0f0f0; /* Szürke háttér jelzi az inaktivitást */
        color: #666;
    }

    /* A görgethető terület konténerének stílusa. */
    QScrollArea#productDetailScrollArea {
        border: 1px solid #BCE8F1;
        border-radius: 4px;
        background-color: transparent; /* Átlátszó, hogy a szülő háttérszíne látszódjon */
    }

    /* A 'Kategorizálás' csoportosító doboz (GroupBox) stílusa. */
    QGroupBox#categoryGroupBox {
        font-weight: bold;
        border: 1px solid #BCE8F1;
        border-radius: 4px;
        margin-top: 10px; /* Hely a címkének */
        padding-top: 15px; /* Belső margó felül */
        background-color: transparent;
    }
    /* A 'Kategorizálás' doboz címkéjének pozícionálása. */
    QGroupBox#categoryGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 5px;
        left: 10px;
    }

    QCheckBox {
        spacing: 5px;
        text-align: left;
        color: #333;
    }


    /* --- Gombok stílusai --- */
    /* Az összes nyomógomb (QPushButton) általános, alapértelmezett stílusa. */
    QPushButton {
        background-color: #4CAF50; /* Alapértelmezetten zöld (pl. a 'Mentés' gomb) */
        color: white;
        padding: 4px 15px;
        border: none;
        border-radius: 4px;
        font-size: 10pt;
    }
    /* Gomb stílusa, ha az egér fölötte van. */
    QPushButton:hover {
        background-color: #45a049;
        border: none;
        outline: none;
    }
    /* Gomb stílusa, ha a fókuszban van (itt kikapcsoljuk a keretet). */
    QPushButton:focus {
        border: none;
        outline: none;
    }
    /* Gomb stílusa, ha le van tiltva (szürke). */
    QPushButton:disabled {
        background-color: #cccccc;
        color: #666666;
    }

    /* A 'Mégse' gomb egyedi stílusa (piros). Az ID alapú selector felülírja az általános QPushButton stílust. */
    QPushButton#cancelButton {
        background-color: #f44336;
    }
    QPushButton#cancelButton:hover {
        background-color: #da190b;
    }
    
    /* A 'Kitöltés/Érvényesítés' gomb egyedi stílusa (sárga). */
    QPushButton#gsFillValidateButton {
        background-color: #F3FC81;
        color: white;
    }
    QPushButton#gsFillValidateButton:hover {
        background-color: #E0E874;
    }
    
    /* === JAVÍTÁS KEZDETE === */
    /* A 'Szerkesztés' gomb egyedi stílusa (kék). */
    QPushButton#editButton {
        background-color: #0069d9;
        color: white; /* Hozzáadva a fehér szövegszín */
    }
    QPushButton#editButton:hover {
        background-color: #0056b3;
    }
    /* === JAVÍTÁS VÉGE === */
"""