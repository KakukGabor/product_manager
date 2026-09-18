import asyncio
import json
import logging
import math
import os
import re
import json
from datetime import datetime
from pathlib import Path
from config.app_folders import FOLDER_APP_DATA, FOLDER_RAW, FOLDER_RAW_GS
from pathlib import Path
from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QApplication
from playwright.async_api import Page, BrowserContext, TimeoutError
from typing import List, Dict, Any, Optional

from managers.settings_manager import SettingsManager
from automation.playwright_automator import PlaywrightAutomator
from automation.sites.gs_core.gs_data_extractor import GaleriaSavariaDataExtractor
from automation.sites.gs_core.gs_form_filler import GaleriaSavariaFormFiller
from models.product_model import MainCategory, Product
from config.gs_category_mapping import GS_CATEGORY_MAPPING
from config.gs_style_mapping import get_gs_style_from_title, get_gs_period_from_style
from .gs_core.gs_product_locator import GaleriaSavariaProductLocator

logger = logging.getLogger(__name__)


class GaleriaSavariaAutomator(QObject):
    gsFlowFinished = Signal(bool, str)
    gsDataExtractionFinished = Signal(str, list, bool, str)
    gsFormFillingFinished = Signal(bool, str, dict)
    gsProductValidationFinished = Signal(bool, str, dict, str)
    gsSemiAutoLocateFinished = Signal(bool, str, str)


    def __init__(self, core_automator: PlaywrightAutomator, settings_manager: SettingsManager, parent=None):
        super().__init__(parent)
        self.core_automator = core_automator
        self.settings_manager = settings_manager
        self._gs_page: Page | None = None
        
        # --- JAVÍTÁS ---
        # A DataExtractor példányosítása a helyes callback függvénnyel, duplikáció nélkül.
        self.data_extractor = GaleriaSavariaDataExtractor(
            settings_manager=self.settings_manager,
            app_root_dir=self.core_automator.app_root_dir,
            log_callback=self._log_from_core_component # <-- A helyes callback név
        )

        # A ProductLocator példányosítása változatlanul helyes.
        self.product_locator = GaleriaSavariaProductLocator(
            log_callback=self._log_from_core_component
        )

    def _log(self, level: int, message: str, *args, **kwargs):
        color = kwargs.pop('color_override', None)
        logger.log(level, f"[GS] {message}", *args, **kwargs)

        try:
            gui_message = message % args if args else message
        except TypeError:
            gui_message = message

        if self.core_automator:
            self.core_automator.emit_status_update(gui_message, level, color)

    def _log_from_core_component(self, message: str, level: int, color: Optional[str]):
        self.core_automator.emit_status_update(message, level, color)

    async def _get_or_create_gs_page_async(self, force_new: bool = False) -> Optional[Page]:
        page = await self.core_automator.browser_manager._create_or_get_page(force_new=force_new)
        if not page:
            self._log(logging.ERROR, "Nincs aktív böngésző kontextus a Galéria Savaria oldalhoz. Kérjük indítsa el a böngészőt.")
            return None
        self._gs_page = page
        return page


    
    async def _run_galeria_savaria_flow_async(self):
        default_navigation_timeout = self.settings_manager.get_setting("browser_settings.default_navigation_timeout_ms", 30000)

        await self.core_automator.browser_manager.close_all_pages_async()
        self._gs_page = await self._get_or_create_gs_page_async(force_new=False)
        if not self._gs_page:
            self.gsFlowFinished.emit(False, "Nem sikerült megnyitni a böngészőt vagy a lapot a Galéria Savaria-hoz.")
            return

        self._log(logging.INFO, "Navigálás a Galéria Savaria oldalra...")
        gs_url = self.settings_manager.get_setting("site_configs.galeria_savaria.button_target_url", "https://galeriasavaria.hu/")
        try:
            await self._gs_page.goto(gs_url, timeout=default_navigation_timeout, wait_until="load")
            self.gsFlowFinished.emit(True, "Galéria Savaria oldal sikeresen megnyílt egy új lapon.")
        except Exception as e:
            message = f"Hiba a Galéria Savaria oldal megnyitásakor: {e}"
            self._log(logging.ERROR, message)
            self.gsFlowFinished.emit(False, message)


    async def _run_gs_new_product_fill_flow_async(self, product_data: Dict[str, Any]):
        success = False
        message = ""

        try:
            # 1. Böngésző előkészítése (ez már csak biztosítja, hogy fusson)
            browser_started = await self.core_automator.start_browser_for_background_task()
            if not browser_started:
                message = "A böngésző indítása sikertelen, az űrlap kitöltése megszakítva."
                self._log(logging.ERROR, message)
                self.gsFormFillingFinished.emit(False, message, product_data)
                return

            await self.core_automator.browser_manager.close_all_pages_async()
            # 2. GS oldal objektum lekérése vagy létrehozása
            self._gs_page = await self._get_or_create_gs_page_async(force_new=False)
            if not self._gs_page:
                message = "Nem sikerült megnyitni a böngészőt vagy a lapot a Galéria Savaria új termék feltöltéshez."
                self._log(logging.ERROR, message)
                self.gsFormFillingFinished.emit(False, message, product_data)
                return

            # 3. Navigáció
            new_product_url = self.settings_manager.get_setting("site_configs.galeria_savaria.new_product_url")
            if not new_product_url:
                raise ValueError("Hiányzik a Galéria Savaria új termék URL-je a beállításokból.")
            
            self._log(logging.INFO, f"Navigálás a GS új termék feltöltési oldalra: {new_product_url}...")
            default_navigation_timeout = self.settings_manager.get_setting("browser_settings.default_navigation_timeout_ms", 30000)
            await self._gs_page.goto(new_product_url, timeout=default_navigation_timeout, wait_until="load")
            
            # === VÉGLEGES JAVÍTÁS KEZDETE ===
            # 4. KÖTELEZŐ LÉPÉS: Az ablakcím visszaállítása a navigáció után!
            automation_title = self.core_automator.browser_manager._AUTOMATION_WINDOW_TITLE
            await self._gs_page.evaluate(f"document.title = '{automation_title}'")
            
            # 5. Most, a helyes címmel, biztonságosan minimalizálhatjuk az ablakot.
            if not self.settings_manager.get_setting("browser_settings.headless", False):
                await self.core_automator.browser_manager.minimize_window()
            # === VÉGLEGES JAVÍTÁS VÉGE ===

            # 6. A FormFiller osztály példányosítása és futtatása
            form_filler = GaleriaSavariaFormFiller(
                page=self._gs_page,
                settings_manager=self.settings_manager,
                log_callback=self._log,
                app_root_dir=self.core_automator.app_root_dir
            )
            
            success, message = await form_filler.fill_form(product_data)

        except Exception as e:
            success = False
            message = f"Váratlan, kritikus hiba a GS terméklapkitöltési folyamat előkészítésekor: {e}"
            self._log(logging.CRITICAL, message, exc_info=True)
        finally:
            self.gsFormFillingFinished.emit(success, message, product_data)
           
           
    async def _extract_gs_structured_products_async(self, page: Page, url: str, identifier: str):
        extracted_products_data: List[Dict[str, Any]] = []
        success = False
        message = ""

        try:
            extracted_products_data = await self.data_extractor.extract_products_from_page(
                page=page,
                url=url
            )

            success = True
            message = f"{len(extracted_products_data)} strukturált GS termék sikeresen kinyerve a(z) '{url}' oldalról."

        except Exception as e:
            message = f"Hiba a(z) '{url}' oldal adatgyűjtésekor: {e}"
            self._log(logging.ERROR, message, exc_info=True)
            success = False
        finally:
            self.gsDataExtractionFinished.emit(identifier, extracted_products_data, success, message)
            
            if not success and self.core_automator.browser_manager._context and not self.settings_manager.get_setting("browser_settings.headless", False):
                self._log(logging.WARNING, "Hiba történt a GS adatkinyeréskor. A böngészőablak előtérbe hozása...")
                try:
                    await self.core_automator.browser_manager.restore_window()
                except Exception as e:
                    self._log(logging.WARNING, f"Nem sikerült az ablakot előtérbe hozni: {e}")


    async def _run_gs_new_product_validate_flow_async(self, original_product_id: str, local_product_title: str, local_price_numeric: float):
        default_navigation_timeout = self.settings_manager.get_setting("browser_settings.default_navigation_timeout_ms", 30000)
        
        success = False
        message = ""
        extracted_on_site_data: Dict[str, Any] = {}

        self._log(logging.INFO, f"Galéria Savaria termék érvényesítés indítása. Helyi termék címe: '{local_product_title}'", color_override="processing")

        if not self._gs_page or self._gs_page.is_closed():
            message = "Nincs aktív Galéria Savaria lap az érvényesítéshez."
            self._log(logging.ERROR, message)
            self.gsProductValidationFinished.emit(False, message, {}, original_product_id)
            return

        try:
            gs_products_url = self.settings_manager.get_setting("site_configs.galeria_savaria.products_url")
            if not gs_products_url:
                message = "Hiba: Hiányzik a Galéria Savaria termékek URL-je a beállításokból."
                self._log(logging.CRITICAL, message)
                self.gsProductValidationFinished.emit(False, message, {}, original_product_id)
                return

            await self._gs_page.goto(gs_products_url, timeout=default_navigation_timeout, wait_until="load")
            self._log(logging.INFO, "Galéria Savaria feltöltött termékek oldala betöltve.", color_override="processing")
            automation_title = self.core_automator.browser_manager._AUTOMATION_WINDOW_TITLE
            await self._gs_page.evaluate(f"document.title = '{automation_title}'")

            find_product_js_script = f"""
                (() => {{
                    const local_title = {json.dumps(local_product_title)};
                    const local_price_numeric = {json.dumps(local_price_numeric)};

                    const firstRow = document.querySelector('table.table_full tbody > tr[class^="prod"]');
                    if (!firstRow) return null;

                    const product = {{}};

                    function getText(el, selector) {{
                        const targetEl = selector ? el.querySelector(selector) : el;
                        return targetEl ? targetEl.textContent.trim() : '';
                    }}

                    function getAttribute(el, selector, attr) {{
                        const targetEl = selector ? el.querySelector(selector) : el;
                        return targetEl ? targetEl.getAttribute(attr) : '';
                    }}

                    try {{
                        const title_el = firstRow.querySelector('td:nth-child(3) a.title_full');
                        const price_el = firstRow.querySelector('td:nth-child(5) strong.price');

                        if (!title_el || !price_el) return null;

                        const site_title = getText(title_el);
                        const site_price_raw = getText(price_el);

                        let site_price_numeric = 0.0;
                        try {{
                            site_price_numeric = parseFloat(site_price_raw.replace(/[^0-9,-]/g, '').replace('.', '').replace(',', '.'));
                        }} catch (e) {{
                            console.warn("Hiba az ár parszolásakor az első sorban:", e);
                            return null;
                        }}

                        const search_string_in_site_title = local_title.substring(0, Math.min(local_title.length, 50));
                        const title_match = site_title.toLowerCase().includes(search_string_in_site_title.toLowerCase());

                        if (title_match && Math.abs(site_price_numeric - local_price_numeric) < 0.01) {{
                            product.name = site_title;
                            product.product_url = getAttribute(title_el, null, 'href');

                            const img_el = firstRow.querySelector('td.termekkep img');
                            product.image_url = img_el ? (getAttribute(img_el, null, 'data-src') || getAttribute(img_el, null, 'src')) : null;

                            const productCodeAndStatsText = firstRow.querySelector('td:nth-child(3) div.view_full.mt5');
                            if (productCodeAndStatsText) {{
                                const lines = getText(productCodeAndStatsText)
                                    .split(/\\r?\\n/)
                                    .map(l => l.trim())
                                    .filter(l => l.length > 0);

                                product.code = '';
                                product.watchers = 0;
                                product.views = 0;

                                lines.forEach(line => {{
                                    if (line.startsWith("Termékkód:")) {{
                                        product.code = line.replace(/[^0-9]/g, '');
                                    }}
                                    if (line.startsWith("Megfigyelők:")) {{
                                        product.watchers = parseInt(line.replace(/[^0-9]/g, ''), 10);
                                    }}
                                    if (line.startsWith("Megtekintések:")) {{
                                        product.views = parseInt(line.replace(/[^0-9]/g, ''), 10);
                                    }}
                                }});
                            }}

                            product.price = site_price_raw;
                            product.price_numeric = site_price_numeric;

                            const upload_date_el = firstRow.querySelector('td:nth-child(6) strong.date');
                            product.upload_date = upload_date_el ? getText(upload_date_el) : null;

                            return product;
                        }}
                        return null;
                    }} catch (e) {{
                        console.error("Hiba az első termék adatainak kinyerésekor:", e, firstRow.outerHTML);
                        return null;
                    }}
                }})()
            """

            found_product_data = await self._gs_page.evaluate(find_product_js_script)

            if found_product_data:
                self._log(logging.INFO, f"Az első termék (feltételezhetően a frissen feltöltött) sikeresen megtalálva a GS oldalon. Kód: {found_product_data.get('code')}", color_override="processing")
                extracted_on_site_data = found_product_data
                success = True
                message = f"Termék '{local_product_title}' sikeresen érvényesítve a Galéria Savaria oldalon (kód: {extracted_on_site_data.get('code')})."
            else:
                message = f"Nem sikerült megtalálni a '{local_product_title}' ({local_price_numeric} Ft) terméket a Galéria Savaria feltöltött termékei között az ELSŐ HELYEN. Lehet, hogy nem töltötték fel, vagy az adatok eltérnek, vagy nem ez a legújabb tétel."
                self._log(logging.ERROR, message)
                success = False

        except TimeoutError as e:
            message = f"Időtúllépés hiba a GS termék érvényesítésekor: {e}"
            self._log(logging.ERROR, message, exc_info=True)
            success = False
        except Exception as e:
            message = f"Váratlan hiba a GS termék érvényesítésekor: {e}"
            self._log(logging.CRITICAL, message, exc_info=True)
            success = False
        finally:
            # A jel kibocsátása itt marad, ez küldi az üzenetet a MainControllernek
            self.gsProductValidationFinished.emit(success, message, extracted_on_site_data, original_product_id)

    @Slot()
    def run_galeria_savaria_automation_flow(self):
        self.core_automator._run_async_slot_wrapper(self._run_galeria_savaria_flow_async, self.gsFlowFinished, identifier="GaleriaSavariaFlow")

    @Slot()
    def stop_galeria_savaria_automation_flow(self):
        self.core_automator._run_async_slot_wrapper(self._stop_galeria_savaria_flow_async, self.gsFlowFinished, identifier="StopGaleriaSavariaFlow")

    @Slot(dict)
    def run_gs_new_product_fill_flow(self, product_data: Dict[str, Any]):
        coro = self._run_gs_new_product_fill_flow_async(product_data=product_data)

        def _done(future):
            exc = future.exception()
            if exc:
                self._log(logging.CRITICAL, f"Váratlan hiba a GS űrlapkitöltés közben a háttérszálon: {exc}", exc_info=True)
                self.gsFormFillingFinished.emit(False, f"Hiba a művelet során: {exc}", product_data)

        future = self.core_automator.loop_worker.run_coro_threadsafe(coro)
        future.add_done_callback(_done)

    @Slot(str, str, float)
    def run_gs_new_product_validate_flow(self, original_product_id: str, local_product_title: str, local_price_numeric: float):
      
        coro = self._run_gs_new_product_validate_flow_async(
            original_product_id=original_product_id,
            local_product_title=local_product_title,
            local_price_numeric=local_price_numeric
        )

        def _done(future):
            exc = future.exception()
            if exc:
                self._log(logging.CRITICAL, f"Váratlan hiba a GS termékérvényesítés közben a háttérszálon: {exc}", exc_info=True)
                self.gsProductValidationFinished.emit(False, f"Hiba a művelet során: {exc}", {}, original_product_id)

        future = self.core_automator.loop_worker.run_coro_threadsafe(coro)
        future.add_done_callback(_done)

    @Slot(str)
    def extract_gs_structured_products(self, url: str):
        coro = self._extract_gs_structured_products_async(url=url, identifier="GS_PRODUCTS_DATA")

        def _done(future):
            exc = future.exception()
            if exc:
                self._log(logging.CRITICAL, f"Váratlan hiba a GS adatkinyerés közben a háttérszálon: {exc}", exc_info=True)

        future = self.core_automator.loop_worker.run_coro_threadsafe(coro)
        future.add_done_callback(_done)

    def run_full_extraction_flow(self, url: str):
        async def full_flow_coroutine():
            # --- MÓDOSÍTÁS: Az új, atomi metódus hívása ---
            success, page = await self.core_automator.start_browser_and_navigate_for_task(url)
            
            if not success or not page:
                self._log(logging.ERROR, "A böngésző indítása vagy a navigáció sikertelen, az adatkinyerés megszakítva.")
                self.gsDataExtractionFinished.emit("GS_PRODUCTS_DATA", [], False, "Böngésző/navigációs hiba.")
                return

            # A már odanavigált oldallal hívjuk meg az adatkinyerő metódust
            await self._extract_gs_structured_products_async(page, url, "GS_PRODUCTS_DATA")

        self.core_automator.loop_worker.run_coro_threadsafe(full_flow_coroutine())

    async def _semi_auto_locate_product_async(self, page: Page, product: Product):
        """
        Meghívja a Product Locator-t. A hibakezelést a hívó (_done callback) végzi.
        """
        operation_id = product.id
        self._log(logging.INFO, f"GS termék megkeresése indítva: '{product.title}'...", color_override="processing")

        # Most már nincs try...except, és nincs visszatérési érték sem.
        # Ha a locate_and_highlight hibát dob, az itt "átesik" és a _done kapja el.
        await self.product_locator.locate_and_highlight(page, product)
        
        # Ha idáig eljut a kód, az azt jelenti, hogy minden sikeres volt.
        message = f"'{product.title}' sikeresen megtalálva és kiemelve a GS oldalon."
        self._log(logging.INFO, message, color_override="green")
        self.gsSemiAutoLocateFinished.emit(True, message, operation_id)

    @Slot(Page, Product)
    def run_gs_semi_auto_locate_flow(self, page: Page, product: Product):
        """Elindítja a termék-megkeresési folyamatot, és központilag kezeli a hibákat."""
        coro = self._semi_auto_locate_product_async(page, product)

        def _done(future):
            # EZ AZ EGYETLEN HELY, AHOL A HIBÁT KEZELJÜK ÉS NAPLÓZZUK!
            exc = future.exception()
            if exc:
                # Az üzenetet közvetlenül a kivételből vesszük
                msg = f"Hiba a(z) '{product.title}' GS termék megkeresésekor: {exc}"
                # A _log metódus gondoskodik a GUI frissítéséről is
                self._log(logging.ERROR, msg, exc_info=True, color_override="red")
                self.gsSemiAutoLocateFinished.emit(False, msg, product.id)

        future = self.core_automator.loop_worker.run_coro_threadsafe(coro)
        future.add_done_callback(_done)