# config/jf_attribute_mapping.py
from typing import Dict, List, Union, Tuple, Any

# "Állapot" listák definiálása
FULL_CONDITION_LIST = [
    "Új", "Újszerű", "Alig használt", "Használt", "Számlával", 
    "Adás vételivel", "Hibátlan", "Korának megfelelő", "Restaurált", "Sérült"
]
SHORT_CONDITION_LIST = ["Új", "Újszerű", "Alig használt", "Használt", "Számlával"]
SZIN_LISTA = ['Barna', 'Natúr', 'Fehér', 'Fekete', 'Szürke', 'Színes', 'Egyéb']

# A "Típus" legördülő menük opciói
FOTELEK_TIPUS = [
    'kinyitható kanapé', 'kárpitozott kanapé', 'bőr-, műbőr kanapé', 
    'sarokülőgarnitúra', 'fotel', 'fekvőfotel', 'lábtartó, puff', 'ülőgarnitúra'
]
ASZTALOK_TIPUS = [
    'íróasztal, számítógépasztal', 'dohányzóasztal', 'étkezőasztal', 
    'étkező garnitúra', 'sarokétkező', 'bárszék, ülőke, kisszék', 
    'báraasztal', 'étkezőszék', 'forgószék'
]
SZEKRENYEK_TIPUS = [
    'nappali szekrénysor', 'gardrób szekrény', 'polc, polc rendszer', 
    'antik bútor', 'tálalószekrény', 'éjjeliszekrény', 'egyéb hálószobabútor', 
    'komód', 'cipősszekrény', 'TV állvány', 'gyerekbútor', 'vitrin', 'előszobaszekrény'
]
FURDOSZOBA_TIPUS = ['fürdőszobaszekrény', 'zuhanyfülke', 'piperepolc', 'egyéb']
LAKASTEXTIL_TIPUS = [
    'törölközők', 'terítő', 'asztali futó', 'falvédő', 
    'párnahuzat, egyéb huzatok', 'bútorszövet', 'egyéb textilek'
]
DISZTARGY_TIPUS = ['gobelin kép', 'váza', 'tükör', 'képkeret', 'szobor', 'kép', 'festmény', 'dísztárgy']
FUGGONY_TIPUS = ['sötétítő, árnyékoló', 'csipke', 'egyéb']
SZONYEG_TIPUS = [
    'gyerek szőnyeg', 'futószőnyeg', 'rongyszőnyeg', 'perzsa szőnyeg', 
    'kerek, ovális szőnyegek', 'fürdőszoba szőnyeg', 'egyéb'
]
AGYNEMU_TIPUS = ['takaró', 'párna', 'lepedő', 'szettek']
ASZTALI_LAMPA_TIPUS = ['üveg', 'textil', 'kerámia', 'kristály', 'egyéb', 'égők, izzók']
MENNYEZETI_VILAGITAS_TIPUS = ['mennyezeti lámpák', 'spot égők', 'égők, izzók']
FALILAMPA_TIPUS = ['modern', 'klasszikus', 'égők, izzók']
KULTERI_VILAGITAS_TIPUS = [
    'reflektor', 'kültéri állólámpa', 'beépíthető lámpa', 'fali lámpa', 
    'kandeláber', 'mozgásérzékelős', 'solar', 'talajba építhető', 'égők, izzók', 
    'viharlámpa, fáklya'
]

# Fő leképező szótár
JF_ATTRIBUTE_MAPPING: Dict[Tuple[str, str], Dict[str, Union[List[str], Dict[str, Any]]]] = {
    # Bútor
    ("Bútor", "Fotelek, kanapék, ülőgarnitúrák"): {
        "Állapot": FULL_CONDITION_LIST,
        "Típus": {
            "special_handler": "priority_rules",
            "rules": [
                { "type": "exact_product_type", "if_product_type": "Fotel", "select": "fotel" },
                { "type": "exact_product_type", "if_product_type": "Ülő", "select": "ülőgarnitúra" },
                { "type": "title_keyword", "keywords": ["bőr ülőgarnitúra", "bőrkanapé"], "select": "bőr-, műbőr kanapé" },
                { "type": "title_keyword", "keywords": ["kinyitható"], "select": "kinyitható kanapé" }
            ],
            "default": "kárpitozott kanapé",
            "options": FOTELEK_TIPUS
        }
    },
    ("Bútor", "Asztalok, székek"): {
        "Állapot": FULL_CONDITION_LIST, 
        "Típus": {
            "special_handler": "priority_rules",
            "rules": [
                { "type": "exact_product_type", "if_product_type": "Étkező", "select": "étkező garnitúra" }
            ],
            "default_handler": "find_shortest_match",
            "options": ASZTALOK_TIPUS
        }
    },
    ("Bútor", "Szekrények, szekrénysorok, polcok"): { "Állapot": FULL_CONDITION_LIST, "Típus": SZEKRENYEK_TIPUS },
    ("Bútor", "Ágyak, matracok"): { "Állapot": FULL_CONDITION_LIST, "Méret": [], "Márka": [] },
    ("Bútor", "Konyhabútor"): { "Állapot": FULL_CONDITION_LIST, "Típus": {"buttons": ["konyhabútor szett", "konyhabútor elem"]} },
    ("Bútor", "Fürdőszoba bútor"): { "Állapot": FULL_CONDITION_LIST, "Típus": FURDOSZOBA_TIPUS },

    # Lakáskiegészítők
    ("Lakáskiegészítők", "Lakástextil"): { "Állapot": SHORT_CONDITION_LIST, "Típus": LAKASTEXTIL_TIPUS },
    ("Lakáskiegészítők", "Dísztárgy, kép, festmény"): {
        "Állapot": FULL_CONDITION_LIST,
        "Típus": {
            "special_handler": "priority_rules",
            "rules": [
                { "type": "exact_product_type", "if_product_type": "Gobelin", "select": "gobelin kép" }
            ],
            "default_handler": "find_shortest_match_reverse",
            "options": DISZTARGY_TIPUS
        }
    },
    ("Lakáskiegészítők", "Függöny"): { "Állapot": FULL_CONDITION_LIST, "Méret": {"buttons": ["rövid", "hosszú"]}, "Típus": FUGGONY_TIPUS },
    ("Lakáskiegészítők", "Szőnyeg"): { "Állapot": SHORT_CONDITION_LIST, "Típus": SZONYEG_TIPUS },
    ("Lakáskiegészítők", "Ágynemű"): { "Állapot": SHORT_CONDITION_LIST, "Méret": {"buttons": ["gyerek", "felnőtt"]}, "Típus": AGYNEMU_TIPUS },

    # Világítás
    ("Világítás", "Állólámpa"): { "Állapot": FULL_CONDITION_LIST, "Típus": {"default": "olvasókarral", "options": {"buttons": ["olvasókarral", "égők, izzók"]}} },
    ("Világítás", "Asztali lámpa"): { "Állapot": FULL_CONDITION_LIST, "Típus": {"default": "egyéb", "options": ASZTALI_LAMPA_TIPUS} },
    ("Világítás", "Mennyezeti világítás"): { "Állapot": FULL_CONDITION_LIST, "Típus": {"default": "mennyezeti lámpák", "options": MENNYEZETI_VILAGITAS_TIPUS} },
    ("Világítás", "Falilámpa"): { "Állapot": FULL_CONDITION_LIST, "Típus": {"default": "klasszikus", "options": FALILAMPA_TIPUS} },
    ("Világítás", "Kültéri világítás"): { "Állapot": FULL_CONDITION_LIST, "Típus": KULTERI_VILAGITAS_TIPUS },
}