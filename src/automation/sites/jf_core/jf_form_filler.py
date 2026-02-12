# automation/sites/jf_core/jf_form_filler.py
import logging
import os
from typing import Dict, Any, Tuple, Callable

from playwright.async_api import Page, TimeoutError, Locator
from managers.settings_manager import SettingsManager
from config.jf_category_mapping import JF_CATEGORY_MAPPING
from config.jf_attribute_mapping import JF_ATTRIBUTE_MAPPING

class JofogasFormFiller:
    TITLE_SELECTOR = "#hf_subject"
    NEXT_BUTTON_SELECTOR = 'button[data-test="ai-next-2"]'
    CATEGORY_LEVEL1_CONTAINER_SELECTOR = 'ul[data-test="category-selector-category-1"]'
    CATEGORY_LEVEL2_CONTAINER_SELECTOR = 'ul[data-test="category-selector-category-2"]'
    CATEGORY_LEVEL3_CONTAINER_SELECTOR = 'ul[data-test="category-selector-category-3"]'
    OFFER_BUTTON_SELECTOR = 'div.btn:has(span:text-is("Kínál"))'
    ATTRIBUTES_CONTAINER_SELECTOR = "#step3-params"
    COLOR_DROPDOWN_SELECTOR = "#hf_home_color_one, #hf_home_color_two"
    DESCRIPTION_SELECTOR = "#hf_body"
    PRICE_SELECTOR = "#hf_price"
    DELIVERY_ENABLED_CHECKBOX_SELECTOR = "#delivery_enabled"
    SHOW_PHONE_CHECKBOX_SELECTOR = "#hf_show_phone"
    ACCEPT_TERMS_CHECKBOX_SELECTOR = "#accept_terms"
    UPLOAD_IMAGE_INPUT_SELECTOR = "#upload-image"
    UPLOAD_LOADER_SELECTOR = "div.image-uploader-loader"

    def __init__(self, page: Page, settings_manager: SettingsManager, log_callback: Callable[..., None], app_root_dir: str):
        self.page = page
        self.settings_manager = settings_manager
        self.log = log_callback
        self.app_root_dir = app_root_dir
        self.element_visibility_timeout = self.settings_manager.get_setting("browser_settings.element_visibility_timeout_ms", 5000)
        self.network_idle_timeout = self.settings_manager.get_setting("browser_settings.default_navigation_timeout_ms", 30000)
        self.upload_completion_timeout = self.settings_manager.get_setting("browser_settings.upload_completion_timeout_ms", 60000)
        
        self.attribute_handlers = {
            "Állapot": self._select_condition_attribute,
            "Típus": self._select_type_attribute,
        }

    async def _scroll_to_top(self) -> None:
        self.log(logging.DEBUG, "Görgetés a lap tetejére...")
        await self.page.evaluate("window.scrollTo(0, 0)")

    async def fill_form(self, product_data: Dict[str, Any]) -> Tuple[bool, str]:
        try:
            self.log(logging.INFO, "Jófogás űrlapkitöltés megkezdése...", color_override="processing")
            
            await self._upload_images(product_data)
            
            await self._fill_title(product_data)
            await self._click_next_after_title()
            
            selected_jf_categories = await self._handle_category_selection(product_data)
            
            if selected_jf_categories and len(selected_jf_categories) > 2 and selected_jf_categories[2] != "Egyéb":
                await self._handle_attributes_selection(product_data, selected_jf_categories)
            else:
                self.log(logging.INFO, "Az 'Egyéb' kategória lett kiválasztva, a tulajdonságok panel kitöltése kihagyva.", color_override="processing")
            
            await self._fill_description(product_data)
            await self._fill_price(product_data)
            
            await self._disable_delivery_option()
            
            await self._check_show_phone()
            await self._check_accept_terms()
            
            await self._scroll_to_top()
            await self.page.wait_for_timeout(1000)
            
            final_message = "Képek feltöltve, űrlap sikeresen kitöltve, feltételek elfogadva."
            self.log(logging.INFO, final_message, color_override="green")
            return True, final_message
            
        except (ValueError, TimeoutError) as e:
            error_message = self._format_error_message(str(e))
            self.log(logging.ERROR, error_message, color_override="red")
            return False, error_message


    async def _fill_title(self, product_data: Dict[str, Any]) -> None:
        product_title = product_data.get("title", "")
        if not product_title: raise ValueError("A termék címe hiányzik.")
        full_title = f"Antik Bútor - {product_title}"
        await self.page.wait_for_selector(self.TITLE_SELECTOR, state="visible", timeout=self.element_visibility_timeout)
        await self.page.fill(self.TITLE_SELECTOR, full_title)
        self.log(logging.INFO, f"Cím kitöltve: '{full_title}'", color_override="processing")

    async def _click_next_after_title(self):
        await self.page.wait_for_selector(self.NEXT_BUTTON_SELECTOR, state="visible", timeout=self.element_visibility_timeout)
        await self.page.click(self.NEXT_BUTTON_SELECTOR)
        self.log(logging.INFO, "Kattintás a 'Tovább' gombra.", color_override="processing")

    async def _select_category(self, level: int, category_name: str, container_selector: str):
        self.log(logging.INFO, f"Kategória kiválasztása (Szint {level}): '{category_name}'...", color_override="processing")
        await self.page.wait_for_selector(container_selector, state="visible", timeout=self.network_idle_timeout)
        if level == 1:
            category_option_selector = f'a:has(span.focat-text:text-is("{category_name}"))'
        else:
            category_option_selector = f'div.btn:has(span:text-is("{category_name}"))'
        await self.page.locator(container_selector).locator(category_option_selector).click()
        self.log(logging.DEBUG, f"'{category_name}' kategóriára kattintva.")
        await self.page.wait_for_load_state("networkidle", timeout=self.network_idle_timeout)
        await self.page.wait_for_timeout(200)

    async def _handle_category_selection(self, product_data: Dict[str, Any]) -> Tuple[str, ...]:
        app_main_cat, app_sub_cat, app_prod_type = product_data.get("main_category_name"), product_data.get("sub_category_name"), product_data.get("product_type_name")
        mapping_key = (app_main_cat, app_sub_cat, app_prod_type)
        jf_categories = JF_CATEGORY_MAPPING.get(mapping_key)
        
        if not jf_categories:
            self.log(logging.WARNING, f"Nincs Jófogás kategória leképezés a(z) '{mapping_key}' számára. 'Egyéb' kategória kerül beállításra.")
            if app_main_cat == "Antik Bútor":
                jf_categories = ("Otthon, háztartás", "Bútor", "Egyéb")
            elif app_main_cat == "Lakáskiegészítő":
                jf_categories = ("Otthon, háztartás", "Lakáskiegészítők", "Egyéb")
            else:
                jf_categories = ("Otthon, háztartás", "Bútor", "Egyéb")
        
        jf_cat_level1, jf_cat_level2, jf_cat_level3 = jf_categories

        if jf_cat_level1: await self._select_category(1, jf_cat_level1, self.CATEGORY_LEVEL1_CONTAINER_SELECTOR)
        if jf_cat_level2: await self._select_category(2, jf_cat_level2, self.CATEGORY_LEVEL2_CONTAINER_SELECTOR)
        if jf_cat_level3: await self._select_category(3, jf_cat_level3, self.CATEGORY_LEVEL3_CONTAINER_SELECTOR)
        self.log(logging.INFO, "Kategóriák sikeresen kiválasztva.", color_override="green")

        await self.page.wait_for_selector(self.OFFER_BUTTON_SELECTOR, state="visible", timeout=self.element_visibility_timeout)
        await self.page.locator(self.OFFER_BUTTON_SELECTOR).click()
        await self.page.wait_for_load_state("networkidle", timeout=self.network_idle_timeout)
        await self.page.wait_for_timeout(200)
        self.log(logging.INFO, "'Kínál' gomb sikeresen megnyomva.", color_override="green")
        
        return jf_categories

    async def _handle_attributes_selection(self, product_data: Dict[str, Any], jf_categories: Tuple[str, ...]):
        self.log(logging.INFO, "Tulajdonságok kitöltése a konfiguráció alapján...", color_override="processing")
        await self.page.wait_for_selector(self.ATTRIBUTES_CONTAINER_SELECTOR, state="visible", timeout=self.element_visibility_timeout)
        
        jf_cat_level2, jf_cat_level3 = jf_categories[1], jf_categories[2]
        attribute_config = JF_ATTRIBUTE_MAPPING.get((jf_cat_level2, jf_cat_level3))

        if attribute_config:
            for attr_label, options in attribute_config.items():
                if isinstance(options, list) and not options:
                    self.log(logging.DEBUG, f"Attribútum '{attr_label}' kihagyva (szabad szöveges mező).")
                    continue
                try:
                    parent_locator = self.page.locator(f"div.form-group:has(label:has-text('{attr_label}'))")
                    await parent_locator.wait_for(state="visible", timeout=self.element_visibility_timeout)
                    
                    if attr_label == "Típus" and jf_cat_level3 == "Szekrények, szekrénysorok, polcok":
                        value_to_select = "antik bútor"
                        await parent_locator.locator("select").select_option(label=value_to_select)
                        self.log(logging.DEBUG, f"Attribútum 'Típus' beállítva (speciális szabály): '{value_to_select}'")
                        # Mivel ezt az attribútumot kezeltük, folytatjuk a következővel
                        continue

                    handler = self.attribute_handlers.get(attr_label)
                    if handler:
                        await handler(parent_locator, product_data, options)

                except TimeoutError:
                    self.log(logging.WARNING, f"Figyelem: Az '{attr_label}' attribútum panel nem jelent meg időben, a kitöltése kihagyva.")
                except Exception as e:
                    self.log(logging.ERROR, f"Hiba az '{attr_label}' attribútum kitöltésekor: {e}")
        
        await self._select_color_attribute(product_data, jf_categories)

    def _determine_condition_value(self, product_data: Dict[str, Any], options: list) -> str:
        app_main_cat = product_data.get("main_category_name")
        value_to_select = "Restaurált" if app_main_cat == "Antik Bútor" else "Korának megfelelő"
        return value_to_select if value_to_select in options else "Használt"

    async def _select_condition_attribute(self, parent_locator: Locator, product_data: Dict[str, Any], options: list):
        value_to_select = self._determine_condition_value(product_data, options)
        dropdown_locator = parent_locator.locator("select")
        await dropdown_locator.select_option(label=value_to_select)
        self.log(logging.DEBUG, f"Attribútum 'Állapot' beállítva: '{value_to_select}'")

    def _determine_type_value(self, product_data: Dict[str, Any], options: Any, jf_categories: Tuple[str, ...]) -> str | None:
        app_prod_type = product_data.get("product_type_name", "").lower()
        jf_cat_level3 = jf_categories[2]
        
        if isinstance(options, dict) and "special_handler" in options:
            product_title_lower = product_data.get("title", "").lower()
            for rule in options.get("rules", []):
                if rule.get("type") == "exact_product_type" and rule.get("if_product_type") == app_prod_type:
                    return rule.get("select")
                if rule.get("type") == "title_keyword":
                    if any(keyword.lower() in product_title_lower for keyword in rule.get("keywords", [])):
                        return rule.get("select")
            
            default_handler = options.get("default_handler")
            opts_list = options.get("options", [])
            if default_handler == "find_shortest_match":
                return next((opt for opt in sorted(opts_list, key=len) if app_prod_type in opt.lower()), options.get("default"))
            if default_handler == "find_shortest_match_reverse":
                return next((opt for opt in sorted(opts_list, key=len, reverse=True) if opt.lower() in app_prod_type), options.get("default"))
            return options.get("default")

        if isinstance(options, dict) and "default" in options:
            return options["default"]
        
        if jf_cat_level3 == "Szekrények, szekrénysorok, polcok" and "antik bútor" in options:
            return "antik bútor"

        opts_list = options.get("options", options) if isinstance(options, dict) else options
        return next((opt for opt in sorted(opts_list, key=len) if app_prod_type in opt.lower()), None)

    async def _select_type_attribute(self, parent_locator: Locator, product_data: Dict[str, Any], options: Any):
        jf_categories = (product_data.get("main_category_name"), product_data.get("sub_category_name"), product_data.get("product_type_name"))
        value_to_select = self._determine_type_value(product_data, options, jf_categories)
        
        if not value_to_select:
            self.log(logging.WARNING, f"Nem sikerült 'Típus' értéket találni a '{product_data.get('product_type_name')}' számára.")
            return

        is_button_selector = isinstance(options, dict) and "options" in options and isinstance(options["options"], dict) and "buttons" in options["options"]
        
        if is_button_selector:
            await parent_locator.locator(f"button:has-text('{value_to_select}')").click()
        else:
            await parent_locator.locator("select").select_option(label=value_to_select)
        
        self.log(logging.DEBUG, f"Attribútum 'Típus' beállítva: '{value_to_select}'")

    def _determine_color_to_select(self, product_data: Dict[str, Any], jf_categories: Tuple[str, ...]) -> str:
        app_main_cat_name = product_data.get("main_category_name")
        jf_cat_level3 = jf_categories[2]

        exceptions = {"Fotelek, kanapék, ülőgarnitúrák", "Konyhabútor", "Fürdőszoba bútor"}
        if jf_cat_level3 in exceptions:
            self.log(logging.DEBUG, f"Szín szabály: Kivétel '{jf_cat_level3}' kategória, 'Egyéb' szín kiválasztva.")
            return "Egyéb"

        if app_main_cat_name == "Antik Bútor":
            self.log(logging.DEBUG, "Szín szabály: 'Antik Bútor' főkategória, 'Barna' szín kiválasztva.")
            return "Barna"

        self.log(logging.DEBUG, "Szín szabály: Alapértelmezett eset, 'Egyéb' szín kiválasztva.")
        return "Egyéb"

    async def _select_color_attribute(self, product_data: Dict[str, Any], jf_categories: Tuple[str, ...]):
        try:
            color_dropdown_locator = self.page.locator(self.COLOR_DROPDOWN_SELECTOR)
            await color_dropdown_locator.wait_for(state="visible", timeout=self.element_visibility_timeout)
            
            value_to_select = self._determine_color_to_select(product_data, jf_categories)
            await color_dropdown_locator.select_option(label=value_to_select)
            self.log(logging.DEBUG, f"Attribútum 'Szín' sikeresen beállítva: '{value_to_select}'")

        except TimeoutError:
            self.log(logging.WARNING, "Figyelem: A 'Szín' legördülő menü nem jelent meg időben, a kitöltése kihagyva.")
        except Exception as e:
            self.log(logging.ERROR, f"Hiba a 'Szín' attribútum kitöltésekor: {e}")
            
    async def _fill_description(self, product_data: Dict[str, Any]) -> None:
        original_description = product_data.get("description")
        if not original_description:
            raise ValueError("A termék leírása hiányzik a forrásadatokból.")
        
        # --- MÓDOSÍTÁS KEZDETE ---
        appendix = "\n\nKérem nézze meg a többi hirdetésemet is!"
        full_description = f"{original_description}{appendix}"
        # --- MÓDOSÍTÁS VÉGE ---

        self.log(logging.INFO, "Leírás mező kitöltése...", color_override="processing")
        await self.page.wait_for_selector(self.DESCRIPTION_SELECTOR, state="visible", timeout=self.element_visibility_timeout)
        await self.page.fill(self.DESCRIPTION_SELECTOR, full_description)
    async def _fill_price(self, product_data: Dict[str, Any]) -> None:
        price = product_data.get("price_numeric")
        
        try:
            price_as_float = float(price)
        except (ValueError, TypeError):
            raise ValueError(f"Érvénytelen vagy hiányzó ár: '{price}'. Numerikus érték szükséges.")

        if price_as_float <= 0:
            raise ValueError(f"Érvénytelen ár: '{price}'. Csak nullánál nagyobb érték adható meg.")
        
        price_to_fill = str(int(price_as_float))

        self.log(logging.INFO, f"Ár mező kitöltése: '{price_to_fill}' Ft", color_override="processing")
       
        await self.page.locator(self.PRICE_SELECTOR).fill(price_to_fill)
     
        self.log(logging.INFO, f"Ár sikeresen beállítva: {price_to_fill} Ft", color_override="green")

    async def _disable_delivery_option(self) -> None:
        self.log(logging.INFO, "Szállítási opció ellenőrzése...", color_override="processing")
        try:
            checkbox_locator = self.page.locator(self.DELIVERY_ENABLED_CHECKBOX_SELECTOR)
            await checkbox_locator.wait_for(state="visible", timeout=self.element_visibility_timeout)
           
            await checkbox_locator.uncheck()
            self.log(logging.INFO, "A 'Házhozszállítás'-i opció sikeresen kikapcsolva.", color_override="green")

        except TimeoutError:
            self.log(logging.WARNING, "A szállítási opció jelölőnégyzete nem jelent meg, a lépés kihagyva.")
        except Exception as e:
            self.log(logging.ERROR, f"Hiba történt a szállítási opció kikapcsolása közben: {e}")

    async def _check_show_phone(self) -> None:
        self.log(logging.INFO, "'Telefon mutatása' bejelölése...", color_override="processing")
        await self.page.locator(self.SHOW_PHONE_CHECKBOX_SELECTOR).check()
        self.log(logging.DEBUG, "'Telefon mutatása' sikeresen bejelölve.")

    async def _check_accept_terms(self) -> None:
        self.log(logging.INFO, "'Felhasználási feltételek' elfogadása...", color_override="processing")
        await self.page.locator(self.ACCEPT_TERMS_CHECKBOX_SELECTOR).focus()
        await self.page.keyboard.press('Space')
        
        self.log(logging.INFO, "'Felhasználási feltételek' sikeresen elfogadva.", color_override="green")

    async def _upload_images(self, product_data: Dict[str, Any]) -> None:
        self.log(logging.INFO, "Képfeltöltés megkezdése...", color_override="processing")
        
        image_dir = ""
        product_id = product_data.get("id")

        if product_id:
            self.log(logging.DEBUG, f"Képek keresése meglévő termékhez (ID: {product_id}).")
            main_cat_slug = product_data.get("main_category_slug")
            sub_cat_slug = product_data.get("sub_category_slug")
            product_type_slug = product_data.get("product_type_slug") # <-- ÚJ VÁLTOZÓ
            
            if not all([main_cat_slug, sub_cat_slug, product_type_slug, product_id]):
                raise ValueError("A képfeltöltéshez szükséges adatok (id, slugs) hiányoznak a termékadatokból.")
            
            image_dir = os.path.join(
                self.app_root_dir,
                "app_data_storage",
                "processed",
                "product_library",
                main_cat_slug,
                sub_cat_slug,
                product_type_slug, # <-- EZ AZ ÚJ, FONTOS RÉSZ
                f"product_{product_id}",
                "images"
            )

        else:
            self.log(logging.DEBUG, "Képek keresése új termékhez az ideiglenes mappából.")
            image_dir = os.path.join(self.app_root_dir, "app_data_storage", "tmp_images")

        if not os.path.isdir(image_dir):
            self.log(logging.WARNING, f"A képmappa nem található, a feltöltés kihagyva: {image_dir}")
            return

        try:
            image_files = [f for f in os.listdir(image_dir) if f.startswith("original_")]
            if not image_files:
                self.log(logging.WARNING, f"Nincsenek 'original_' előtagú képek a mappában, a feltöltés kihagyva: {image_dir}")
                return
            
            image_paths = [os.path.join(image_dir, f) for f in image_files]
            self.log(logging.INFO, f"{len(image_paths)} kép előkészítve feltöltésre.")
            
        except Exception as e:
            raise IOError(f"Hiba történt a képfájlok olvasása közben: {e}")

        try:
            file_input = self.page.locator(self.UPLOAD_IMAGE_INPUT_SELECTOR)
            await file_input.set_input_files(image_paths)
            
            loader = self.page.locator(self.UPLOAD_LOADER_SELECTOR)
            self.log(logging.DEBUG, "Várakozás a képek feldolgozására...")
            await loader.wait_for(state="visible", timeout=self.element_visibility_timeout)
            await loader.wait_for(state="hidden", timeout=self.upload_completion_timeout)
            
            self.log(logging.INFO, "Képek sikeresen feltöltve és feldolgozva.", color_override="green")

        except TimeoutError:
            raise TimeoutError("A képfeltöltés időtúllépés miatt megszakadt. Lehet, hogy a képek túl nagyok vagy a kapcsolat lassú.")
        except Exception as e:
            raise RuntimeError(f"Váratlan hiba a képek feltöltésekor: {e}")

    def _format_error_message(self, error_details: str) -> str:
        if self.UPLOAD_IMAGE_INPUT_SELECTOR in error_details: return "Hiba: A képfeltöltő elem nem jelent meg."
        if self.TITLE_SELECTOR in error_details: return "Hiba: A cím mező nem jelent meg."
        if self.NEXT_BUTTON_SELECTOR in error_details: return "Hiba: A 'Tovább' gomb nem vált elérhetővé."
        if self.DESCRIPTION_SELECTOR in error_details: return "Hiba: A 'Leírás' mező nem jelent meg."
        if self.PRICE_SELECTOR in error_details: return "Hiba: Az 'Ár' mező nem jelent meg."
        if self.SHOW_PHONE_CHECKBOX_SELECTOR in error_details: return "Hiba: A 'Telefon mutatása' jelölőnégyzet nem jelent meg."
        if self.ACCEPT_TERMS_CHECKBOX_SELECTOR in error_details: return "Hiba: A 'Felhasználási feltételek' jelölőnégyzet (input) nem jelent meg."
        
        if any(s in error_details for s in [
            self.CATEGORY_LEVEL1_CONTAINER_SELECTOR, self.CATEGORY_LEVEL2_CONTAINER_SELECTOR,
            self.CATEGORY_LEVEL3_CONTAINER_SELECTOR, self.OFFER_BUTTON_SELECTOR,
            self.ATTRIBUTES_CONTAINER_SELECTOR
        ]):
             return "Hiba: A kitöltési folyamat egy eleme (pl. kategória, 'Kínál' gomb, tulajdonságok panel) nem jelent meg időben."
             
        return f"Hiba a kitöltési folyamat során: {error_details}"