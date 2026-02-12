# config/jf_category_mapping.py

from typing import Dict, Tuple, Optional

# A Jófogás kategóriáinak leképezése a belső rendszerünkhöz.
JF_CATEGORY_MAPPING: Dict[Tuple[str, str, str], Tuple[str, str, Optional[str]]] = {
    # --- Antik Bútor Kategóriák -> Otthon, háztartás -> Bútor ---
    ("Antik Bútor", "Ülőbútor", "Étkezőszék"):         ("Otthon, háztartás", "Bútor", "Asztalok, székek"),
    ("Antik Bútor", "Ülőbútor", "Karosszék"):          ("Otthon, háztartás", "Bútor", "Egyéb"),
    ("Antik Bútor", "Ülőbútor", "Hall szék"):          ("Otthon, háztartás", "Bútor", "Egyéb"),
    ("Antik Bútor", "Ülőbútor", "Trónszék"):           ("Otthon, háztartás", "Bútor", "Egyéb"),
    ("Antik Bútor", "Ülőbútor", "Dagobert szék"):      ("Otthon, háztartás", "Bútor", "Egyéb"),
    ("Antik Bútor", "Ülőbútor", "Kanapé"):             ("Otthon, háztartás", "Bútor", "Fotelek, kanapék, ülőgarnitúrák"),
    ("Antik Bútor", "Ülőbútor", "Fekvőkanapé"):        ("Otthon, háztartás", "Bútor", "Egyéb"),
    # === JAVÍTÁS: "Pad" áthelyezve az "Egyéb" kategóriába ===
    ("Antik Bútor", "Ülőbútor", "Pad"):                ("Otthon, háztartás", "Bútor", "Egyéb"),
    ("Antik Bútor", "Ülőbútor", "Fotel"):              ("Otthon, háztartás", "Bútor", "Fotelek, kanapék, ülőgarnitúrák"),
    ("Antik Bútor", "Ülőbútor", "Egyéb ülőbútor"):     ("Otthon, háztartás", "Bútor", "Egyéb"),

    ("Antik Bútor", "Asztal", "Étkezőasztal"):          ("Otthon, háztartás", "Bútor", "Asztalok, székek"),
    ("Antik Bútor", "Asztal", "Íróasztal"):             ("Otthon, háztartás", "Bútor", "Asztalok, székek"),
    ("Antik Bútor", "Asztal", "Konzolasztal"):          ("Otthon, háztartás", "Bútor", "Egyéb"),
    ("Antik Bútor", "Asztal", "Társalgóasztal"):        ("Otthon, háztartás", "Bútor", "Egyéb"),
    ("Antik Bútor", "Asztal", "Egyéb asztal"):          ("Otthon, háztartás", "Bútor", "Egyéb"),

    ("Antik Bútor", "Szekrény", "Tálalószekrény"):      ("Otthon, háztartás", "Bútor", "Szekrények, szekrénysorok, polcok"),
    ("Antik Bútor", "Szekrény", "Pohárszék"):           ("Otthon, háztartás", "Bútor", "Szekrények, szekrénysorok, polcok"),
    ("Antik Bútor", "Szekrény", "Kabinetszekrény"):     ("Otthon, háztartás", "Bútor", "Szekrények, szekrénysorok, polcok"),
    ("Antik Bútor", "Szekrény", "Ruhásszekrény"):       ("Otthon, háztartás", "Bútor", "Szekrények, szekrénysorok, polcok"),
    ("Antik Bútor", "Szekrény", "Könyvszekrény"):       ("Otthon, háztartás", "Bútor", "Szekrények, szekrénysorok, polcok"),
    ("Antik Bútor", "Szekrény", "Fiókos szekrény"):     ("Otthon, háztartás", "Bútor", "Szekrények, szekrénysorok, polcok"),
    ("Antik Bútor", "Szekrény", "Éjjeliszekrény"):      ("Otthon, háztartás", "Bútor", "Szekrények, szekrénysorok, polcok"),
    ("Antik Bútor", "Szekrény", "Bárszekrény"):         ("Otthon, háztartás", "Bútor", "Szekrények, szekrénysorok, polcok"),
    ("Antik Bútor", "Szekrény", "Magas szekrény"):      ("Otthon, háztartás", "Bútor", "Szekrények, szekrénysorok, polcok"),
    ("Antik Bútor", "Szekrény", "Vitrin"):              ("Otthon, háztartás", "Bútor", "Szekrények, szekrénysorok, polcok"),
    ("Antik Bútor", "Szekrény", "Komód"):               ("Otthon, háztartás", "Bútor", "Szekrények, szekrénysorok, polcok"),
    ("Antik Bútor", "Szekrény", "Szekreter"):           ("Otthon, háztartás", "Bútor", "Szekrények, szekrénysorok, polcok"),
    ("Antik Bútor", "Szekrény", "Egyéb szekrény"):      ("Otthon, háztartás", "Bútor", "Egyéb"),

    ("Antik Bútor", "Egyéb Bútor", "Ágy"):              ("Otthon, háztartás", "Bútor", "Ágyak, matracok"),
    ("Antik Bútor", "Egyéb Bútor", "Láda"):             ("Otthon, háztartás", "Bútor", "Egyéb"),
    ("Antik Bútor", "Egyéb Bútor", "Fogas"):            ("Otthon, háztartás", "Bútor", "Egyéb"),
    
    ("Antik Bútor", "Garnitúra", "Étkező"):             ("Otthon, háztartás", "Bútor", "Asztalok, székek"),
    ("Antik Bútor", "Garnitúra", "Ülő"):                ("Otthon, háztartás", "Bútor", "Fotelek, kanapék, ülőgarnitúrák"),
    ("Antik Bútor", "Garnitúra", "Hálószoba"):          ("Otthon, háztartás", "Bútor", "Egyéb"),

    # --- Lakáskiegészítő Kategóriák ---
    ("Lakáskiegészítő", "Műtárgy", "Festmény"):             ("Otthon, háztartás", "Lakáskiegészítők", "Dísztárgy, kép, festmény"),
    ("Lakáskiegészítő", "Műtárgy", "Szobor"):               ("Otthon, háztartás", "Lakáskiegészítők", "Dísztárgy, kép, festmény"),
    ("Lakáskiegészítő", "Műtárgy", "Porcelán és kerámia"): ("Otthon, háztartás", "Lakáskiegészítők", "Dísztárgy, kép, festmény"),
    ("Lakáskiegészítő", "Műtárgy", "Üvegtárgy"):           ("Otthon, háztartás", "Lakáskiegészítők", "Dísztárgy, kép, festmény"),
    ("Lakáskiegészítő", "Műtárgy", "Váza"):                 ("Otthon, háztartás", "Lakáskiegészítők", "Dísztárgy, kép, festmény"),
    ("Lakáskiegészítő", "Műtárgy", "Posztamens"):           ("Otthon, háztartás", "Lakáskiegészítők", "Egyéb"),

    ("Lakáskiegészítő", "Kép és Fali Dísz", "Grafika és nyomat"): ("Otthon, háztartás", "Lakáskiegészítők", "Dísztárgy, kép, festmény"),
    ("Lakáskiegészítő", "Kép és Fali Dísz", "Képkeret"):        ("Otthon, háztartás", "Lakáskiegészítők", "Dísztárgy, kép, festmény"),
    # === JAVÍTÁS: "Gobelin" áthelyezve a helyes kategóriába ===
    ("Lakáskiegészítő", "Kép és Fali Dísz", "Gobelin"):         ("Otthon, háztartás", "Lakáskiegészítők", "Dísztárgy, kép, festmény"),

    ("Lakáskiegészítő", "Óra", "Falióra"):                  ("Otthon, háztartás", "Lakáskiegészítők", "Egyéb"),
    ("Lakáskiegészítő", "Óra", "Kandallóóra"):              ("Otthon, háztartás", "Lakáskiegészítők", "Egyéb"),
    ("Lakáskiegészítő", "Óra", "Asztali óra"):              ("Otthon, háztartás", "Lakáskiegészítők", "Egyéb"),
    ("Lakáskiegészítő", "Óra", "Állóóra"):                  ("Otthon, háztartás", "Lakáskiegészítők", "Egyéb"),

    ("Lakáskiegészítő", "Tükör", "Fali tükör"):             ("Otthon, háztartás", "Lakáskiegészítők", "Dísztárgy, kép, festmény"),
    ("Lakáskiegészítő", "Tükör", "Asztali tükör"):          ("Otthon, háztartás", "Lakáskiegészítők", "Dísztárgy, kép, festmény"),
    ("Lakáskiegészítő", "Tükör", "Álló tükör"):             ("Otthon, háztartás", "Lakáskiegészítők", "Dísztárgy, kép, festmény"),

    ("Lakáskiegészítő", "Textília", "Szőnyeg"):             ("Otthon, háztartás", "Lakáskiegészítők", "Szőnyeg"),
    ("Lakáskiegészítő", "Textília", "Díszpárna"):           ("Otthon, háztartás", "Lakáskiegészítők", "Lakástextil"),
    ("Lakáskiegészítő", "Textília", "Terítő"):              ("Otthon, háztartás", "Lakáskiegészítők", "Lakástextil"),
    ("Lakáskiegészítő", "Textília", "Függöny"):             ("Otthon, háztartás", "Lakáskiegészítők", "Függöny"),
    
    ("Lakáskiegészítő", "Egyéb kiegészítő", "Kandalló szett"): ("Otthon, háztartás", "Lakáskiegészítők", "Egyéb"),
    ("Lakáskiegészítő", "Egyéb kiegészítő", "Könyvtámasz"):   ("Otthon, háztartás", "Lakáskiegészítők", "Egyéb"),

    # --- Világítás Kategóriák -> Otthon, háztartás -> Világítás ---
    ("Lakáskiegészítő", "Világítás", "Csillár"):            ("Otthon, háztartás", "Világítás", "Mennyezeti világítás"),
    ("Lakáskiegészítő", "Világítás", "Fali lámpa"):         ("Otthon, háztartás", "Világítás", "Falilámpa"),
    ("Lakáskiegészítő", "Világítás", "Asztali lámpa"):      ("Otthon, háztartás", "Világítás", "Asztali lámpa"),
    ("Lakáskiegészítő", "Világítás", "Állólámpa"):          ("Otthon, háztartás", "Világítás", "Állólámpa"),
    ("Lakáskiegészítő", "Világítás", "Gyertyatartó"):       ("Otthon, háztartás", "Világítás", "Egyéb"),
}