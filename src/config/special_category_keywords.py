# config/special_category_keywords.py
from typing import Dict, Tuple

"""
Ez a szótár speciális kulcsszavakat és a hozzájuk tartozó,
kikényszerített kategória-besorolásokat tartalmazza.

A ProductCategoryManager először ebben a szótárban keres egyezést.
Ha talál, azonnal azt a kategóriát adja vissza, és nem futtatja le
a pontozásos algoritmust.

FONTOS: A kulcsoknak normalizált stringeknek kell lenniük 
(kisbetűs, ékezet nélküli, kötőjeles), hogy a keresés megbízható legyen.
Például a "Dagobert szék" kifejezéshez a "dagobert-szek" kulcsot kell használni.
"""

SPECIAL_CATEGORY_KEYWORDS: Dict[str, Tuple[str, str, str]] = {

    "talalo-szekreny": ("Antik Bútor", "Szekrény", "Tálalószekrény"),
    "kabinet-szekreny": ("Antik Bútor", "Szekrény", "Kabinetszekrény"),
    "konyvesszekreny": ("Antik Bútor", "Szekrény", "Könyvszekrény"),
    "konyves-szekreny": ("Antik Bútor", "Szekrény", "Könyvszekrény"),

    "etkezo-asztal": ("Antik Bútor", "Asztal", "Étkezőasztal"),
    "dohanyzo-asztal": ("Antik Bútor", "Asztal", "Társalgóasztal"),
    "dohanyzoasztal": ("Antik Bútor", "Asztal", "Társalgóasztal"),
    "teazo-asztal": ("Antik Bútor", "Asztal", "Társalgóasztal"),
    "teazoasztal": ("Antik Bútor", "Asztal", "Társalgóasztal"),
    "tarsalgo-asztal": ("Antik Bútor", "Asztal", "Társalgóasztal"),
    "kisasztal": ("Antik Bútor", "Asztal", "Társalgóasztal"),
    "elokeszito-asztal": ("Antik Bútor", "Asztal", "Előkészítőasztal"),
    "desszertasztal": ("Antik Bútor", "Asztal", "Tálalóasztal"),
    "desszert-asztal": ("Antik Bútor", "Asztal", "Tálalóasztal"),

    "neoreneszansz-szekek": ("Antik Bútor", "Ülőbútor", "Étkezőszék"),
    "neobarokk-szekek": ("Antik Bútor", "Ülőbútor", "Étkezőszék"),

    "blackamoor-lampa": ("Lakáskiegészítő", "Világítás", "Állólámpa"),
}