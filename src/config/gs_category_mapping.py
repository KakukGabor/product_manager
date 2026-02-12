# models/gs_category_mapping.py

from typing import Dict, Tuple, Optional

# Megjegyzés: Ezek a kulcsok az app belső kategóriáinak
#             (Fő kategória, Alkategória, Terméktípus) string reprezentációi.
#             A MainCategory Enum display_name-je, az alkategória és terméktípus pedig
#             a PRODUCT_CATEGORY_STRUCTURE-ben szereplő nevük.

# AZ ÉRTÉKEK MOST MÁR PONTOSAN AZT A SZÖVEGET TARTALMAZZÁK, AMIT A GS OLDALON LÁTUNK,
# BELEÉRTVE A ' >' KARAKTERT IS, AHOL EZ SZÜKSÉGES, AZ ÖN ÁLTAL MEGADOTT LISTÁK ALAPJÁN.

GS_CATEGORY_MAPPING: Dict[Tuple[str, str, str], Tuple[Optional[str], Optional[str]]] = {
    # --- Antik Bútor Kategóriák ---
    # Fő kategória: "Antik Bútor" -> GS Első szint: "Bútor >" (mivel van második szint)
    ("Antik Bútor", "Ülőbútor", "Étkezőszék"):          ("Bútor >", "Szék >"), 
    ("Antik Bútor", "Ülőbútor", "Karosszék"):          ("Bútor >", "Szék >"), 
    ("Antik Bútor", "Ülőbútor", "Hall szék"):          ("Bútor >", "Szék >"), 
    ("Antik Bútor", "Ülőbútor", "Trónszék"):           ("Bútor >", "Szék >"), 
    ("Antik Bútor", "Ülőbútor", "Dagobert szék"):      ("Bútor >", "Szék >"), 
    ("Antik Bútor", "Ülőbútor", "Kanapé"):             ("Bútor >", "Kanapé, szófa >"), 
    ("Antik Bútor", "Ülőbútor", "Fekvőkanapé"):        ("Bútor >", "Kanapé, szófa >"), 
    ("Antik Bútor", "Ülőbútor", "Pad"):                ("Bútor >", "Szék >"), 
    ("Antik Bútor", "Ülőbútor", "Fotel"):              ("Bútor >", "Fotel >"), 
    ("Antik Bútor", "Ülőbútor", "Egyéb ülőbútor"):     ("Bútor >", "Egyéb bútor >"), 

    ("Antik Bútor", "Asztal", "Étkezőasztal"):          ("Bútor >", "Asztal >"), 
    ("Antik Bútor", "Asztal", "Íróasztal"):             ("Bútor >", "Íróasztal >"), 
    ("Antik Bútor", "Asztal", "Konzolasztal"):          ("Bútor >", "Asztal >"), 
    ("Antik Bútor", "Asztal", "Társalgóasztal"):        ("Bútor >", "Asztal >"), 
    ("Antik Bútor", "Asztal", "Előkészítőasztal"):      ("Bútor >", "Asztal >"), 
    ("Antik Bútor", "Asztal", "Tálalóasztal"):          ("Bútor >", "Tálalóasztal >"), 
    ("Antik Bútor", "Asztal", "Fésülködőasztal"):       ("Bútor >", "Fésülködő asztal >"), 
    ("Antik Bútor", "Asztal", "Loo asztal"):            ("Bútor >", "Asztal >"), 
    ("Antik Bútor", "Asztal", "Pedestal asztal"):       ("Bútor >", "Posztamens, szobortartó >"), 
    ("Antik Bútor", "Asztal", "Egyéb asztal"):          ("Bútor >", "Egyéb bútor >"), 

    ("Antik Bútor", "Szekrény", "Tálalószekrény"):      ("Bútor >", "Szekrény >"), 
    ("Antik Bútor", "Szekrény", "Pohárszék"):           ("Bútor >", "Szekrény >"), 
    ("Antik Bútor", "Szekrény", "Kabinetszekrény"):     ("Bútor >", "Szekrény >"), 
    ("Antik Bútor", "Szekrény", "Ruhásszekrény"):       ("Bútor >", "Szekrény >"), 
    ("Antik Bútor", "Szekrény", "Könyvszekrény"):       ("Bútor >", "Szekrény >"), 
    ("Antik Bútor", "Szekrény", "Vitrin"):              ("Bútor >", "Vitrin >"), 
    ("Antik Bútor", "Szekrény", "Fiókos szekrény"):     ("Bútor >", "Szekrény >"), 
    ("Antik Bútor", "Szekrény", "Szekreter"):           ("Bútor >", "Szekreter >"), 
    ("Antik Bútor", "Szekrény", "Komód"):               ("Bútor >", "Komód >"), 
    ("Antik Bútor", "Szekrény", "Éjjeliszekrény"):      ("Bútor >", "Éjjeli szekrény >"), 
    ("Antik Bútor", "Szekrény", "Bárszekrény"):         ("Bútor >", "Szekrény >"), 
    ("Antik Bútor", "Szekrény", "Magas szekrény"):      ("Bútor >", "Szekrény >"), 
    ("Antik Bútor", "Szekrény", "Egyéb szekrény"):      ("Bútor >", "Egyéb bútor >"), 

    ("Antik Bútor", "Egyéb Bútor", "Ágy"):              ("Bútor >", "Ágy >"), 
    ("Antik Bútor", "Egyéb Bútor", "Falburkolat"):      ("Bútor >", "Egyéb bútor >"), 
    ("Antik Bútor", "Egyéb Bútor", "Láda"):             ("Bútor >", "Láda >"), 
    ("Antik Bútor", "Egyéb Bútor", "Fogas"):            ("Bútor >", "Fogas, akasztó >"), 
    ("Antik Bútor", "Egyéb Bútor", "Mosdóállvány"):     ("Bútor >", "Egyéb bútor >"), 
    ("Antik Bútor", "Egyéb Bútor", "Gyermekbútor"):    ("Bútor >", "Egyéb bútor >"), 

    ("Antik Bútor", "Garnitúra", "Étkező"): ("Bútor >", "Komplett garnitúra >"), 
    ("Antik Bútor", "Garnitúra", "Hálószoba"): ("Bútor >", "Komplett garnitúra >"), 
    ("Antik Bútor", "Garnitúra", "Dolgozószoba"): ("Bútor >", "Komplett garnitúra >"), 
    ("Antik Bútor", "Garnitúra", "Ülő"):     ("Bútor >", "Ülőgarnitúra >"), 
    ("Antik Bútor", "Garnitúra", "Előszoba"): ("Bútor >", "Komplett garnitúra >"), 

    # --- Lakáskiegészítő Kategóriák ---
    # Műtárgy
    ("Lakáskiegészítő", "Műtárgy", "Festmény"):             ("Festmény >", "Egyéb >"), 
    ("Lakáskiegészítő", "Műtárgy", "Szobor"):               ("Szobor >", "Egyéb szobor >"), 
    ("Lakáskiegészítő", "Műtárgy", "Porcelán és kerámia"): ("Kerámia >", "Egyéb >"), 
    ("Lakáskiegészítő", "Műtárgy", "Üvegtárgy"):           ("Üveg >", "Egyéb >"), 
    ("Lakáskiegészítő", "Műtárgy", "Váza"):                 ("Kerámia >", "Váza"), 
    ("Lakáskiegészítő", "Műtárgy", "Posztamens"):           ("Bútor >", "Posztamens, szobortartó >"), 

    # Kép és Fali Dísz
    ("Lakáskiegészítő", "Kép és Fali Dísz", "Grafika és nyomat"): ("Kép, grafika >", "Grafika"), 
    ("Lakáskiegészítő", "Kép és Fali Dísz", "Képkeret"):        ("Képkeret", None), 
    ("Lakáskiegészítő", "Kép és Fali Dísz", "Gobelin"):         ("Szőnyeg, Textil", "Gobelin"), 

    # Óra
    ("Lakáskiegészítő", "Óra", "Falióra"):                  ("Óra >", "Falióra"), 
    ("Lakáskiegészítő", "Óra", "Kandallóóra"):              ("Óra >", "Kandalló óra"), 
    ("Lakáskiegészítő", "Óra", "Asztali óra"):              ("Óra >", "Asztali óra"), 
    ("Lakáskiegészítő", "Óra", "Állóóra"):                  ("Óra >", "Állóóra"), 

    # Világítás (a listában itt nincsenek > karakterek az alkategóriák után)
    ("Lakáskiegészítő", "Világítás", "Csillár"):            ("Lámpa, csillár >", "Csillár"),
    ("Lakáskiegészítő", "Világítás", "Fali lámpa"):         ("Lámpa, csillár >", "Fali lámpa"),
    ("Lakáskiegészítő", "Világítás", "Asztali lámpa"):      ("Lámpa, csillár >", "Asztali lámpa"),
    ("Lakáskiegészítő", "Világítás", "Állólámpa"):          ("Lámpa, csillár >", "Állólámpa"),
    ("Lakáskiegészítő", "Világítás", "Gyertyatartó"):       ("Lámpa, csillár >", "Egyéb lámpa"),

    # Tükör (ez kivétel mert még 2. kategóriája sincs, ennek az egynek a főkategóriában nincs > a végén)
    ("Lakáskiegészítő", "Tükör", "Fali tükör"):             ("Tükör", None),
    ("Lakáskiegészítő", "Tükör", "Asztali tükör"):          ("Tükör", None),
    ("Lakáskiegészítő", "Tükör", "Álló tükör"):             ("Tükör", None),

    # Textília (a listában a Szőnyeg az egyetlen, aminek van >-ja)
    ("Lakáskiegészítő", "Textília", "Szőnyeg"):             ("Szőnyeg, Textil", "Szőnyeg >"),
    ("Lakáskiegészítő", "Textília", "Díszpárna"):           ("Szőnyeg, Textil", "Díszpárna"),
    ("Lakáskiegészítő", "Textília", "Terítő"):              ("Szőnyeg, Textil", "Terítő"),
    ("Lakáskiegészítő", "Textília", "Függöny"):             ("Szőnyeg, Textil", "Függöny és tartozékok"),

    # Egyéb kiegészítő
    ("Lakáskiegészítő", "Egyéb kiegészítő", "Kandalló szett"): ("Fémmunka >", "Egyéb >"),
    ("Lakáskiegészítő", "Egyéb kiegészítő", "Könyvtámasz"):   ("Otthon, háztartás kellékei >", "Egyéb >"),
    ("Lakáskiegészítő", "Egyéb kiegészítő", "Pipaállvány és szivartartó"): ("Gyűjtemény >", "Egyéb >"),
    ("Lakáskiegészítő", "Egyéb kiegészítő", "Levélnehezék"):  ("Otthon, háztartás kellékei >", "Egyéb >"),
    ("Lakáskiegészítő", "Egyéb kiegészítő", "Papírkosár"):    ("Otthon, háztartás kellékei >", "Egyéb >"),
    ("Lakáskiegészítő", "Egyéb kiegészítő", "Sétapálcatartó és esernyőtartó"): ("Bútor >", "Esernyőtartó >"),
    ("Lakáskiegészítő", "Egyéb kiegészítő", "Parfümös üveg és kozmetikai tartó"): ("Üveg >", "Egyéb >"),
}