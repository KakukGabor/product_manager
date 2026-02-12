# automation/sites/gs_core/gs_form_filler.py
import logging
import os
import re
import tempfile  ### ÚJ IMPORT ###
import shutil    ### ÚJ IMPORT ###
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable, Tuple

from PySide6.QtGui import QImage ### ÚJ IMPORT ###
from playwright.async_api import Page, TimeoutError

from config.gs_category_mapping import GS_CATEGORY_MAPPING
from config.gs_style_mapping import get_gs_style_from_title, get_gs_period_from_style
from managers.settings_manager import SettingsManager
from models.product_model import MainCategory


class GaleriaSavariaFormFiller:
    """
    Ez az osztály felelős a Galéria Savaria új termék feltöltési űrlapjának
    automatizált kitöltéséért, kisebb, jól definiált metódusokra bontva.
    """

    def __init__(self,
                 page: Page,
                 settings_manager: SettingsManager,
                 log_callback: Callable[..., None],
                 app_root_dir: str):
        self.page = page
        self.settings_manager = settings_manager
        self.log = log_callback
        self.app_root_dir = app_root_dir

        # Beállítások előre betöltése a hatékonyság érdekében
        self.default_navigation_timeout = self.settings_manager.get_setting("browser_settings.default_navigation_timeout_ms", 30000)
        self.element_visibility_timeout = self.settings_manager.get_setting("browser_settings.element_visibility_timeout_ms", 5000)
        self.post_action_delay = self.settings_manager.get_setting("browser_settings.post_action_delay_ms", 500)
        self.new_product_url = self.settings_manager.get_setting("site_configs.galeria_savaria.new_product_url")

    async def _fill_main_details(self, product_data: Dict[str, Any]) -> None:
        """Kitölti a termék címét és leírását, a leírást formázás nélkül beillesztve."""
        await self.page.fill('input#title', product_data.get("title", ""), timeout=self.element_visibility_timeout)
        self.log(logging.INFO, f"Cím kitöltve: '{product_data.get('title')}'", color_override="processing")

        original_description = product_data.get("description", "")
        appendix = "\n\nKérem nézze meg a többi hirdetésemet is!"
        full_description = f"{original_description}{appendix}"

        description_selector = 'div[contenteditable="true"]'

        try:
            await self.page.evaluate("text => navigator.clipboard.writeText(text)", full_description)
            await self.page.focus(description_selector)
            await self.page.keyboard.press("Control+V")
            self.log(logging.INFO, "Leírás beillesztve (formázás nélkül).", color_override="processing")
        except Exception as e:
            self.log(logging.WARNING, f"A vágólapos beillesztés nem sikerült ({e}), a leírás közvetlen kitöltése következik.", color_override="orange")
            await self.page.fill(description_selector, full_description, timeout=self.element_visibility_timeout)
            self.log(logging.INFO, "Leírás kitöltve (közvetlen módszerrel).", color_override="processing")

    async def _select_categories_and_attributes(self, product_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        messages = []
        overall_success = True
        third_level_filled = False

        try:
            await self.page.click('text=Kategóriaválasztó', timeout=self.element_visibility_timeout)
            await self.page.wait_for_selector('select#select-cat1', state='visible', timeout=self.element_visibility_timeout)
            
            app_main_cat_name = product_data.get("main_category_name")
            app_sub_cat_name = product_data.get("sub_category_name")
            app_prod_type_name = product_data.get("product_type_name")
            mapping_key = (app_main_cat_name, app_sub_cat_name, app_prod_type_name)
            gs_categories = GS_CATEGORY_MAPPING.get(mapping_key)

            if not gs_categories:
                raise ValueError(f"Nincs GS kategória leképezés a(z) {mapping_key} app kategóriához.")
            
            gs_first_level_cat_text, gs_second_level_cat_text = gs_categories
            await self.page.select_option('select#select-cat1', label=gs_first_level_cat_text, timeout=self.element_visibility_timeout)
            self.log(logging.INFO, f"1. szintű kategória '{gs_first_level_cat_text}' kiválasztva.", color_override="processing")

            if gs_second_level_cat_text:
                await self.page.wait_for_selector('select#select-cat2 option:not([value=""]):not([value="0"])', state='visible', timeout=self.element_visibility_timeout)
                await self.page.select_option('select#select-cat2', label=gs_second_level_cat_text, timeout=self.element_visibility_timeout)
                self.log(logging.INFO, f"2. szintű kategória '{gs_second_level_cat_text}' kiválasztva.", color_override="processing")
            
            await self.page.wait_for_load_state('networkidle', timeout=self.default_navigation_timeout)
            messages.append("Alap kategóriák sikeresen beállítva.")
        except Exception as e:
            msg = f"Hiba az alapvető GS kategóriák beállításakor: {e}. Manuális ellenőrzés szükséges!"
            messages.append(msg)
            self.log(logging.ERROR, msg, exc_info=True, color_override="red")
            return False, messages

        try:
            product_title = product_data.get("title", "")
            target_style_name = get_gs_style_from_title(product_title)
            target_period_name = get_gs_period_from_style(target_style_name)
            
            await self.page.select_option('select#select-cat3', label=target_period_name, timeout=self.element_visibility_timeout)
            self.log(logging.INFO, f"Korszak '{target_period_name}' kiválasztva.", color_override="processing")
            await self.page.wait_for_load_state('networkidle', timeout=self.default_navigation_timeout)

            await self.page.click('div.select:has(strong:has-text("Stílus:")) div.custom_select', timeout=self.element_visibility_timeout)
            style_option_selector = f'a:has-text("{target_style_name}")'
            if target_style_name == "modern": style_option_selector = 'a[data-value="25"]:has-text("modern")'
            elif target_style_name == "Neo-": style_option_selector = 'a:has-text("Neo-")'
            await self.page.click(style_option_selector, timeout=self.element_visibility_timeout)
            self.log(logging.INFO, f"Stílus '{target_style_name}' kiválasztva.", color_override="processing")
            await self.page.wait_for_load_state('networkidle', timeout=self.default_navigation_timeout)
            messages.append("Korszak és Stílus sikeresen beállítva.")
            third_level_filled = True
        except Exception as e:
            msg = f"Figyelem: Nem sikerült a Korszak és Stílus beállítása! Manuális ellenőrzés szükséges."
            messages.append(msg)
            self.log(logging.WARNING, msg, exc_info=True)

        if third_level_filled:
            try:
                main_cat_name = product_data.get("main_category_name")
                condition_map = {
                    MainCategory.ANTIQUE_FURNITURE.display_name: ("restaurált", "38"),
                    MainCategory.HOME_ACCESSORY.display_name: ("korának megfelelő", "37"),
                }
                if main_cat_name in condition_map:
                    cond_name, cond_val = condition_map[main_cat_name]
                    await self.page.click('div.select:has(strong:has-text("Állapot:")) div.custom_select', timeout=self.element_visibility_timeout)
                    await self.page.click(f'a[data-value="{cond_val}"]:has-text("{cond_name}")', timeout=self.element_visibility_timeout)
                    self.log(logging.INFO, f"Állapot '{cond_name}' kiválasztva.", color_override="processing")
                    messages.append("Állapot sikeresen beállítva.")
                else:
                    messages.append(f"Figyelem: Állapot beállítása kihagyva (ismeretlen fő kategória: '{main_cat_name}').")
            except Exception as e:
                messages.append(f"Figyelem: Hiba az Állapot beállítása során ({e}). Manuális ellenőrzés szükséges.")

            try:
                await self.page.click('div.select:has(strong:has-text("Eredetiség:")) div.custom_select', timeout=self.element_visibility_timeout)
                await self.page.click('a[data-value="41"]:has-text("eredeti")', timeout=self.element_visibility_timeout)
                self.log(logging.INFO, "Eredetiség 'eredeti' kiválasztva.", color_override="processing")
                await self.page.wait_for_load_state('networkidle', timeout=self.default_navigation_timeout)
                messages.append("Eredetiség sikeresen beállítva.")
            except Exception as e:
                messages.append(f"Figyelem: Hiba az Eredetiség beállítása során ({e}). Manuális ellenőrzés szükséges.")
        else:
            messages.append("Figyelem: Állapot és Eredetiség beállítása kihagyva a Korszak/Stílus hiba miatt.")

        return overall_success, messages

    async def _fill_price_and_shipping(self, product_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        messages = []
        success = True
        
        try:
            await self.page.click('label:has-text("Fix ár") span.label-text', timeout=self.element_visibility_timeout)
            price_str = str(int(product_data.get("price_numeric", 0)))
            await self.page.fill('input#fp_prod_price', price_str, timeout=self.element_visibility_timeout)
            self.log(logging.INFO, f"Ár kitöltve: '{price_str}'", color_override="processing")
            
            await self.page.click('label:has-text("Nem, nem várok ajánlatokat") span.label-text', timeout=self.element_visibility_timeout)
            await self.page.click('label:has-text("Szállítási sablont használok") span.label-text', timeout=self.element_visibility_timeout)
            await self.page.click('div.use_shipping_wrapper a.btn.color_gray:has-text("Sablon kiválasztása")', timeout=self.element_visibility_timeout)
            await self.page.wait_for_selector('div.dflex.aicenter.jcspacebetween.ml10.pl10 a.btn.color_black.__modal:has-text("Választás")', state='visible', timeout=self.element_visibility_timeout)
            await self.page.click('div.dflex.aicenter.jcspacebetween.ml10.pl10 a.btn.color_black.__modal:has-text("Választás")', timeout=self.element_visibility_timeout)
            await self.page.wait_for_load_state('networkidle', timeout=self.default_navigation_timeout)
            await self.page.click('label:has-text("Készpénz") span.label-text', timeout=self.element_visibility_timeout)
            messages.append("Ár, szállítás és fizetés sikeresen beállítva.")
        except Exception as e:
            msg = f"Hiba az ár/szállítás beállításakor: {e}."
            messages.append(msg)
            self.log(logging.ERROR, msg, exc_info=True)
            success = False
        
        return success, messages
    
    ### TELJESEN ÚJ, JAVÍTOTT METÓDUS KEZDETE ###
    async def _upload_images(self) -> Tuple[bool, str]:
        """
        Megkeresi a 'mixed_*.webp' képeket a termékmappában, ideiglenesen átkonvertálja
        őket JPG formátumba, feltölti, majd letakarítja az ideiglenes fájlokat.
        """
        temp_upload_dir = None
        try:
            # 1. Forrás képek megkeresése (a végleges helyükről, WEBP formátumban)
            # A 'tmp_images' mappát már az ImageGalleryWidget kezeli új terméknél.
            source_image_dir = Path(self.app_root_dir) / "app_data_storage" / "tmp_images"
            
            webp_images = [f for f in source_image_dir.iterdir() if f.is_file() and f.name.lower().startswith("mixed_") and f.suffix.lower() == ".webp"]
            
            if not webp_images:
                self.log(logging.WARNING, "Nem található 'mixed_*.webp' kép a feltöltéshez.")
                return True, "(Nem volt feltöltendő kép.)"
            
            webp_images.sort(key=lambda p: int(re.search(r'_(\d+)\.', os.path.basename(p)).group(1)) or 0)
            self.log(logging.INFO, f"{len(webp_images)} db kép előkészítése JPG konverzióra...", color_override="processing")

            # 2. Ideiglenes mappa létrehozása a JPG fájloknak
            temp_upload_dir = Path(tempfile.mkdtemp(prefix="gs_upload_"))
            self.log(logging.DEBUG, f"Ideiglenes feltöltési mappa létrehozva: {temp_upload_dir}")
            
            temp_jpg_paths = []
            for webp_path in webp_images:
                # 3. Konverzió QImage segítségével
                image = QImage(str(webp_path))
                if image.isNull():
                    self.log(logging.WARNING, f"Nem sikerült betölteni a képet a konverzióhoz: {webp_path.name}")
                    continue
                
                # Új JPG fájlnév létrehozása az ideiglenes mappában
                jpg_filename = webp_path.with_suffix('.jpg').name
                temp_jpg_path = temp_upload_dir / jpg_filename
                
                # Mentés JPG formátumban, 90-es minőséggel
                if image.save(str(temp_jpg_path), "JPG", 90):
                    temp_jpg_paths.append(str(temp_jpg_path))
                else:
                    self.log(logging.WARNING, f"A JPG mentés sikertelen: {temp_jpg_path.name}")

            if not temp_jpg_paths:
                raise IOError("Nem sikerült egyetlen képet sem átkonvertálni JPG formátumba.")

            # 4. Feltöltés a konvertált JPG fájlokkal
            self.log(logging.INFO, f"{len(temp_jpg_paths)} db ideiglenes JPG kép feltöltése...", color_override="processing")
            async with self.page.expect_file_chooser(timeout=self.element_visibility_timeout) as fc_info:
                await self.page.click('button#html_upload', timeout=self.element_visibility_timeout)
            file_chooser = await fc_info.value
            await file_chooser.set_files(temp_jpg_paths)

            # Várakozás a feltöltés befejeződésére
            last_image_slot = len(temp_jpg_paths)
            key_input_selector = f'div.image-wrapper:has(input[name="fp_prod[image_{last_image_slot}]"]) input.key'
            await self.page.wait_for_function(
                f"document.querySelector('{key_input_selector}') && document.querySelector('{key_input_selector}').value !== ''",
                timeout=self.element_visibility_timeout * 15 
            )
            self.log(logging.INFO, "Minden kép sikeresen feltöltve.", color_override="processing")
            return True, "(Képek sikeresen feltöltve.)"

        except Exception as e:
            msg = f"Hiba történt a képek feltöltésekor: {e}"
            self.log(logging.ERROR, msg, exc_info=True)
            return False, f"({msg})"
        
        finally:
            # 5. Takarítás: Az ideiglenes mappa törlése, BÁRMI történjék is
            if temp_upload_dir and temp_upload_dir.exists():
                shutil.rmtree(temp_upload_dir)
                self.log(logging.DEBUG, f"Ideiglenes feltöltési mappa törölve: {temp_upload_dir}")
    ### TELJESEN ÚJ, JAVÍTOTT METÓDUS VÉGE ###

    async def fill_form(self, product_data: Dict[str, Any]) -> Tuple[bool, str]:
        overall_success = True
        final_message_parts = []
        
        try:
            await self._fill_main_details(product_data)

            cat_success, cat_messages = await self._select_categories_and_attributes(product_data)
            final_message_parts.extend(cat_messages)
            if not cat_success:
                raise ValueError("A termék alap kategóriáinak beállítása sikertelen, a folyamat nem folytatható.")

            price_success, price_messages = await self._fill_price_and_shipping(product_data)
            final_message_parts.extend(price_messages)
            if not price_success:
                raise ValueError("Az ár vagy a szállítási beállítások kitöltése sikertelen, a folyamat nem folytatható.")
            
            # A javított képfeltöltő metódus hívása
            img_success, img_message = await self._upload_images()
            final_message_parts.insert(0, img_message)

            has_warnings = any("Hiba" in msg or "Figyelem" in msg for msg in final_message_parts)
            final_status_base = "GS űrlap kitöltése figyelmeztetésekkel fejeződött be. " if has_warnings else "GS űrlap kitöltése befejeződött. "
            final_message = (
                f"{final_status_base}"
                "Manuálisan ellenőrizze az oldalt, majd kattintson a Feltöltés gombra, "
                "végül az alkalmazásban az 'Érvényesítés' gombra."
            )
            self.log(logging.WARNING if has_warnings else logging.INFO, final_message)
            
            return overall_success, final_message
        
        except (ValueError, TimeoutError) as e:
            message = f"Kritikus hiba a GS űrlap kitöltésekor: {e}"
            self.log(logging.ERROR, message, exc_info=True)
            return False, message
        except Exception as e:
            message = f"Váratlan, általános hiba a GS űrlap kitöltésekor: {e}"
            self.log(logging.CRITICAL, message, exc_info=True)
            return False, message