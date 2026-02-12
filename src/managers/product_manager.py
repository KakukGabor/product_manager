# src/managers/product_manager.py
import json
import logging
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import re
import os
import collections
import shutil
from config.app_folders import FOLDER_APP_DATA, FOLDER_RAW, FOLDER_RAW_GS

from PySide6.QtCore import QObject, Signal, Slot

from models.product_model import Product, MainCategory, _sanitize_for_slug
from managers.settings_manager import SettingsManager
from managers.product_category_manager import ProductCategoryManager

logger = logging.getLogger(__name__)


class ProductManager(QObject):
    productsLoaded = Signal(list, bool, str)
    productAdded = Signal(Product, bool, str)
    productUpdated = Signal(Product, bool, str)
    productDeleted = Signal(str, bool, str)
    categoryChanged = Signal(str, str, str, bool, str)
    errorOccurred = Signal(str, str)
    productsBatchProcessed = Signal(list, bool, str)
    productSold = Signal(str, bool, str)
    productNeedsUploadStateChanged = Signal(str, bool)
    gsProcessingReportReady = Signal(str)
    jfProcessingReportReady = Signal(str)
    reportGenerated = Signal(str)
    productLoadingErrors = Signal(list)


    def __init__(self, app_root_dir: str, settings_manager: SettingsManager, category_manager: ProductCategoryManager, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.app_root_dir = Path(app_root_dir).resolve()
        self.settings_manager = settings_manager
        self.category_manager = category_manager

        self._products: Dict[str, Product] = {}
        self._filtered_products: List[Product] = []
        self._current_filters: Dict[str, Any] = {}
        

        self._base_product_dir: Path = self.app_root_dir / "app_data_storage" / "processed" / "product_library"

        if not self._base_product_dir.exists():
            try:
                self._base_product_dir.mkdir(parents=True, exist_ok=True)
                self._log(logging.INFO, f"Alap termékmappa létrehozva: {self._base_product_dir.absolute()}")
            except OSError as e:
                self._log(logging.CRITICAL, f"HIBA: Nem sikerült létrehozni az alap termékmappát: {self._base_product_dir.absolute()}. Hiba: {e}", exc_info=True)
                self.errorOccurred.emit("Fájlrendszer hiba", f"Nem sikerült létrehozni az alap termékmappát: {self._base_product_dir.absolute()}. Hiba: {e}")


    def _log(self, level: int, message: str, *args, **kwargs):
        """Segédmetódus a naplózáshoz a ProductManager kontextusában."""
        logger.log(level, f"[ProductManager] {message}", *args, **kwargs)


    # --- Segéd metódusok útvonalakhoz ---

    def _get_product_path_from_product_object(self, product: Product) -> Path:
        main_cat_slug = _sanitize_for_slug(product.main_category.to_slug())
        sub_cat_slug = _sanitize_for_slug(product.sub_category_slug) if product.sub_category_slug else _sanitize_for_slug("Nincs alkategória")
        product_type_slug = _sanitize_for_slug(product.product_type_slug) if product.product_type_slug else _sanitize_for_slug("Nincs terméktípus")
        product_id_slug = _sanitize_for_slug(product.id)

        if not main_cat_slug or not product_id_slug:
            raise ValueError(f"Hiányzó fő kategória slug ('{main_cat_slug}') vagy termék ID ('{product_id_slug}') a termék útvonalának létrehozásához. Termék ID: {product.id}")

        path_components = [main_cat_slug]
        if sub_cat_slug != _sanitize_for_slug("Nincs alkategória"):
            path_components.append(sub_cat_slug)
        if product_type_slug != _sanitize_for_slug("Nincs terméktípus"):
            path_components.append(product_type_slug)
        path_components.append(f"product_{product_id_slug}")

        return self._base_product_dir.joinpath(*path_components)


    def _get_product_path_from_slugs(self, product_id: str, main_cat_slug: str, sub_cat_slug: Optional[str], product_type_slug: Optional[str]) -> Path:
        main_cat_slug = _sanitize_for_slug(main_cat_slug)
        sub_cat_slug = _sanitize_for_slug(sub_cat_slug) if sub_cat_slug else _sanitize_for_slug("Nincs alkategória")
        product_type_slug = _sanitize_for_slug(product_type_slug) if product_type_slug else _sanitize_for_slug("Nincs terméktípus")
        product_id_slug = _sanitize_for_slug(product_id)

        if not main_cat_slug or not product_id_slug:
            raise ValueError(f"Hiányzó fő kategória slug ('{main_cat_slug}') vagy termék ID ('{product_id_slug}') az útvonal létrehozásához. Termék ID: {product_id}")

        path_components = [main_cat_slug]
        if sub_cat_slug != _sanitize_for_slug("Nincs alkategória"):
            path_components.append(sub_cat_slug)
        if product_type_slug != _sanitize_for_slug("Nincs terméktípus"):
            path_components.append(product_type_slug)
        path_components.append(f"product_{product_id_slug}")

        return self._base_product_dir.joinpath(*path_components)


    def _get_product_json_path(self, product_base_dir: Path) -> Path:
        product_id_from_dir_name = product_base_dir.name
        product_id_clean = product_id_from_dir_name.replace("product_", "")
        return product_base_dir / f"{product_id_clean}.json"


    # --- Termékek betöltése ---

    @Slot()
    def load_all_products_sync(self):
        loaded_count = 0
        self._products.clear()
        loading_errors = []

        try:
            if not self._base_product_dir.exists():
                message = f"Hiba: A termék alapkönyvtár nem létezik: {self._base_product_dir.absolute()}"
                self._log(logging.WARNING, message)
                self.productsLoaded.emit([], False, message)
                return

            for json_file_path in self._base_product_dir.rglob('*.json'):
                file_name_stem = json_file_path.stem
                parent_dir_name = json_file_path.parent.name

                if not parent_dir_name.startswith("product_"):
                    self._log(logging.WARNING, f"Kihagyott fájl: A szülőkönyvtár neve nem 'product_' előtaggal kezdődik: {json_file_path.absolute()}")
                    continue

                expected_id_from_parent = parent_dir_name.replace("product_", "")

                if file_name_stem == expected_id_from_parent:
                    try:
                        with open(json_file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        product = Product.from_dict(data)
                        
                        self._products[product.id] = product
                        loaded_count += 1
                        

                    except (json.JSONDecodeError, ValueError) as e:
                        error_msg = f"Hiba a(z) '{json_file_path.name}' fájl feldolgozásakor: {e}"
                        self._log(logging.ERROR, error_msg, exc_info=True)
                        loading_errors.append(error_msg)
                        self.errorOccurred.emit(f"Hiba a JSON fájl olvasásakor: {json_file_path.absolute()}", str(e))
                    except Exception as e:
                        error_msg = f"Ismeretlen hiba a(z) '{json_file_path.name}' betöltésekor: {e}"
                        self._log(logging.ERROR, f"Ismeretlen hiba a termék betöltésekor: {json_file_path.absolute()} - {e}", exc_info=True)
                        loading_errors.append(error_msg)
                        self.errorOccurred.emit(f"Ismeretlen hiba a termék betöltésekor: {json_file_path.absolute()}", str(e))
                else:
                    self._log(logging.WARNING, f"Kihagyott fájl, mert a JSON fájl neve ('{file_name_stem}') nem egyezik a szülőkönyvtár ID részével ('{expected_id_from_parent}'): {json_file_path.absolute()}")

            self._log(logging.INFO, f"{loaded_count} aktív termék sikeresen betöltve a memóriába.")
            self._apply_filters_internal()
            self.productsLoaded.emit(self._filtered_products, True, f"{loaded_count} aktív termék sikeresen betöltve.")
            if loading_errors:
                self.productLoadingErrors.emit(loading_errors)

        except Exception as e:
            self._log(logging.CRITICAL, f"Kritikus hiba a termékek betöltésekor: {e}", exc_info=True)
            message = f"Kritikus hiba a termékek betöltésekor: {e}"
            self.productsLoaded.emit([], False, message)
            self.errorOccurred.emit("Kritikus hiba a termékek betöltésekor", str(e))


    # --- Termék CRUD műveletek ---

    def _save_product_to_disk(self, product: Product, target_dir: Optional[Path] = None):
        """
        Elmenti a termék JSON adatokat a lemezre.
        Ez a metódus most már a Product objektum összes (beleértve a képszámlálókat is) adatát menti.
        """
        product_dir = target_dir if target_dir else self._get_product_path_from_product_object(product)
        json_file_path = self._get_product_json_path(product_dir)

        try:
            product_dir.mkdir(parents=True, exist_ok=True)
            images_dir = product_dir / "images"
            images_dir.mkdir(exist_ok=True)

            with open(json_file_path, 'w', encoding='utf-8') as f:
                json.dump(product.to_dict(), f, indent=4, ensure_ascii=False)
        except OSError as e:
            raise IOError(f"Fájlrendszer hiba a termék JSON mentésekor a '{json_file_path.absolute()}' helyre: {e}") from e
        except Exception as e:
            raise IOError(f"Váratlan hiba a termék JSON mentésekor a '{json_file_path.absolute()}' helyre: {e}") from e


    def _generate_next_local_product_id(self) -> str:
        """
        Megkeresi az első szabad, nem GS-függő termék ID-t 1000-től kezdve.
        A teljes fájlrendszert átvizsgálja, beleértve az eladott termékeket is,
        hogy megtalálja a "lyukakat" az ID-k sorozatában.
        """
        existing_ids = set()

        if self._base_product_dir.exists():
            # A 'product_*' mappanevekből gyűjtjük az ID-kat.
            for product_dir in self._base_product_dir.rglob('product_*'):
                if not product_dir.is_dir():
                    continue

                # A reguláris kifejezés biztosítja, hogy csak a tisztán numerikus
                # ID-jű mappákat (a nem GS-függő termékeket) vegyük figyelembe.
                match = re.search(r'^product_(\d+)$', product_dir.name)
                if match:
                    try:
                        existing_ids.add(int(match.group(1)))
                    except (ValueError, IndexError):
                        continue
        
        # Elindulunk 1000-től, és megkeressük az első számot, ami nincs a halmazban.
        next_id = 1000
        while next_id in existing_ids:
            next_id += 1
        
        new_id_str = str(next_id)
        self._log(logging.INFO, f"Új egyedi helyi termék ID generálva (első szabad hely): {new_id_str}")
        return new_id_str


    @Slot(Product)
    def add_or_update_product_sync(self, product: Product, run_filter_and_emit: bool = True):
        if not product:
            logger.warning("add_or_update_product_sync hívva 'None' termékkel. A művelet megszakítva.")
            return

        is_new_product = not product.id or product.id not in self._products
        
        old_needs_upload_state: Optional[bool] = None
        if not is_new_product and product.id in self._products:
            old_needs_upload_state = self._products[product.id].needs_upload

        try:
            if is_new_product and not product.is_gs_dependent:
                product.id = self._generate_next_local_product_id()
                self._log(logging.INFO, f"ProductManager: Új lokális ID generálva: '{product.id}'")
                product.created_at = datetime.now()
                product.needs_upload = True

                temp_images_dir = self.app_root_dir / "app_data_storage" / "tmp_images"
                if temp_images_dir.exists():
                    product_images_dir = self._get_product_path_from_product_object(product) / "images"
                    product_images_dir.mkdir(parents=True, exist_ok=True)
                    
                    image_files_to_move = [f for f in temp_images_dir.iterdir() if f.is_file()]
                    
                    product.num_original_images = len([f for f in image_files_to_move if f.name.startswith('original_')])
                    product.num_transparent_images = len([f for f in image_files_to_move if f.name.startswith('transparent_')])
                    product.num_mixed_images = len([f for f in image_files_to_move if f.name.startswith('mixed_')])
                    
                    for image_file in image_files_to_move:
                        shutil.move(str(image_file), str(product_images_dir / image_file.name))
                    
                    self._log(logging.INFO, f"{len(image_files_to_move)} kép áthelyezve a '{product.id}' termék mappájába.")
            
            elif is_new_product and product.is_gs_dependent:
                self._log(logging.INFO, f"ProductManager: Új, GS-függő termék mentése: '{product.id}'")

            elif not product.id:
                 raise ValueError("A termék ID mezője kötelező a frissítéshez.")

            if not product.main_category_slug or not product.product_type_slug:
                raise ValueError(f"A termék fő kategória slug ({product.main_category_slug}) és terméktípus slug ({product.product_type_slug}) mezői kötelezőek a mentéshez.")

            self._save_product_to_disk(product)          
            self._products[product.id] = product

            if run_filter_and_emit:
                self._apply_filters_internal()
                if is_new_product:
                    self.productAdded.emit(product, True, f"Új termék sikeresen hozzáadva: {product.title} (ID: {product.id})")
                else:
                    self.productUpdated.emit(product, True, f"Termék sikeresen frissítve: {product.title} (ID: {product.id})")
                    if old_needs_upload_state is not None and old_needs_upload_state != product.needs_upload:
                        self.productNeedsUploadStateChanged.emit(product.id, product.needs_upload)

        except (ValueError, IOError, Exception) as e:
            error_type = type(e).__name__
            log_level = logging.CRITICAL if isinstance(e, (IOError, Exception)) else logging.ERROR
            self._log(log_level, f"ProductManager: HIBA a termék hozzáadásakor/frissítésekor ({error_type}): {e}", exc_info=True)
            
            error_title = f"Termék mentési hiba ({error_type})"
            if product and product.id:
                error_title += f": {product.id}"
            else:
                error_title += ": N/A"

            self.errorOccurred.emit(error_title, str(e))
            
            signal_to_emit = self.productAdded if is_new_product else self.productUpdated
            signal_to_emit.emit(product, False, f"Hiba a termék mentésekor: {e}")

    def _get_product_from_any_source(self, product_id: str) -> Optional[Product]:
        """
        Megpróbálja lekérni a terméket a memóriából, vagy ha ott nem található,
        akkor a lemezről betölteni annak JSON fájlját.
        """
        if product_id in self._products:
            self._log(logging.DEBUG, f"Termék '{product_id}' megtalálva a memóriában.")
            return self._products[product_id]

        self._log(logging.DEBUG, f"Termék '{product_id}' nem található a memóriában, keresés a lemezen.")
        found_json_path: Optional[Path] = None
        for json_file_path in self._base_product_dir.rglob(f'*{product_id}.json'):
            if json_file_path.parent.name == f"product_{product_id}":
                found_json_path = json_file_path
                break
        
        if found_json_path:
            try:
                with open(found_json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                product = Product.from_dict(data)
                self._log(logging.DEBUG, f"Termék '{product_id}' sikeresen betöltve a lemezről a '_get_product_from_any_source' metódusban.")
                return product
            except Exception as e:
                self._log(logging.ERROR, f"Hiba a termék '{product_id}' JSON fájljának betöltésekor a lemezről: {e}", exc_info=True)
                return None
        
        self._log(logging.DEBUG, f"Termék '{product_id}' sem a memóriában, sem a lemezen nem található.")
        return None

    @Slot(str)
    def mark_product_as_sold_sync(self, product_id: str):
        self._log(logging.INFO, f"Termék '{product_id}' eladottként jelölése kérés érkezett.")
        
        product_to_mark_sold = self._get_product_from_any_source(product_id)

        if not product_to_mark_sold:
            message = f"Hiba: A '{product_id}' azonosítójú termék nem található a memóriában és a lemezen sem az eladáshoz."
            self._log(logging.ERROR, message)
            self.productSold.emit(product_id, False, message)
            self.productDeleted.emit(product_id, False, message)
            return
        
        if product_to_mark_sold.is_sold:
            message = f"A termék '{product_id}' már eladottként van jelölve."
            self._log(logging.INFO, message)
            self.productSold.emit(product_id, True, message)
            return

        product_to_mark_sold.is_sold = True

        try:
            self._save_product_to_disk(product_to_mark_sold)
            product_to_mark_sold.needs_upload = True

            self._apply_filters_internal()

            message = f"Termék '{product_id}' sikeresen eladottként jelölve."
            self._log(logging.INFO, message)
            
            self.productSold.emit(product_id, True, message)

            self.productDeleted.emit(product_id, True, message)

        except Exception as e:
            message = f"Hiba a termék '{product_id}' eladottként jelölésekor: {e}"
            self._log(logging.ERROR, message, exc_info=True)
            self.errorOccurred.emit(f"Eladottként jelölés hiba: {product_id}", str(e))
            self.productSold.emit(product_id, False, message)
            self.productDeleted.emit(product_id, False, message)

    @Slot(str)
    def delete_product_permanently_sync(self, product_id: str):
        self._log(logging.INFO, f"Termék '{product_id}' végleges törlése kezdeményezve (merevlemezről is).")

        product_to_delete = self._get_product_from_any_source(product_id)
        if not product_to_delete:
            message = f"Hiba: A '{product_id}' azonosítójú termék nem található a memóriában és a lemezen sem a végleges törléshez."
            self._log(logging.ERROR, message)
            self.errorOccurred.emit("Végleges törlés hiba", message)
            self.productDeleted.emit(product_id, False, message)
            return

        product_dir = self._get_product_path_from_product_object(product_to_delete)

        try:
            if product_dir.exists():
                shutil.rmtree(product_dir)
                self._log(logging.INFO, f"Termékmappa sikeresen törölve a merevlemezről: {product_dir.absolute()}")
            else:
                self._log(logging.WARNING, f"Termékmappa '{product_dir.absolute()}' nem létezik, nincs mit törölni a merevlemezről.")

            if product_id in self._products:
                del self._products[product_id]

            self._apply_filters_internal()

            message = f"Termék '{product_id}' véglegesen törölve a merevlemezről."
            self._log(logging.INFO, message)
            self.productDeleted.emit(product_id, True, message)

        except Exception as e:
            message = f"Hiba a termék '{product_id}' végleges törlésekor a merevlemezről: {e}"
            self._log(logging.ERROR, message, exc_info=True)
            self.errorOccurred.emit("Végleges törlés hiba", message)
            self.productDeleted.emit(product_id, False, message)


    @Slot(str, MainCategory, str, str)
    def change_product_category_sync(self, product_id: str, new_main_category: MainCategory,
                                     new_sub_category_slug: Optional[str], new_product_type_slug: Optional[str]):
        self._log(logging.INFO, f"Termék '{product_id}' kategória módosításának kérése. Új fő kat.: {new_main_category.name}, Alkat.: {new_sub_category_slug}, Típus: {new_product_type_slug}")

        product = self._products.get(product_id)
        if not product:
            message = f"Hiba: A '{product_id}' azonosítójú termék nem található a kategória módosításához."
            self._log(logging.WARNING, message)
            self.categoryChanged.emit(product_id, "", "", False, message)
            return

        old_product_path = self._get_product_path_from_product_object(product)
        new_product_path = self._get_product_path_from_slugs(
            product_id, new_main_category.to_slug(), new_sub_category_slug, new_product_type_slug
        )

        old_path_str = str(old_product_path.absolute())
        new_path_str = str(new_product_path.absolute())

        try:
            # --- FÁJLRENDSZER MŰVELETEK ---
            if old_product_path != new_product_path:
                if not new_product_path.exists():
                    # NORMÁL ESET: A cél nem létezik, áthelyezzük a régit.
                    shutil.move(old_product_path, new_product_path)
                    self._log(logging.INFO, f"Termékmappa sikeresen áthelyezve: '{old_path_str}' -> '{new_path_str}'")
                else:
                    # HELYREÁLLÍTÁSI ESET: A cél már létezik. Töröljük a régi, felesleges mappát.
                    self._log(logging.WARNING, f"A célkönyvtár ('{new_path_str}') már létezik. Helyreállítás: a régi mappa törlésre kerül.")
                    if old_product_path.exists():
                        shutil.rmtree(old_product_path)
                        self._log(logging.INFO, f"Felesleges régi mappa sikeresen törölve: '{old_path_str}'")

                # Az áthelyezés/törlés után takarítjuk az üres szülőmappákat a régi helyen.
                current_old_parent = old_product_path.parent
                while current_old_parent != self._base_product_dir and not any(current_old_parent.iterdir()):
                    try:
                        current_old_parent.rmdir()
                        self._log(logging.DEBUG, f"Üres szülőkönyvtár törölve: {current_old_parent}")
                        current_old_parent = current_old_parent.parent
                    except OSError as e:
                        self._log(logging.WARNING, f"Nem sikerült törölni az üres szülőkönyvtárat '{current_old_parent}': {e}")
                        break

            # --- ADATFRISSÍTÉS A MEMÓRIÁBAN ---
            product.main_category = new_main_category
            product.main_category_slug = new_main_category.to_slug()
            product.sub_category_slug = new_sub_category_slug or _sanitize_for_slug("Nincs alkategória")
            product.product_type_slug = new_product_type_slug or _sanitize_for_slug("Nincs terméktípus")
            
            sub_cat_name = next((name for name, slug in self.category_manager.get_sub_categories_with_slugs_for_main(new_main_category) if slug == new_sub_category_slug), "")
            
            new_product_type_name = "Nincs terméktípus"
            if sub_cat_name:
                new_product_type_name = next((name for name in self.category_manager.get_product_types_for_sub(new_main_category, sub_cat_name) if _sanitize_for_slug(name) == new_product_type_slug), "Nincs terméktípus")
            product.product_type = new_product_type_name
            
            product.needs_manual_category_review = False
            if not product.needs_upload:
                product.needs_upload = True

            # --- MENTÉS ÉS JELZÉSEK ---
            self._save_product_to_disk(product, target_dir=new_product_path)
            self._products[product_id] = product
            self._apply_filters_internal()

            message = f"Termék '{product_id}' kategóriája sikeresen módosítva."
            self._log(logging.INFO, message)
            
            #self.productUpdated.emit(product, True, message)
            self.categoryChanged.emit(product_id, old_path_str, new_path_str, True, message)
            self.productsLoaded.emit(self._filtered_products, True, "Lista frissítve a kategória módosítása után.")

        except (IOError, ValueError, Exception) as e:
            # Visszaállítási kísérlet hiba esetén
            original_product_state = self.get_product_by_id(product_id)
            if original_product_state:
                self._products[product_id] = original_product_state

            message = f"Hiba a termék '{product_id}' kategóriájának módosításakor: {e}"
            self._log(logging.ERROR, message, exc_info=True)
            self.errorOccurred.emit(f"Kategória módosítási hiba: {product_id}", str(e))
            self.categoryChanged.emit(product_id, old_path_str, new_path_str, False, message)


    # --- Galéria Savaria adatfeldolgozás ---

    @Slot(str, list, bool, str)
    def process_gs_extracted_products_slot(self, identifier: str, extracted_data: List[Dict[str, Any]], success: bool, message: str):
        if not success:
            self._log(logging.ERROR, f"Hiba a Galéria Savaria adatok kinyerésekor ({identifier}): {message}")
            self.errorOccurred.emit("GS adatkinyerési hiba", f"Azonosító: {identifier}, Üzenet: {message}")
            self.productsBatchProcessed.emit([], False, f"GS adatok feldolgozása sikertelen: {message}")
            return

        self._log(logging.INFO, f"Galéria Savaria adatok feldolgozása indult ({len(extracted_data)} elem) azonosító: {identifier}.")

        gs_product_ids_before_scrape = {p.id for p in self._products.values() if p.is_gs_dependent and not p.is_sold}
        found_gs_ids_in_scrape = set()
        products_processed_in_this_batch: List[Product] = []
        new_products_info = []

        for item_data in extracted_data:
            gs_product_id = str(item_data.get('code'))
            if not gs_product_id:
                self._log(logging.WARNING, f"Galéria Savaria termék azonosító nélkül. Kihagyva: {item_data.get('name', 'N/A')}")
                continue

            found_gs_ids_in_scrape.add(gs_product_id)
            product_to_update_or_create: Optional[Product] = self._products.get(gs_product_id)
            product_title = item_data.get('name', '')

            if product_to_update_or_create:
                # --- JAVÍTÁS KEZDETE ---

                # Először ellenőrizzük, hogy a cím megváltozott-e, mert ez befolyásolja a kategóriát.
                title_changed = product_to_update_or_create.title != product_title
                
                # Ellenőrizzük, hogy van-e bármilyen más frissítenivaló adat.
                data_changed = (
                    product_to_update_or_create.gs_views != item_data.get('views', 0) or
                    product_to_update_or_create.gs_watchers != item_data.get('watchers', 0) or
                    product_to_update_or_create.price_numeric != item_data.get('price_numeric', 0.0) or
                    product_to_update_or_create.is_delisted_on_gs
                )

                # Csak akkor lépünk tovább, ha a cím vagy valamilyen más adat megváltozott.
                if title_changed or data_changed:
                    
                    # Alapadatok frissítése
                    product_to_update_or_create.title = product_title
                    product_to_update_or_create.price_numeric = item_data.get('price_numeric', 0.0)
                    product_to_update_or_create.price_raw = item_data.get('price', '')
                    product_to_update_or_create.gs_watchers = item_data.get('watchers', 0)
                    product_to_update_or_create.gs_views = item_data.get('views', 0)
                    product_to_update_or_create.is_delisted_on_gs = False # Ha szerepel a listában, akkor biztosan nem törölt
                    
                    # Kategória frissítése, HA a cím változott, VAGY ha a termék eddig nem volt besorolva.
                    if title_changed or product_to_update_or_create.main_category == MainCategory.UNCATEGORIZED:
                        self._log(logging.DEBUG, f"Termék újrakategorizálása: '{gs_product_id}', ok: {'címváltozás' if title_changed else 'kategorizálatlan'}.")
                        best_match = self.category_manager.find_best_category_by_item_name(product_title)
                        if best_match:
                            main_cat_str, sub_cat_str, item_type_str = best_match
                            try:
                                main_cat = MainCategory(main_cat_str)
                                # Explicit és helyes értékadás a keveredés elkerülése végett
                                product_to_update_or_create.main_category = main_cat
                                product_to_update_or_create.main_category_slug = main_cat.to_slug()
                                product_to_update_or_create.sub_category_slug = _sanitize_for_slug(sub_cat_str)
                                product_to_update_or_create.product_type = item_type_str
                                product_to_update_or_create.product_type_slug = _sanitize_for_slug(item_type_str)
                                product_to_update_or_create.needs_manual_category_review = False
                            except ValueError:
                                # Ha a konvertálás nem sikerül, hagyjuk felülvizsgálandónak
                                product_to_update_or_create.needs_manual_category_review = True
                        else:
                            # Ha nincs találat, szintén felülvizsgálandó
                            product_to_update_or_create.needs_manual_category_review = True
                    
                    # A frissített termék mentése
                    self.add_or_update_product_sync(product_to_update_or_create, run_filter_and_emit=False)
                    products_processed_in_this_batch.append(product_to_update_or_create)
                # --- JAVÍTÁS VÉGE ---
            else:
                # Új termék létrehozása (ez a rész már helyesen működött)
                new_products_info.append(f"({gs_product_id}) {product_title}")
                main_cat, main_cat_slug, sub_cat_slug, product_type_name, product_type_slug, needs_review = self._get_suggested_category_for_new_product(product_title)
                new_product = Product(
                    id=gs_product_id, title=product_title, price_numeric=item_data.get('price_numeric', 0.0), price_raw=item_data.get('price', ''),
                    main_category=main_cat, main_category_slug=main_cat_slug, sub_category_slug=sub_cat_slug,
                    product_type=product_type_name, product_type_slug=product_type_slug,
                    gs_watchers=item_data.get('watchers', 0), gs_views=item_data.get('views', 0), is_gs_dependent=True,
                    needs_manual_category_review=needs_review, needs_upload=True,
                    image_url=item_data.get('image_url'), product_url=item_data.get('product_url'), additional_attributes=item_data
                )
                self.add_or_update_product_sync(new_product, run_filter_and_emit=False)
                products_processed_in_this_batch.append(new_product)

        delisted_product_ids = gs_product_ids_before_scrape - found_gs_ids_in_scrape
        if delisted_product_ids:
            self._log(logging.INFO, f"{len(delisted_product_ids)} termék tűnt el a GS oldalról. Jelölésük...")
            for product_id in delisted_product_ids:
                product = self._products.get(product_id)
                if product and not product.is_delisted_on_gs:
                    product.is_delisted_on_gs = True
                    self.add_or_update_product_sync(product, run_filter_and_emit=False)
                    products_processed_in_this_batch.append(product)

        # === JAVÍTÁS: Riport adatok számítása a legutóbbi két RAW fájl összehasonlításával ===
        view_changes_count = 0
        watcher_changes_count = 0
        total_items_read = len(extracted_data)

        try:
            raw_gs_dir = self.app_root_dir / FOLDER_APP_DATA / FOLDER_RAW / FOLDER_RAW_GS
            
            # Módosítási idő alapján rendezzük a fájlokat, ez a legbiztosabb
            json_files = sorted(raw_gs_dir.glob('gs_data_raw_*.json'), key=os.path.getmtime)

            if len(json_files) >= 2:
                latest_file = json_files[-1]
                previous_file = json_files[-2]

                with open(latest_file, 'r', encoding='utf-8') as f:
                    current_data_from_file = json.load(f)
                with open(previous_file, 'r', encoding='utf-8') as f:
                    previous_data_from_file = json.load(f)

                # A korábbi adatokból készítünk egy gyorsan kereshető szótárat
                previous_stats = {item['code']: {'views': item['views'], 'watchers': item['watchers']} 
                                  for item in previous_data_from_file if 'code' in item}
                
                # Végigmegyünk az AKTUÁLIS adatokon, és összevetjük a KORÁBBI szótárral
                for current_item in current_data_from_file:
                    code = current_item.get('code')
                    if code and code in previous_stats:
                        if previous_stats[code]['views'] != current_item.get('views', 0):
                            view_changes_count += 1
                        if previous_stats[code]['watchers'] != current_item.get('watchers', 0):
                            watcher_changes_count += 1
                
                self._log(logging.INFO, f"Változások összehasonlítása: '{latest_file.name}' vs '{previous_file.name}'. Változások (Nézettség/Figyelők): {view_changes_count}/{watcher_changes_count}")
            else:
                self._log(logging.INFO, "Nem áll rendelkezésre elegendő (legalább 2) nyers adatfájl a változások összehasonlításához.")

        except Exception as e:
            self._log(logging.ERROR, f"Hiba a nyers adatfájlok összehasonlítása közben a riport generálásához: {e}", exc_info=True)
        # === JAVÍTÁS VÉGE ===

        # --- A riport generálása és a jelek kibocsátása (változatlan) ---
        report_html = self._generate_gs_report_html(total_items_read, new_products_info, view_changes_count, watcher_changes_count)
        self.gsProcessingReportReady.emit(report_html)

        self._apply_filters_internal()
        self.productsBatchProcessed.emit(products_processed_in_this_batch, True, f"Galéria Savaria adatok feldolgozva, {len(products_processed_in_this_batch)} termék frissítve/hozzáadva.")

    def _get_suggested_category_for_new_product(self, product_title: str) -> Tuple:
        """Segédfüggvény, ami egy új termék címéből megpróbálja kitalálni a kategóriát."""
        main_cat = MainCategory.UNCATEGORIZED
        main_cat_slug = main_cat.to_slug()
        sub_cat_slug = _sanitize_for_slug("Nincs alkategória")
        product_type_name = "Nincs terméktípus"
        product_type_slug = _sanitize_for_slug("Nincs terméktípus")
        needs_review = True

        best_match = self.category_manager.find_best_category_by_item_name(product_title)
        if best_match:
            try:
                main_cat_str, sub_cat_str, item_type_str = best_match
                main_cat = MainCategory(main_cat_str)
                main_cat_slug = main_cat.to_slug()
                sub_cat_slug = _sanitize_for_slug(sub_cat_str)
                product_type_name = item_type_str
                product_type_slug = _sanitize_for_slug(item_type_str)
                needs_review = False
            except ValueError:
                self._log(logging.WARNING, f"Ismeretlen főkategória-név a javaslatból: '{best_match[0]}'")
        
        return main_cat, main_cat_slug, sub_cat_slug, product_type_name, product_type_slug, needs_review

    def _generate_gs_report_html(self, total_read: int, new_products: List[str], view_changes: int, watcher_changes: int) -> str:
        """Összeállít egy HTML formátumú jelentést a feldolgozás eredményeiről."""
        timestamp = datetime.now().strftime("%Y. %m. %d. %H:%M:%S")
        
        html = f"<h1>Galéria Savaria Feldolgozási Jelentés</h1>"
        html += f"<p><i>Generálva: {timestamp}</i></p>"
        html += "<hr>"
        
        html += f"<h2>Összegzés</h2>"
        html += f"<p><b>Beolvasott termékek száma a weboldalról:</b> {total_read}</p>"
        html += f"<p><b>Megtekintések számában változás:</b> {view_changes} terméknél</p>"
        html += f"<p><b>Megfigyelők számában változás:</b> {watcher_changes} terméknél</p>"
        html += f"<p><b>Újonnan hozzáadott termékek az adatbázisba:</b> {len(new_products)} db</p>"

        if new_products:
            html += f"<h2>Új Termékek Listája</h2>"
            html += "<ul>"
            for product_info in new_products:
                html += f"<li>{product_info}</li>"
            html += "</ul>"
        
        return html

    @Slot(str, list, bool, str)
    def process_jf_extracted_products_slot(self, identifier: str, extracted_data: List[Dict[str, Any]], success: bool, message: str):
        if not success:
            self._log(logging.ERROR, f"Hiba a Jófogás adatok kinyerésekor ({identifier}): {message}")
            self.errorOccurred.emit("Jófogás adatkinyerési hiba", f"Azonosító: {identifier}, Üzenet: {message}")
            self.productsBatchProcessed.emit([], False, f"Jófogás adatok feldolgozása sikertelen: {message}")
            return

        self._log(logging.INFO, f"Jófogás adatok feldolgozása indult ({len(extracted_data)} elem).")
        products_processed_in_this_batch: List[Product] = []
        
        # --- RIport adatok gyűjtése ---
        total_items_on_jofogas = len(extracted_data)
        expires_in_75 = 0; expires_in_50 = 0; expires_in_15 = 0
        for ad_data in extracted_data:
            try:
                days = ad_data.get("expires_in_days")
                if isinstance(days, int):
                    if days < 15: expires_in_15 += 1
                    if days < 50: expires_in_50 += 1
                    if days < 75: expires_in_75 += 1
            except (ValueError, TypeError): continue

        # --- Termékek párosítása és frissítése ---
        found_product_ids_in_scrape = set()

        def clean_jofogas_name(raw_name: str) -> str:
            parts = raw_name.strip().split(' - ', 1)
            return (parts[1] if len(parts) > 1 else parts[0]).strip().lower()

        for ad_data in extracted_data:
            ad_name_raw = ad_data.get("name")
            if not ad_name_raw:
                continue

            cleaned_ad_name = clean_jofogas_name(ad_name_raw)
            ad_price = ad_data.get("price_numeric", -1.0)

            found_product: Optional[Product] = None
            for product in self._products.values():
                if not product.is_sold and (product.title.strip().lower() == cleaned_ad_name and abs(product.price_numeric - ad_price) < 0.01):
                    found_product = product
                    break
            
            if found_product:
                found_product_ids_in_scrape.add(found_product.id)
                updated = False
                
                # 1. Pozíció frissítése a fő objektumon
                new_position = ad_data.get("position")
                if found_product.jf_position != new_position:
                    found_product.jf_position = new_position
                    updated = True

                # 2. Egyéb adatok frissítése az attribútumokban
                jf_attributes = found_product.additional_attributes.get("jofogas", {})
                
                new_views = ad_data.get("views")
                if new_views != "N/A" and jf_attributes.get("views") != new_views:
                    jf_attributes["views"] = new_views
                    updated = True
                
                new_expires = ad_data.get("expires_in_days")
                if new_expires != "N/A" and jf_attributes.get("expires_in_days") != new_expires:
                    jf_attributes["expires_in_days"] = new_expires
                    updated = True

                if "position" in jf_attributes:
                    del jf_attributes["position"]

                if updated:
                    found_product.additional_attributes["jofogas"] = jf_attributes
                    self.add_or_update_product_sync(found_product, run_filter_and_emit=False)
                    products_processed_in_this_batch.append(found_product)
                    self._log(logging.DEBUG, f"Jófogás adatok frissítve: '{found_product.title}'")

        # --- Listáról lekerült termékek pozíciójának nullázása ---
        for product in self._products.values():
            if product.jf_position is not None and product.id not in found_product_ids_in_scrape:
                product.jf_position = None
                self.add_or_update_product_sync(product, run_filter_and_emit=False)
                products_processed_in_this_batch.append(product)
                self._log(logging.INFO, f"'{product.title}' lekerült a Jófogásról, pozíció nullázva.")

        # --- Riport generálása és jelek kibocsátása ---
        jofogas_ad_tuples = {(clean_jofogas_name(ad['name']), ad.get('price_numeric', -1.0)) for ad in extracted_data if 'name' in ad}
        missing_gs_products = [p for p in self._products.values() if p.is_gs_dependent and not p.is_sold and (p.title.strip().lower(), p.price_numeric) not in jofogas_ad_tuples]

        report_html = self._generate_jf_report_html(total_items_on_jofogas, expires_in_75, expires_in_50, expires_in_15, missing_gs_products)
        self.jfProcessingReportReady.emit(report_html)
        
        self._apply_filters_internal()

        if products_processed_in_this_batch:
            self.productsBatchProcessed.emit(products_processed_in_this_batch, True, f"Jófogás adatok feldolgozva, {len(products_processed_in_this_batch)} termék frissítve.")
        else:
            self._log(logging.INFO, "Jófogás adatfeldolgozás befejezve, nem történt termékfrissítés.")

    def _generate_jf_report_html(self, total_count: int, expires_75: int, expires_50: int, expires_15: int, missing_products: List[Product]) -> str:
        """Összeállít egy HTML formátumú jelentést a Jófogás feldolgozás eredményeiről."""
        timestamp = datetime.now().strftime("%Y. %m. %d. %H:%M:%S")
        
        html = f"<h1>Jófogás Feldolgozási Jelentés</h1>"
        html += f"<p><i>Generálva: {timestamp}</i></p>"
        html += "<hr>"
        
        html += f"<h2>Összegzés</h2>"
        html += f"<p><b>Hirdetések száma a Jófogáson összesen:</b> {total_count} db</p>"

        html += f"<h2>Lejárati Kategóriák</h2>"
        html += "<ul>"
        html += f"<li><b>75 napon belül lejár:</b> {expires_75} db</li>"
        html += f"<li><b>50 napon belül lejár:</b> {expires_50} db</li>"
        html += f"<li><b>15 napon belül lejár:</b> {expires_15} db</li>"
        html += "</ul>"

        html += f"<h2>Hiányzó GS-Függő Termékek</h2>"
        html += f"<p>Az alábbi {len(missing_products)} GS-függő termék nem található meg a Jófogás hirdetések között:</p>"

        if missing_products:
            html += "<table border='1' cellpadding='5' style='border-collapse: collapse; width: 100%;'>"
            html += "<tr style='background-color: #f2f2f2;'><th>ID</th><th>Név</th><th>Ár</th></tr>"
            for product in sorted(missing_products, key=lambda p: p.id):
                 price_str = f"{int(product.price_numeric):,} Ft".replace(',', ' ')
                 html += f"<tr><td>{product.id}</td><td>{product.title}</td><td>{price_str}</td></tr>"
            html += "</table>"
        else:
            html += "<p><i>(Nincs hiányzó termék.)</i></p>"

        return html

    # --- Szűrés ---

    def _apply_filters_internal(self):
        is_sold_filter_active = self._current_filters.get("is_sold", False)

        if is_sold_filter_active:
            self._filtered_products = [p for p in self._products.values() if p.is_sold]
            self._log(logging.INFO, f"{len(self._filtered_products)} eladott termék felel meg a szűrőnek.")
            return

        if not self._current_filters:
            self._filtered_products = [p for p in self._products.values() if not p.is_sold]
            self._log(logging.INFO, f"Nincs aktív szűrő. {len(self._filtered_products)} aktív termék megjelenítve.")
            return

        filtered_list = []
        
        search_term = self._current_filters.get("search_term", "").lower()
        search_in_title = self._current_filters.get("search_in_title", False)
        search_in_description = self._current_filters.get("search_in_description", False)
        id_filter = self._current_filters.get("id", "").lower()
        price_min = self._current_filters.get("price_min", 0.0)
        price_max = self._current_filters.get("price_max", float('inf'))
        main_category_slug_filter = self._current_filters.get("main_category_slug", "").lower()
        sub_category_slug_filter = self._current_filters.get("sub_category_slug", "").lower()
        product_type_slug_filter = self._current_filters.get("product_type_slug", "").lower()
        is_gs_dependent_filter = self._current_filters.get("is_gs_dependent", None)

        for product in self._products.values():
            if product.is_sold:
                continue

            match = True

            if match and search_term:
                term_found = False
                if search_in_title and search_term in product.title.lower():
                    term_found = True
                if not term_found and search_in_description and product.description and search_term in product.description.lower():
                    term_found = True
                if not term_found:
                    match = False

            if match and id_filter and id_filter not in product.id.lower():
                match = False

            if match and (product.price_numeric < price_min or product.price_numeric > price_max):
                match = False

            if match and main_category_slug_filter and main_category_slug_filter != product.main_category_slug.lower():
                match = False

            if match and sub_category_slug_filter and sub_category_slug_filter != product.sub_category_slug.lower():
                match = False

            if match and product_type_slug_filter and product_type_slug_filter != product.product_type_slug.lower():
                match = False

            if match and is_gs_dependent_filter is not None and product.is_gs_dependent != is_gs_dependent_filter:
                match = False
            
            if match:
                filtered_list.append(product)

        self._filtered_products = filtered_list
        self._log(logging.INFO, f"{len(self._filtered_products)} aktív termék felel meg a szűrőfeltételeknek.")


    @Slot(dict)
    def apply_filters(self, filters: Dict[str, Any]):
        self._current_filters = filters
        self._apply_filters_internal()
        self.productsLoaded.emit(self._filtered_products, True, f"{len(self._filtered_products)} termék szűrve.")
        self._log(logging.INFO, f"Szűrők alkalmazva: {filters}. Eredmény: {len(self._filtered_products)} termék.")


    @Slot()
    def clear_filters(self):
        self._current_filters.clear()
        self._apply_filters_internal()
        self.productsLoaded.emit(self._filtered_products, True, "Szűrők törölve, teljes lista megjelenítve.")
        self._log(logging.INFO, "Szűrők törölve, teljes lista megjelenítve.")


    @Slot(str)
    def reactivate_product_sync(self, product_id: str):
        """Egy eladott terméket újra aktívvá tesz."""
        product = self.get_product_by_id(product_id)
        if not product:
            message = f"Hiba: A '{product_id}' azonosítójú termék nem található az újraaktiváláshoz."
            self._log(logging.ERROR, message)
            self.productUpdated.emit(None, False, message)
            return

        product.is_sold = False
        product.needs_upload = True
        
        self.add_or_update_product_sync(product)
        self._log(logging.INFO, f"A(z) '{product_id}' termék újraaktiválva és mentve.")

        self.apply_filters(self._current_filters)

    def get_product_by_id(self, product_id: str) -> Optional[Product]:
        return self._products.get(product_id)


    def get_all_products(self) -> List[Product]:
        return list(self._products.values())


    def get_filtered_products(self) -> List[Product]:
        return self._filtered_products


    def get_products_by_main_category(self, main_category: MainCategory) -> List[Product]:
        return [p for p in self._products.values() if p.main_category == main_category]


    def get_sold_products(self) -> List[Product]:
        return []


    def get_gs_dependent_products(self) -> List[Product]:
        return [p for p in self._products.values() if p.is_gs_dependent]


    def get_products_needing_review(self) -> List[Product]:
        return [p for p in self._products.values() if p.needs_manual_category_review]
    
    @Slot(dict, Product)
    def finalize_gs_new_product(self, validated_on_site_data: dict, original_product_data: Product):
        """
        Sikeres GS validálás után véglegesíti és elmenti az új terméket.
        """
        try:
            new_id = validated_on_site_data.get('code')
            if not new_id:
                raise ValueError("A validált adatokból hiányzik a termékazonosító (code).")

            final_product = original_product_data
            final_product.id = new_id
            
            final_product.gs_views = validated_on_site_data.get('views', 0)
            final_product.gs_watchers = validated_on_site_data.get('watchers', 0)
            final_product.product_url = validated_on_site_data.get('product_url')
            final_product.image_url = validated_on_site_data.get('image_url')
            final_product.additional_attributes.update(validated_on_site_data)
            
            temp_images_dir = self.app_root_dir / "app_data_storage" / "tmp_images"
            if temp_images_dir.exists():
                product_images_dir = self._get_product_path_from_product_object(final_product) / "images"
                product_images_dir.mkdir(parents=True, exist_ok=True)
                
                image_files_to_move = [f for f in temp_images_dir.iterdir() if f.is_file()]
                
                final_product.num_original_images = len([f for f in image_files_to_move if f.name.startswith('original_')])
                final_product.num_transparent_images = len([f for f in image_files_to_move if f.name.startswith('transparent_')])
                final_product.num_mixed_images = len([f for f in image_files_to_move if f.name.startswith('mixed_')])
                
                for image_file in image_files_to_move:
                    shutil.move(str(image_file), str(product_images_dir / image_file.name))
                
                self._log(logging.INFO, f"{len(image_files_to_move)} kép áthelyezve az új '{final_product.id}' GS termék mappájába.")

            self.add_or_update_product_sync(final_product)

        except Exception as e:
            message = f"Hiba az új GS termék véglegesítésekor: {e}"
            self._log(logging.ERROR, message, exc_info=True)
            self.errorOccurred.emit("Új GS termék mentési hiba", message)

    @Slot()
    def increment_all_jofogas_positions_sync(self):
        """
        Növeli az összes létező Jófogás pozíciót 1-gyel.
        Ez akkor hasznos, ha egy új hirdetés kerül az 1. helyre,
        és minden más hátrébb csúszik.
        """
        self._log(logging.INFO, "Jófogás pozíciók növelése 1-gyel (új hirdetés beszúrása)...")
        affected_products: List[Product] = []

        # Gyűjtsük ki az összes olyan terméket, aminek van pozíciója
        products_to_update = [
            p for p in self._products.values() if p.jf_position is not None
        ]

        if not products_to_update:
            self._log(logging.INFO, "Nincs egyetlen termék sem Jófogás pozícióval, nincs teendő.")
            return

        for product in products_to_update:
            try:
                product.jf_position += 1
                self._save_product_to_disk(product)
                affected_products.append(product)
            except (IOError, Exception) as e:
                message = f"Hiba a(z) '{product.id}' termék Jófogás pozíciójának növelésekor: {e}"
                self._log(logging.ERROR, message, exc_info=True)
                self.errorOccurred.emit("Jófogás pozíció mentési hiba", message)
        
        if affected_products:
            self._log(logging.INFO, f"{len(affected_products)} termék Jófogás pozíciója sikeresen növelve.")
            # Jelezzük a UI-nak, hogy tömeges változás történt, és frissítenie kell a listát.
            self.productsBatchProcessed.emit(affected_products, True, "Jófogás pozíciók frissítve.")

    @Slot(str)
    def decrement_jofogas_positions_after_sync(self, deleted_product_id: str):
        """
        Egy termék "törlése" után csökkenti az összes utána következő termék
        Jófogás pozícióját 1-gyel. A törölt termék pozícióját None-ra állítja.
        """
        self._log(logging.INFO, f"Jófogás pozíciók csökkentése a '{deleted_product_id}' termék törlése miatt...")
        affected_products: List[Product] = []

        # 1. Keressük meg a törölt terméket és annak pozícióját
        deleted_product = self._products.get(deleted_product_id)
        if not deleted_product or deleted_product.jf_position is None:
            self._log(logging.WARNING, f"A '{deleted_product_id}' termék nem található vagy nincs Jófogás pozíciója. A művelet megszakítva.")
            return

        deleted_position = deleted_product.jf_position

        # 2. A törölt termék pozíciójának nullázása és mentése
        try:
            deleted_product.jf_position = None
            self._save_product_to_disk(deleted_product)
            affected_products.append(deleted_product)
        except (IOError, Exception) as e:
            message = f"Hiba a(z) '{deleted_product_id}' termék Jófogás pozíciójának nullázásakor: {e}"
            self._log(logging.ERROR, message, exc_info=True)
            self.errorOccurred.emit("Jófogás pozíció mentési hiba", message)
            # A hiba ellenére folytatjuk, hátha a többit sikerül frissíteni
        
        # 3. Keressük meg az összes terméket, ami a törölt után következett
        products_to_update = [
            p for p in self._products.values() 
            if p.jf_position is not None and p.jf_position > deleted_position
        ]

        # 4. Csökkentsük a pozíciójukat és mentsük el őket
        for product in products_to_update:
            try:
                product.jf_position -= 1
                self._save_product_to_disk(product)
                affected_products.append(product)
            except (IOError, Exception) as e:
                message = f"Hiba a(z) '{product.id}' termék Jófogás pozíciójának csökkentésekor: {e}"
                self._log(logging.ERROR, message, exc_info=True)
                self.errorOccurred.emit("Jófogás pozíció mentési hiba", message)
        
        if len(affected_products) > 1: # (a töröltön kívül más is módosult)
            self._log(logging.INFO, f"{len(products_to_update)} termék Jófogás pozíciója sikeresen csökkentve.")
            self.productsBatchProcessed.emit(affected_products, True, "Jófogás pozíciók frissítve törlés miatt.")
        else:
             self.productUpdated.emit(deleted_product, True, "Termék Jófogás pozíciója törölve.")

    def _check_id_mismatches(self) -> list:
        """
        Végigpásztázza a termékkönyvtárat, és megkeresi azokat a termékeket,
        ahol a JSON fájl neve nem egyezik a szülő 'product_*' mappa ID-jával.
        Visszaad egy listát a hibás elemekről.
        """
        mismatches = []
        self._log(logging.INFO, "ID eltérések keresése a fájlrendszerben...")
        
        if not self._base_product_dir.exists():
            return []

        for json_file_path in self._base_product_dir.rglob('*.json'):
            file_name_stem = json_file_path.stem
            parent_dir = json_file_path.parent
            parent_dir_name = parent_dir.name

            if parent_dir_name.startswith("product_"):
                expected_id = parent_dir_name.replace("product_", "")
                if file_name_stem != expected_id:
                    mismatches.append({
                        "path": str(parent_dir.relative_to(self._base_product_dir)),
                        "expected_id": expected_id,
                        "actual_filename": json_file_path.name
                    })
        
        self._log(logging.INFO, f"{len(mismatches)} db ID eltérés található.")
        return mismatches

    def _generate_id_mismatch_report_html(self, mismatches: list) -> str:
        """HTML riportot generál az ID eltérésekről."""
        timestamp = datetime.now().strftime("%Y. %m. %d. %H:%M:%S")
        
        html = f"<h1>Adatbázis Ellenőrzési Jelentés: ID Eltérések</h1>"
        html += f"<p><i>Generálva: {timestamp}</i></p>"
        
        if not mismatches:
            html += "<p style='color: green; font-weight: bold;'>Nem található ID eltérés a fájlnév és a mappaszerkezet között. Minden rendben!</p>"
            return html

        html += f"<p style='color: red; font-weight: bold;'>Figyelem! {len(mismatches)} db eltérés található:</p>"
        html += "<table border='1' cellpadding='5' style='border-collapse: collapse; width: 100%;'>"
        html += "<tr style='background-color: #f2f2f2;'><th>Mappa Útvonal</th><th>Várt ID (mappa alapján)</th><th>Tényleges Fájlnév</th></tr>"
        
        for error in mismatches:
             html += f"<tr><td>{error['path']}</td><td>{error['expected_id']}</td><td style='color: red;'>{error['actual_filename']}</td></tr>"
        html += "</table>"
        
        return html

    def _check_for_duplicate_ids(self) -> Dict[str, List[str]]:
        """
        Végigpásztázza a termékkönyvtárat, és megkeresi azokat a termék ID-kat,
        amelyek több helyen is előfordulnak.
        Visszaad egy szótárat, ahol a kulcs a duplikált ID, az érték pedig a
        hozzá tartozó kategória-útvonalak listája.
        """
        self._log(logging.INFO, "Duplikált ID-k keresése a fájlrendszerben...")
        
        id_locations = collections.defaultdict(list)
        
        if not self._base_product_dir.exists():
            return {}

        # Végigmegyünk az összes JSON fájlon a termékkönyvtárban
        for json_file_path in self._base_product_dir.rglob('*.json'):
            try:
                with open(json_file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                product_id = data.get('id')
                if product_id:
                    # A kategória-útvonalat a mappa szerkezetéből olvassuk ki
                    relative_path = json_file_path.parent.relative_to(self._base_product_dir)
                    # A 'product_*' részt levágjuk a végéről
                    category_parts = relative_path.parts[:-1]
                    # Formázzuk az útvonalat olvashatóvá
                    category_str = " > ".join(part.replace('-', ' ').title() for part in category_parts)
                    
                    id_locations[product_id].append(category_str or "Gyökér")

            except (json.JSONDecodeError, KeyError) as e:
                self._log(logging.WARNING, f"Hiba a(z) '{json_file_path}' fájl olvasásakor: {e}")
                continue
        
        # Kiszűrjük azokat az ID-kat, amelyek csak egyszer fordultak elő
        duplicates = {id: paths for id, paths in id_locations.items() if len(paths) > 1}
        
        self._log(logging.INFO, f"{len(duplicates)} db duplikált ID található.")
        return duplicates

    def _generate_duplicate_id_report_html(self, duplicates: Dict[str, List[str]]) -> str:
        """HTML riportot generál a duplikált ID-kről."""
        timestamp = datetime.now().strftime("%Y. %m. %d. %H:%M:%S")
        
        html = f"<h1>Adatbázis Ellenőrzési Jelentés: Duplikált ID-k</h1>"
        html += f"<p><i>Generálva: {timestamp}</i></p>"
        
        if not duplicates:
            html += "<p style='color: green; font-weight: bold;'>Nem található duplikált termék ID az adatbázisban. Minden rendben!</p>"
            return html

        html += f"<p style='color: red; font-weight: bold;'>Figyelem! {len(duplicates)} db termék ID több helyen is előfordul:</p>"
        html += "<table border='1' cellpadding='5' style='border-collapse: collapse; width: 100%;'>"
        html += "<tr style='background-color: #f2f2f2;'><th>Duplikált Termék ID</th><th>Előfordulások (Kategória útvonalak)</th></tr>"
        
        for product_id, paths in duplicates.items():
             paths_html = "<br>".join(f"- {path}" for path in sorted(paths))
             html += f"<tr><td style='font-weight: bold;'>{product_id}</td><td>{paths_html}</td></tr>"
        html += "</table>"
        
        return html

    # <<< MÓDOSÍTÁS: Frissítsd a `run_database_integrity_check_sync` metódust >>>
    @Slot(str)
    def run_database_integrity_check_sync(self, check_type: str):
        """Elindítja a kért ADATBÁZIS-OLDALI ellenőrzési feladatot."""
        # --- JAVÍTÁS: A hibát okozó aszinkron hívás eltávolítva ---
        # A server_client_sync_check logikát most már a MainController kezeli.
        
        if check_type == "duplicate_id_check":
            duplicates = self._check_for_duplicate_ids()
            report_html = self._generate_duplicate_id_report_html(duplicates)
            self.reportGenerated.emit(report_html)
        elif check_type == "full_list_report":
            all_products = self.get_all_products()
            report_html = self._generate_full_list_report_html(all_products)
            self.reportGenerated.emit(report_html)
        else:
            self._log(logging.WARNING, f"A ProductManager által nem kezelt ellenőrzési típus: '{check_type}'")
            # Nem bocsátunk ki hibajelzést, mert ezt a MainControllernek kell kezelnie.

    def _update_product_category_from_title(self, product: Product, title: str):
        """
        Frissíti a megadott termék kategória-adatait a címe alapján.
        Biztosítja, hogy a 'product_type' és 'product_type_slug' mezők helyesen legyenek kitöltve.
        """
        best_match = self.category_manager.find_best_category_by_item_name(title)
        if best_match:
            main_cat_str, sub_cat_str, item_type_str = best_match
            try:
                main_cat = MainCategory(main_cat_str)
                product.main_category = main_cat
                product.main_category_slug = main_cat.to_slug()
                product.sub_category_slug = _sanitize_for_slug(sub_cat_str)
                
                # A kulcsfontosságú javítás:
                # Mindig a teljes nevet ('item_type_str') adjuk a 'product_type'-nak,
                # és a slugosított verziót a 'product_type_slug'-nak.
                product.product_type = item_type_str
                product.product_type_slug = _sanitize_for_slug(item_type_str)
                
                product.needs_manual_category_review = False
            except ValueError:
                # Ha a konverzió hibás, a termék marad felülvizsgálandó
                product.needs_manual_category_review = True
        else:
            product.needs_manual_category_review = True

    def _generate_full_list_report_html(self, all_products: List[Product]) -> str:
        """HTML riportot generál a teljes termékadatbázisról, a kért formázásokkal."""
        timestamp = datetime.now().strftime("%Y. %m. %d. %H:%M:%S")
        
        html = f"<h1>Teljes Adatbázis Riport</h1>"
        html += f"<p><i>Generálva: {timestamp}</i></p>"
        html += f"<p><b>Termékek száma összesen:</b> {len(all_products)}</p>"
        
        if not all_products:
            html += "<p>Az adatbázis üres.</p>"
            return html

        sorted_products = sorted(all_products, key=lambda p: p.id)

        html += "<table border='1' cellpadding='5' style='border-collapse: collapse; width: 100%; font-size: 9pt;'>"
        html += """
            <tr style='background-color: #f2f2f2; font-weight: bold;'>
                <th>ID</th>
                <th>Név</th>
                <th>Ár</th>
                <th>Főkategória</th>
                <th>Alkategória</th>
                <th>Típus</th>
                <th>Létrehozva</th>
                <th>Eladva?</th>
                <th>Feltöltendő?</th>
                <th title='Eredeti képek száma'>Orig.</th>
                <th title='Transzparens képek száma'>Trans.</th>
                <th title='Szerkesztett (feltöltendő) képek száma'>Mixed</th>
            </tr>
        """
        
        for product in sorted_products:
            price_str = f"{int(product.price_numeric):,} Ft".replace(',', ' ') if product.price_numeric is not None else "N/A"
            created_str = product.created_at.strftime("%Y-%m-%d %H:%M") if product.created_at else "N/A"
            is_sold_str = "<span style='color: red; font-weight: bold;'>Igen</span>" if product.is_sold else "Nem"
            needs_upload_str = "<span style='color: red;'>Igen</span>" if product.needs_upload else "Nem"
            sub_cat_name = next((name for name, slug in self.category_manager.get_sub_categories_with_slugs_for_main(product.main_category) if slug == product.sub_category_slug), product.sub_category_slug)

            # --- MÓDOSÍTÁS: A stílusdefiníciók frissítése a kérés alapján ---
            row_style = " style='background-color: #EFEFEF; color: #777;'" if product.is_sold else ""
            category_style = " style='background-color: #FFDDDD; color: red;'" if product.main_category == MainCategory.UNCATEGORIZED and not product.is_sold else ""
            
            # Közös stílus a piros kiemeléshez
            red_bold_style = " style='color: red; font-weight: bold;'"

            # Stílusok alkalmazása, ha a képek száma nulla (és a termék nem eladott)
            original_style = red_bold_style if product.num_original_images == 0 and not product.is_sold else ""
            transparent_style = red_bold_style if product.num_transparent_images == 0 and not product.is_sold else ""
            mixed_style = red_bold_style if product.num_mixed_images == 0 and not product.is_sold else ""
            # --- MÓDOSÍTÁS VÉGE ---

            html += f"<tr{row_style}>"
            html += f"<td>{product.id}</td>"
            html += f"<td>{product.title}</td>"
            html += f"<td>{price_str}</td>"
            html += f"<td{category_style}>{product.main_category.display_name}</td>"
            html += f"<td{category_style}>{sub_cat_name}</td>"
            html += f"<td{category_style}>{product.product_type}</td>"
            html += f"<td>{created_str}</td>"
            html += f"<td>{is_sold_str}</td>"
            html += f"<td>{needs_upload_str}</td>"
            
            # --- MÓDOSÍTÁS: A frissített stílusok alkalmazása a cellákon ---
            html += f"<td align='center'{original_style}>{product.num_original_images}</td>"
            html += f"<td align='center'{transparent_style}>{product.num_transparent_images}</td>"
            html += f"<td align='center'{mixed_style}>{product.num_mixed_images}</td>"
            # --- MÓDOSÍTÁS VÉGE ---

            html += "</tr>"
            
        html += "</table>"
        
        return html
    
    async def _run_server_client_sync_check_async(self):
        """
        Aszinkron metódus, ami elvégzi a kliens és szerver közötti összehasonlítást
        és legenerálja a riportot.
        """
        try:
            # 1. Lekérjük a helyi ID-kat (ez gyors, szinkron művelet)
            local_ids = set(self._products.keys())
            
            # 2. Lekérjük a távoli ID-kat az FtpManager segítségével (ez a lassú, hálózati művelet)
            remote_ids = await self.ftp_manager._get_all_remote_product_ids_async()
            
            if remote_ids is None:
                # Hiba történt az FTP művelet során, a riport ezt jelezni fogja
                report_html = self._generate_sync_report_html(set(), set(), error=True)
                self.reportGenerated.emit(report_html)
                return

            # 3. Kiszámoljuk a két halmaz különbségét
            local_only = local_ids - remote_ids
            remote_only = remote_ids - local_ids

            # 4. Legeneráljuk és kibocsátjuk a riportot
            report_html = self._generate_sync_report_html(local_only, remote_only)
            self.reportGenerated.emit(report_html)

        except Exception as e:
            self._log(logging.CRITICAL, f"Váratlan hiba a szerver-kliens szinkronizáció ellenőrzésekor: {e}", exc_info=True)
            error_report = f"<h1>Hiba</h1><p>Váratlan hiba történt az ellenőrzés során: {e}</p>"
            self.reportGenerated.emit(error_report)

    def get_all_product_ids(self) -> set:
        """Visszaadja az összes memóriában lévő termék ID-ját egy set-ben."""
        return set(self._products.keys())

    # --- MÓDOSÍTÁS: A metódus publikussá tétele és átnevezése ---
    def generate_sync_report_html(self, local_only: set, remote_only: set, error: bool = False) -> str:
        """HTML riportot generál a szerver-kliens szinkronizációs eltérésekről."""
        timestamp = datetime.now().strftime("%Y. %m. %d. %H:%M:%S")
        
        html = f"<h1>Szerver-Kliens Szinkronizációs Jelentés</h1>"
        html += f"<p><i>Generálva: {timestamp}</i></p><hr>"

        if error:
            html += "<h2 style='color: red;'>Hiba történt</h2>"
            html += "<p>Nem sikerült lekérdezni az adatokat a szerverről. Ellenőrizze az FTP kapcsolatot és a beállításokat.</p>"
            return html

        if not local_only and not remote_only:
            html += "<h2 style='color: green;'>Minden rendben!</h2>"
            html += "<p>A kliens oldali adatbázis és a szerveren található termékmappák szinkronban vannak.</p>"
            return html

        html += f"<h2>Kliensen létező, de a szerveren hiányzó termékek ({len(local_only)} db)</h2>"
        if local_only:
            html += "<p>Ezek a termékek valószínűleg még nincsenek feltöltve, vagy a feltöltésük sikertelen volt.</p>"
            html += "<table border='1' cellpadding='5' style='border-collapse: collapse; width: 100%;'>"
            html += "<tr style='background-color: #FFF3CD;'><th>ID</th><th>Név</th></tr>"
            for product_id in sorted(list(local_only)):
                product = self._products.get(product_id)
                product_name = product.title if product else "(Ismeretlen név)"
                html += f"<tr><td>{product_id}</td><td>{product_name}</td></tr>"
            html += "</table>"
        else:
            html += "<p>Nincs ilyen termék.</p>"
            
        html += "<br><hr><br>"

        html += f"<h2>Szerveren létező, de a kliensen hiányzó termékek ({len(remote_only)} db)</h2>"
        if remote_only:
            html += "<p>Ezek a termékek valószínűleg törölve lettek a kliensről, de a szerverről nem. Manuális törlésük javasolt a szerveren.</p>"
            html += "<table border='1' cellpadding='5' style='border-collapse: collapse; width: 50%;'>"
            html += "<tr style='background-color: #D6EAF8;'><th>ID</th></tr>"
            for product_id in sorted(list(remote_only)):
                html += f"<tr><td>{product_id}</td></tr>"
            html += "</table>"
        else:
            html += "<p>Nincs ilyen termék.</p>"

        return html

    def get_mixed_image_paths(self, product_id: str) -> List[Path]:
        """
        Visszaadja a 'mixed_' előtagú képek teljes elérési útvonalát egy adott termékhez.
        """
        product = self.get_product_by_id(product_id)
        if not product:
            self._log(logging.WARNING, f"A '{product_id}' ID-jű termék nem található a képútvonalak lekérdezéséhez.")
            return []

        image_dir = self._get_product_path_from_product_object(product) / "images"
        if not image_dir.exists() or not image_dir.is_dir():
            return []

        mixed_images = [
            f for f in image_dir.iterdir()
            if f.is_file() and f.name.lower().startswith("mixed_")
        ]
        
        # Sorbarendezés a sorszám alapján a fájlnévben
        mixed_images.sort(key=lambda p: int(re.search(r'_(\d+)\.', p.name).group(1)) if re.search(r'_(\d+)\.', p.name) else 0)
        
        return mixed_images
    
    def export_product_folder_sync(self, product_id: str) -> Tuple[bool, str]:
        """
        A megadott termék teljes mappáját (JSON, képek, stb.) a beállításokban
        megadott letöltési könyvtárba másolja.

        Returns:
            Egy (siker, üzenet) tuple-t ad vissza.
        """
        try:
            # 1. Termék és útvonalak lekérdezése
            product = self.get_product_by_id(product_id)
            if not product:
                raise FileNotFoundError(f"A(z) '{product_id}' ID-jű termék nem található.")

            source_path = self._get_product_path_from_product_object(product)
            if not source_path.exists() or not source_path.is_dir():
                raise FileNotFoundError(f"A forrásmappa nem létezik: {source_path}")

            download_folder_str = self.settings_manager.get_setting("client_settings.download_folder")
            if not download_folder_str or not os.path.isdir(download_folder_str):
                raise IOError("Érvénytelen letöltési mappa.")

            # 2. Cél útvonal létrehozása
            destination_path = Path(download_folder_str) / source_path.name
            
            # 3. Ellenőrzés, hogy a célmappa létezik-e már
            if destination_path.exists():
                return (False, f"Hiba: A célmappa már létezik: {destination_path}")

            # 4. Másolás
            shutil.copytree(source_path, destination_path)

            self._log(logging.INFO, f"Termékmappa sikeresen exportálva ide: {destination_path}")
            return (True, f"'{product.title}' sikeresen exportálva.")

        except (FileNotFoundError, IOError, shutil.Error, Exception) as e:
            message = f"Hiba az exportálás során: {e}"
            self._log(logging.ERROR, message, exc_info=True)
            return (False, message)
        
    def generate_server_duplicate_report_html(self, duplicates: Optional[Dict[str, List[str]]]) -> str:
        """HTML riportot generál a szerveren talált duplikált ID-kről."""
        timestamp = datetime.now().strftime("%Y. %m. %d. %H:%M:%S")
        
        html = f"<h1>Szerveroldali Duplikátum Ellenőrzési Jelentés</h1>"
        html += f"<p><i>Generálva: {timestamp}</i></p><hr>"
        
        if duplicates is None:
            html += "<h2 style='color: red;'>Hiba történt</h2>"
            html += "<p>Nem sikerült lekérdezni az adatokat a szerverről. Ellenőrizze a kapcsolatot és a naplófájlokat.</p>"
            return html

        if not duplicates:
            html += "<h2 style='color: green;'>Minden rendben!</h2>"
            html += "<p>Nem található duplikált termék ID a szerveren.</p>"
            return html

        html += f"<h2 style='color: red;'>Figyelem! {len(duplicates)} db duplikált termék ID található:</h2>"
        html += "<p>Az alábbi termékek több kategóriában is szerepelnek a szerveren, ami hibát okozhat.</p>"
        html += "<table border='1' cellpadding='5' style='border-collapse: collapse; width: 100%;'>"
        html += "<tr style='background-color: #f2f2f2;'><th>Duplikált Termék ID</th><th>Előfordulások (Útvonalak a szerveren)</th></tr>"
        
        for product_id, paths in sorted(duplicates.items()):
             paths_html = "<br>".join(f"- {path}" for path in sorted(paths))
             html += f"<tr><td style='font-weight: bold;'>{product_id}</td><td>{paths_html}</td></tr>"
        html += "</table>"
        
        return html
    
    def check_if_product_exists(self, title: str, price: float) -> bool:
        """
        Ellenőrzi, hogy létezik-e már aktív (nem eladott) termék a megadott
        címmel és árral. A cím-összehasonlítás nem kis- és nagybetű érzékeny.

        Args:
            title (str): A keresendő termék címe.
            price (float): A keresendő termék ára.

        Returns:
            bool: Igaz, ha már létezik ilyen termék, egyébként hamis.
        """
        normalized_title = title.strip().lower()
        
        for product in self._products.values():
            # Csak az aktív termékek között keresünk
            if not product.is_sold:
                # Cím- és ár-összehasonlítás
                if (product.title.strip().lower() == normalized_title and
                        abs(product.price_numeric - price) < 0.01): # Lebegőpontos számok biztonságos összehasonlítása
                    self._log(logging.WARNING, f"Duplikátumot talált! Létező ID: {product.id}, Név: '{title}', Ár: {price}")
                    return True
        return False