# models/gs_style_mapping.py

from typing import List, Dict, Tuple, Optional
import re
import logging

logger = logging.getLogger(__name__)

# A függvény a szöveg normalizálásához, hogy konzisztens legyen a keresés
def _normalize_text_for_style_matching(text: str) -> str:
    """
    Normalizálja a szöveget stíluskereséshez: kisbetűsít, eltávolítja az ékezeteket,
    és csak alfanumerikus karaktereket hagy meg.
    """
    if not text:
        logger.debug(f"Input text for normalization is empty.")
        return ""
    
    original_text = text # Mentjük az eredetit a debug loghoz
    text = text.lower().strip()
    logger.debug(f"Normalized step 1 (lower, strip) for '{original_text}': '{text}'")
    
    # Magyar ékezetes karakterek cseréje ASCII megfelelőkre
    text = text.replace('á', 'a')
    text = text.replace('é', 'e')
    text = text.replace('í', 'i')
    text = text.replace('ó', 'o')
    text = text.replace('ö', 'o')
    text = text.replace('ő', 'o')
    text = text.replace('ú', 'u')
    text = text.replace('ü', 'u')
    text = text.replace('ű', 'u')
    logger.debug(f"Normalized step 2 (accents removed) for '{original_text}': '{text}'")
    
    # Nem alfanumerikus karakterek eltávolítása (beleértve a szóközöket is)
    text = re.sub(r'[^a-z0-9]', '', text) 
    logger.debug(f"Normalized step 3 (non-alphanumeric removed) for '{original_text}': '{text}'")
    
    return text

# Map, ahol a kulcs a normalizált címben keresett minta, az érték pedig a pontos GS stílusnév.
# AZ ÉRTÉKEKNEK PONTOSAN AZT A SZÖVEGET KELL TARTALMAZNIUK, AMIT A GS OLDALON A STÍLUS LEGÖRDÜLŐJÉBEN KI VÁLASZTANI.
GS_STYLE_KEYWORDS_TO_OPTION_MAP: Dict[str, str] = {
    # Prioritás: Specifikus "neo-" vagy "historizáló" stílusok. Ezek a GS-en a "Neo-" opciót jelentik.
    "neobarokk": "Neo-",
    "neoreneszansz": "Neo-",
    "neorokoko": "Neo-",
    "neoklasszicista": "Neo-",
    "neoklasszikus": "Neo-",
    "neogotikus": "Neo-",
    "neoroman": "Neo-",
    "historizalo": "Neo-",
    "breton": "Neo-",

    # Egyéb stílusok (a kulcsok normalizálva, az értékek a GS-en látható opciók)
    "artdeco": "art deco",
    "artnouveau": "art nouveau",
    "barokk": "barokk",
    "bauhaus": "bauhaus",
    "biedermeier": "biedermeier",
    "chippendale": "chippendale",
    "copf": "copf",
    "eklektikus": "eklektikus",
    "empire": "empire",
    "keleti": "keleti",
    "klasszicista": "klasszicista",
    "kolonial": "koloniál",
    "lajoskorabeli": "lajos korabeli",
    "nepi": "népi",
    "onemet": "ónémet",
    "regence": "régence",
    "reneszansz": "reneszánsz",
    "retro": "retro",
    "rokoko": "rokokó",
    "szecesszio": "szecesszió",
    "thonet": "thonet",
    # "modern" a get_gs_style_from_title alapértelmezettje, nincs benne itt expliciten.
}

# A kulcsszavakat hosszuk szerint csökkenő sorrendben rendezzük,
# hogy a specifikusabb (hosszabb) kifejezések előbb kerüljenek felismerésre.
GS_STYLE_KEYWORDS_TO_OPTION_MAP_SORTED: List[Tuple[str, str]] = sorted(
    GS_STYLE_KEYWORDS_TO_OPTION_MAP.items(),
    key=lambda item: len(item[0]),
    reverse=True
)
logger.debug(f"Sorted style keywords (top 5): {GS_STYLE_KEYWORDS_TO_OPTION_MAP_SORTED[:5]}")


# ÚJ: Leképezés a GS stílus opció nevéből a GS harmadik kategóriájának (korszak) értékére.
# Az értékeknek pontosan azokat a szövegeket kell tartalmazniuk, amiket a `select#select-cat3` opciói tartalmaznak.
GS_STYLE_TO_PERIOD_MAPPING: Dict[str, str] = {
    # -1800
    "reneszánsz": "-1800",
    "barokk": "-1800",
    "régence": "-1800",
    "lajos korabeli": "-1800",
    "rokokó": "-1800",
    "chippendale": "-1800",
    "copf": "-1800",
    "klasszicista": "-1800",

    # 1800-1899
    "Empire": "1800-1899",
    "biedermeier": "1800-1899",
    "eklektikus": "1800-1899",
    "ónémet": "1800-1899",
    "thonet": "1800-1899",
    "Neo-": "1800-1899", # Historizáló/neo stílusok ehhez a korszakhoz tartoznak

    # 1900-1949
    "art nouveau": "1900-1949",
    "szecesszió": "1900-1949",
    "art deco": "1900-1949",
    "bauhaus": "1900-1949",

    # 1950-
    "modern": "1950-",
    "retro": "1950-",

    # Ismeretlen (ezekhez nincs fix időkeret)
    "keleti": "Ismeretlen",
    "koloniál": "Ismeretlen",
    "népi": "Ismeretlen",
    # Az alapértelmezett "Ismeretlen", ha nincs találat, így expliciten nem kell mindenhol szerepelnie.
}


def get_gs_style_from_title(title: str) -> str:
    """
    A termék nevéből próbálja megállapítani a megfelelő Galéria Savaria stílust.
    Prioritást élveznek a specifikusabb stílusok (hosszabb kulcsszavak).
    Ha nem talál releváns stílust, alapértelmezésben "modern"-t ad vissza.

    Args:
        title (str): A termék címe.

    Returns:
        str: A Galéria Savaria stílus opciójának pontos neve ("Neo-", "modern", "art deco", stb.).
    """
    logger.debug(f"Attempting to determine GS style for title: '{title}'")
    normalized_title = _normalize_text_for_style_matching(title)
    logger.debug(f"Normalized title for style matching: '{normalized_title}'")
    
    for keyword_normalized, gs_style_name in GS_STYLE_KEYWORDS_TO_OPTION_MAP_SORTED:
        logger.debug(f"Checking for keyword: '{keyword_normalized}' (maps to '{gs_style_name}') in normalized title ('{normalized_title}').")
        if keyword_normalized in normalized_title:
            logger.info(f"Matched keyword '{keyword_normalized}', returning target GS style: '{gs_style_name}'")
            return gs_style_name

    logger.info(f"No specific style keyword found in title ('{title}'). Returning default 'modern'.")
    return "modern"

def get_gs_period_from_style(gs_style_option_name: str) -> str:
    """
    Meghatározza a Galéria Savaria harmadik kategóriájának (korszak) értékét
    a megadott GS stílusopció neve alapján.

    Args:
        gs_style_option_name (str): A GS stílus legördülőjéből kiválasztott stílus neve
                                    (pl. "Neo-", "modern", "barokk").

    Returns:
        str: A megfelelő korszak string (pl. "-1800", "1800-1899", "1950-", "Ismeretlen").
    """
    period = GS_STYLE_TO_PERIOD_MAPPING.get(gs_style_option_name, "Ismeretlen")
    logger.debug(f"Mapped style option '{gs_style_option_name}' to period: '{period}'")
    return period