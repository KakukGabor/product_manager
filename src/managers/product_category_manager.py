import re

from typing import List, Optional, Tuple, Iterator
from config.product_categories import PRODUCT_CATEGORY_STRUCTURE
from models.product_model import MainCategory, _sanitize_for_slug
from config.special_category_keywords import SPECIAL_CATEGORY_KEYWORDS

class ProductCategoryManager:
    def __init__(self, category_data=None):
        self.categories = category_data if category_data is not None else PRODUCT_CATEGORY_STRUCTURE
        self._flattened_index = self._create_flattened_index()

    def _create_flattened_index(self):
        index = []
        for main_category, sub_categories_dict in self.categories.items():
            for sub_category, item_strings in sub_categories_dict.items():
                for item_str in item_strings:
                    index.append((main_category, sub_category, item_str))
        return index

    def _normalize_for_search(self, text: str) -> str:
        """
        Normalizálja a szöveget kereséshez: kisbetűsít, eltávolítja az ékezeteket,
        és csak alfanumerikus karaktereket, szóközöket és kötőjeleket hagy meg.
        """
        if not text:
            return ""
        text = text.lower().strip()
        text = text.replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ö', 'o').replace('ő', 'o').replace('ú', 'u').replace('ü', 'u').replace('ű', 'u')
        text = text.replace(' ', '-').replace('_', '-') # Szóközök és aláhúzások kötőjellel
        text = re.sub(r'[^\w-]', '', text) # Csak alfanumerikus és kötőjelek
        text = re.sub(r'[-]+', '-', text).strip('-') # Többszörös kötőjelek egyetlenre
        return text

    def get_main_categories(self) -> List[MainCategory]:
        main_cat_enums = []
        for cat_name_from_structure in self.categories.keys(): 
            try:
                # Value-ból konvertálunk, pl. "Antik Bútor" -> MainCategory.ANTIQUE_FURNITURE
                main_cat_enums.append(MainCategory(cat_name_from_structure)) 
            except ValueError:
                print(f"Figyelem: '{cat_name_from_structure}' fő kategória nem található a MainCategory enum VALUE-jában. Kihagyva.")
        return main_cat_enums

    def get_sub_categories_for_main(self, main_category_enum: MainCategory) -> List[str]: 
        """Visszaadja egy fő kategória alkategóriáit sztringként."""
        # JAVÍTVA: main_category_enum.value használata kulcsként
        # print(f"[ProductCategoryManager] get_sub_categories_for_main hívva: {main_category_enum.value}") # LOG
        result = list(self.categories.get(main_category_enum.value, {}).keys())
        # print(f"[ProductCategoryManager] Alkategóriák a(z) '{main_category_enum.value}' számára: {result}") # LOG
        return result

    def get_sub_categories_with_slugs_for_main(self, main_category_enum: MainCategory) -> Iterator[Tuple[str, str]]:
        """
        Visszaadja egy fő kategória alkategóriáit (név, slug) párokat tartalmazó iterátorként.
        Kifejezetten a UI elemek és adat-visszakeresések számára.
        """
        sub_category_names = self.get_sub_categories_for_main(main_category_enum)
        for name in sub_category_names:
            yield (name, _sanitize_for_slug(name))

    def get_product_types_for_sub(self, main_category_enum: MainCategory, sub_category_name: str) -> List[str]: 
        """Visszaadja egy alkategória terméktípusait sztringként."""
        # JAVÍTVA: main_category_enum.value használata kulcsként
        # print(f"[ProductCategoryManager] get_product_types_for_sub hívva: Fő: {main_category_enum.value}, Al: {sub_category_name}") # LOG
        result = self.categories.get(main_category_enum.value, {}).get(sub_category_name, [])
        # print(f"[ProductCategoryManager] Terméktípusok a(z) '{main_category_enum.value}' - '{sub_category_name}' számára: {result}") # LOG
        return result

    def search_categories_by_item_name(self, item_name): 
        normalized_item_name = self._normalize_for_search(item_name)
        matches = []

        for main_category_str, sub_category_str, item_type_str in self._flattened_index:
            score = 0
            
            normalized_main_cat = self._normalize_for_search(main_category_str)
            normalized_sub_cat = self._normalize_for_search(sub_category_str)
            normalized_item_type = self._normalize_for_search(item_type_str)

            # Prioritás: Terméktípus pontosabb egyezése a normalizált névben
            if normalized_item_type and normalized_item_type in normalized_item_name:
                score += 100
                # Ha a termék név tartalmazza a stílust is, az erősítheti a találatot, de ehhez külön stíluskereső kellene.
                # Most csak a közvetlen típusra fókuszálunk.

            # Alkategória egyezése
            if normalized_sub_cat and normalized_sub_cat != self._normalize_for_search("Nincs alkategória") and normalized_sub_cat in normalized_item_name:
                score += 40

            # Fő kategória egyezése
            if normalized_main_cat and normalized_main_cat != self._normalize_for_search("Nincs fő kategória") and normalized_main_cat in normalized_item_name:
                score += 20
            
            # Plusz pont, ha a teljes terméknév (akár rendezve) tartalmazza az összes kategória részt.
            # Ez egy bonyolultabb súlyozás, ami torzíthatja a specifikusabb találatokat.
            # Egyelőre a fenti közvetlen "in" ellenőrzések a leginkább hatékonyak.

            if score > 0:
                matches.append((score, main_category_str, sub_category_str, item_type_str))
        
        matches.sort(key=lambda x: x[0], reverse=True)
        return matches if matches else [] 

    def find_best_category_by_item_name(self, item_name) -> Optional[Tuple[str, str, str]]:
        """
        Visszaadja a legjobb találat kategória információit (MainCategory_str, SubCategory_str, ItemType_str).
        """
        normalized_item_name = self._normalize_for_search(item_name)
        
        for keyword, category_tuple in SPECIAL_CATEGORY_KEYWORDS.items():
            if keyword in normalized_item_name:
                return category_tuple

        all_matches = self.search_categories_by_item_name(item_name)
        if all_matches:
            return all_matches[0][1:] 
        return None 

    def test(self):
        print("Fő kategóriák (Enum):", self.get_main_categories())
        
        antik_butor_enum = next((mc for mc in self.get_main_categories() if mc.name == "Antik Bútor"), None)
        if antik_butor_enum:
            print("\nAntik Bútor alkategóriái:", self.get_sub_categories_for_main(antik_butor_enum))
            print("\nÜlőbútor terméktípusok:", self.get_product_types_for_sub(antik_butor_enum, "Ülőbútor"))

        print("\n--- Keresési eredmények ---")

        print("\nLegjobb kategória keresése 'Reneszánsz tálalószekrény' néven:")
        best_result = self.find_best_category_by_item_name("Reneszánsz tálalószekrény")
        print(f"Legjobb találat: {best_result}")

        print("\nLegjobb kategória keresése 'étkezőasztal' néven:")
        best_result = self.find_best_category_by_item_name("étkezőasztal")
        print(f"Legjobb találat: {best_result}")

        print("\nLegjobb kategória keresése 'asztal' néven:")
        best_result = self.find_best_category_by_item_name("asztal")
        print(f"Legjobb találat: {best_result}")

        print("\nÖsszes kategória keresése 'asztal' néven:")
        all_results = self.search_categories_by_item_name("asztal")
        if all_results:
            print(f"Találatok száma: {len(all_results)}")
            for score, main_cat, sub_cat, item_type in all_results:
                print(f"  Pontszám: {score}, Fő kategória: {main_cat}, Alkategória: {sub_cat}, Terméktípus: {item_type}")
        else:
            print("Nincs találat.")