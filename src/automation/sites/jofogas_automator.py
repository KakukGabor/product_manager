import asyncio
import logging
import re
import os
import json
from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QApplication
from playwright.async_api import Page, BrowserContext, TimeoutError
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

from managers.settings_manager import SettingsManager
from automation.playwright_automator import PlaywrightAutomator
from config.app_folders import FOLDER_APP_DATA, FOLDER_RAW, FOLDER_RAW_JF
from models.product_model import Product
from playwright.async_api import Page
from .jf_core.jf_product_locator import JofogasProductLocator
from .jf_core.jf_form_filler import JofogasFormFiller

logger = logging.getLogger(__name__)


class JofogasAutomator(QObject):
    jfFlowFinished = Signal(bool, str)
    jfDataExtractionFinished = Signal(str, list, bool, str)
    jfFormFillingFinished = Signal(bool, str, dict)
    jfSemiAutoLocateFinished = Signal(Page, bool, str, str)

    def __init__(self, core_automator: PlaywrightAutomator, settings_manager: SettingsManager, app_root_dir: str, parent=None):
        super().__init__(parent)
        self.core_automator = core_automator
        self.settings_manager = settings_manager
        self.app_root_dir = app_root_dir
        self._jf_page: Page | None = None
        self.product_locator = JofogasProductLocator(
            log_callback=lambda msg, lvl, clr: self._log(lvl, msg, color_override=clr)
        )

    def _log(self, level: int, message: str, *args, color_override: Optional[str] = None, emit_status_signal: bool = True, **kwargs):
        prefixed_message = f"[JF] {message}"
        logger.log(level, prefixed_message, *args, **kwargs)
        if emit_status_signal:
            try:
                gui_message = message % args if args else message
            except TypeError:
                gui_message = message
            self.core_automator.statusUpdated.emit(gui_message, level, color_override)


    @Slot(str, int, object)
    def _handle_core_automator_status_update(self, message: str, level: int, color_override: Optional[str]):
        pass 


    async def _get_or_create_jf_page_async(self, force_new: bool = False) -> Optional[Page]:
        browser_context = self.core_automator.browser_manager._context
        if not browser_context:
            self._log(logging.ERROR, "Nincs aktív böngésző kontextus a Jófogás oldalhoz.", color_override="red")
            return None

        if force_new and self._jf_page and not self._jf_page.is_closed():
            await self._jf_page.close()
            self._jf_page = None

        if self._jf_page is None or self._jf_page.is_closed():
            try:
                self._jf_page = await browser_context.new_page()
            except Exception as e:
                self._log(logging.ERROR, f"Hiba az új Jófogás lap létrehozásakor: {e}", color_override="red")
                return None

            screen = QApplication.primaryScreen()
            if screen:
                screen_geom = screen.availableGeometry()
                await self._jf_page.set_viewport_size({"width": screen_geom.width(), "height": screen_geom.height()})
        return self._jf_page


    async def _run_jofogas_flow_async(self):
        default_navigation_timeout = self.settings_manager.get_setting("browser_settings.default_navigation_timeout_ms", 30000)

        if not self.core_automator.browser_manager._context:
            self._log(logging.INFO, "Böngésző indítása a Jófogás adatgyűjtéshez.", color_override="blue")
            if not await self.core_automator.start_browser_for_background_task():
                self.jfFlowFinished.emit(False, "Nem sikerült elindítani a böngészőt a Jófogás adatgyűjtéshez.")
                return

        self._jf_page = await self._get_or_create_jf_page_async(force_new=True)
        if not self._jf_page:
            self.jfFlowFinished.emit(False, "Nem sikerült megnyitni a böngészőt vagy a lapot a Jófogáshoz.")
            return

        jf_main_url = self.settings_manager.get_setting("site_configs.jofogas.button_target_url", "https://www.jofogas.hu/")
        try:
            await self._jf_page.goto(jf_main_url, timeout=default_navigation_timeout, wait_until="load")
        except Exception as e:
            message = f"Hiba a Jófogás főoldal megnyitásakor: {e}"
            self._log(logging.ERROR, message, color_override="red")
            self.jfFlowFinished.emit(False, message)
            return
        
        jf_products_url = self.settings_manager.get_setting("site_configs.jofogas.products_url", "https://www.jofogas.hu/fiok/hirdeteseim")
        try:
            await self._jf_page.goto(jf_products_url, timeout=default_navigation_timeout, wait_until="load")
            self.jfFlowFinished.emit(True, "Jófogás hirdetések oldal sikeresen megnyílt.")
        except Exception as e:
            message = f"Hiba a Jófogás hirdetések oldal megnyitásakor: {e}"
            self._log(logging.ERROR, message, color_override="red")
            self.jfFlowFinished.emit(False, message)

    def _save_raw_jf_data(self, data: List[Dict[str, Any]]):
        try:
            save_dir = (
                Path(self.app_root_dir)
                / FOLDER_APP_DATA
                / FOLDER_RAW
                / FOLDER_RAW_JF
            )
            save_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"jf_data_raw_{timestamp}.json"
            save_path = save_dir / filename

            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            
            self._log(logging.INFO, f"Nyers Jófogás adatok mentve: {filename}", color_override="green")

        except Exception as e:
            self._log(logging.ERROR, f"Hiba a nyers Jófogás adatok mentésekor: {e}", exc_info=True)

    async def _extract_jofogas_ads_data_async(self) -> List[Dict[str, Any]]:
        await self._run_jofogas_flow_async()

        if not self.settings_manager.get_setting("browser_settings.headless", False):
            try:
                self._log(logging.INFO, "Böngésző ablak minimalizálása az adatgyűjtés idejére...", color_override="blue")
                automation_title = self.core_automator.browser_manager._AUTOMATION_WINDOW_TITLE
                if self._jf_page and not self._jf_page.is_closed():
                    await self._jf_page.evaluate(f"document.title = '{automation_title}'")
                
                await self.core_automator.browser_manager.minimize_window()
            except Exception as e:
                self._log(logging.WARNING, f"Nem sikerült a Jófogás ablakot minimalizálni: {e}")

        extracted_ads_data: List[Dict[str, Any]] = []
        page = self._jf_page
        current_page_num = 1

        absolute_position_counter = 1

        if not page or page.is_closed():
            self.jfDataExtractionFinished.emit("Hiba", [], False, "Nincs aktív Jófogás lap az adatok kinyeréséhez.")
            return []

        try:
            while True:
                self._log(logging.DEBUG, f"Adatok kinyerése az {current_page_num}. oldalról...", color_override="darkblue")
                await page.wait_for_selector(".jfg-item.my-item", timeout=15000)
                await asyncio.sleep(2)

                ad_elements = await page.locator(".jfg-item.my-item").all()
                
                if not ad_elements:
                    self._log(logging.WARNING, "Nem található hirdetés az oldalon.", color_override="red")
                    break

                for i, ad_element in enumerate(ad_elements):
                    ad_data = {}
                    try:
                        name_element = ad_element.locator(".my-item-subject .subject")
                        ad_data["name"] = await name_element.text_content() if name_element else "N/A"

                        price_element = ad_element.locator(".my-item-price .price")
                        price_raw_text = await price_element.text_content() if await price_element.is_visible() else "0 Ft"
                        ad_data["price_raw"] = price_raw_text
                        
                        try:
                            price_numeric = float(price_raw_text.replace("Ft", "").replace(" ", "").strip())
                            ad_data["price_numeric"] = price_numeric
                        except (ValueError, TypeError):
                            ad_data["price_numeric"] = 0.0
                    
                        expiration_text_element = ad_element.locator(".my-item-expiration.my-item-param span.ng-binding")
                        expiration_text = await expiration_text_element.text_content() if await expiration_text_element.is_visible() else "N/A"
                        if expiration_text != "N/A":
                            match = re.search(r'(\d+)\s+nap múlva', expiration_text)
                            ad_data["expires_in_days"] = int(match.group(1)) if match else "N/A"
                        else:
                            ad_data["expires_in_days"] = "N/A"

                        views_text_element = ad_element.locator(".my-item-views.my-item-param span.ng-binding")
                        views_text = await views_text_element.text_content() if await views_text_element.is_visible() else "N/A"
                        if views_text != "N/A":
                            match = re.search(r'(\d+)\s+ember látta összesen', views_text)
                            ad_data["views"] = int(match.group(1)) if match else "N/A"
                        else:
                            ad_data["views"] = "N/A"
                        
                        ad_data["position"] = absolute_position_counter
                        absolute_position_counter += 1

                        extracted_ads_data.append(ad_data)
                        self._log(logging.DEBUG, f"Kinyert adat ({i+1}/{len(ad_elements)}): {ad_data}", color_override="light_blue", emit_status_signal=False)

                    except Exception as e:
                        self._log(logging.ERROR, f"Hiba egy hirdetés adatainak kinyerésekor (index {i}): {e}", color_override="red", emit_status_signal=False)

                next_page_button_clickable_locator = page.locator("ul.pagination li.pagination-next:not(.disabled) a")
                navigation_timeout = self.settings_manager.get_setting("browser_settings.default_navigation_timeout_ms", 30000)
                
                try:
                    is_visible = await next_page_button_clickable_locator.is_visible(timeout=2000)
                    is_enabled = await next_page_button_clickable_locator.is_enabled(timeout=2000)

                    if is_visible and is_enabled:
                        self._log(logging.INFO, f"Lapozás a {current_page_num + 1}. oldalra...", color_override="darkblue")
                        
                        # 1. Kattintás a gombra
                        await next_page_button_clickable_locator.click(timeout=navigation_timeout)
                        
                        # --- JAVÍTÁS KEZDETE ---
                        # networkidle HELYETT megvárjuk, amíg az aktív oldalszám megváltozik
                        next_page_num = current_page_num + 1
                        try:
                            # Megvárjuk, amíg a lapozóban az új oldalszám lesz az aktív
                            await page.wait_for_selector(
                                f"ul.pagination li.pagination-page.active a:text-is('{next_page_num}')", 
                                timeout=10000
                            )
                        except:
                            # Ha a lapozó nem frissülne időben, egy fix rövid várakozás fallback-nek
                            await asyncio.sleep(3)
                        # --- JAVÍTÁS VÉGE ---

                        current_page_num += 1
                    else:
                        self._log(logging.INFO, "Nincs több oldal a lapozáshoz.", color_override="navy")
                        break
                        
                except TimeoutError:
                    self._log(logging.INFO, "Nincs több oldal a lapozáshoz (időtúllépés).", color_override="navy")
                    break
                except Exception as e:
                    self._log(logging.ERROR, f"Hiba lapozás közben: {e}. Lapozás vége.", color_override="red")
                    break

        except TimeoutError:
            self._log(logging.ERROR, "Időtúllépés az adatok kinyerése során.", color_override="red")
            self.jfDataExtractionFinished.emit("Hiba", [], False, "Időtúllépés az adatok kinyerése során.")
            return []
        except Exception as e:
            message = f"Általános hiba az adatok kinyerése során: {e}"
            self._log(logging.ERROR, message, color_override="red")
            self.jfDataExtractionFinished.emit("Hiba", [], False, message)
            return []

        if extracted_ads_data:
            self._save_raw_jf_data(extracted_ads_data)

        self.jfDataExtractionFinished.emit("Siker", extracted_ads_data, True, "Jófogás adatok sikeresen kinyerve.")
        return extracted_ads_data


    @Slot()
    def extract_jofogas_ads(self):
        future = self.core_automator.loop_worker.run_coro_threadsafe(self._extract_jofogas_ads_data_async())
        def on_done(fut):
            exc = fut.exception()
            if exc:
                self._log(logging.CRITICAL, f"Váratlan hiba a JF adatkinyerés közben a háttérszálon: {exc}", exc_info=True)
        
        # --- MÓDOSÍTÁS: A hiányzó sor hozzáadása ---
        future.add_done_callback(on_done)

    async def _semi_auto_locate_product_async(self, page: Page, product: Product):
        """
        Meghívja a Jofogas Product Locator osztályt a feladat elvégzésére.
        Hiba esetén kivételt dob, amit a hívó (_done callback) kezel.
        """
        self._log(logging.INFO, f"Jófogás hirdetés megkeresése indítva: '{product.title}'...", color_override="processing")

        await self.product_locator.locate_and_highlight(page, product)
        
        message = f"'{product.title}' sikeresen megtalálva és kiemelve a Jófogás oldalon."
        self._log(logging.INFO, message, color_override="green")
        self.jfSemiAutoLocateFinished.emit(page, True, message, product.id)

    @Slot(Page, Product)
    def run_jf_semi_auto_locate_flow(self, page: Page, product: Product):
        """Elindítja a termék-megkeresési folyamatot, és központilag kezeli a hibákat."""
        coro = self._semi_auto_locate_product_async(page, product)

        def _done(future):
            exc = future.exception()
            if exc:
                msg = f"Hiba a(z) '{product.title}' Jófogás hirdetés megkeresésekor: {exc}"
                self._log(logging.ERROR, msg, exc_info=True, color_override="red")
                self.jfSemiAutoLocateFinished.emit(None, False, msg, product.id)

        future = self.core_automator.loop_worker.run_coro_threadsafe(coro)
        future.add_done_callback(_done)

    async def _run_jf_new_product_fill_flow_async(self, product_data: Dict[str, Any]):
        """
        Elindítja a Jófogás új hirdetés feladási folyamatát:
        1. Biztosítja a böngésző futását.
        2. Elnavigál az új hirdetés oldalára.
        3. Meghívja a FormFiller-t a tényleges kitöltésre.
        """
        success = False
        message = ""

        try:
            # 1. Böngésző előkészítése (futás biztosítása, minimalizálás)
            browser_started = await self.core_automator.start_browser_for_background_task()
            if not browser_started:
                message = "A böngésző indítása sikertelen, a Jófogás űrlap kitöltése megszakítva."
                self._log(logging.ERROR, message)
                self.jfFormFillingFinished.emit(False, message, product_data)
                return

            await self.core_automator.browser_manager.close_all_pages_async()
            # 2. Jófogás oldal objektum lekérése vagy létrehozása
            self._jf_page = await self._get_or_create_jf_page_async(force_new=True)
            if not self._jf_page:
                message = "Nem sikerült lapot nyitni a Jófogás hirdetésfeladáshoz."
                self._log(logging.ERROR, message)
                self.jfFormFillingFinished.emit(False, message, product_data)
                return

            # 3. Navigáció a hirdetésfeladási oldalra
            new_product_url = self.settings_manager.get_setting("site_configs.jofogas.new_product_url")
            if not new_product_url:
                raise ValueError("Hiányzik a Jófogás új hirdetés URL-je a beállításokból.")
            
            self._log(logging.INFO, f"Navigálás a Jófogás hirdetésfeladási oldalra: {new_product_url}...")
            default_navigation_timeout = self.settings_manager.get_setting("browser_settings.default_navigation_timeout_ms", 30000)
            await self._jf_page.goto(new_product_url, timeout=default_navigation_timeout, wait_until="load")
            
            # Ablakcím visszaállítása és minimalizálás (GS-hez hasonlóan)
            automation_title = self.core_automator.browser_manager._AUTOMATION_WINDOW_TITLE
            await self._jf_page.evaluate(f"document.title = '{automation_title}'")
            if not self.settings_manager.get_setting("browser_settings.headless", False):
                await self.core_automator.browser_manager.minimize_window()

            # 4. A FormFiller osztály példányosítása és futtatása
            form_filler = JofogasFormFiller(
                page=self._jf_page,
                settings_manager=self.settings_manager,
                log_callback=lambda lvl, msg, **kwargs: self._log(lvl, msg, **kwargs),
                app_root_dir=self.app_root_dir
            )
            
            success, message = await form_filler.fill_form(product_data)

            # A folyamat végén (vagy ha hiba van) hozzuk elő az ablakot
            if not self.settings_manager.get_setting("browser_settings.headless", False):
                await self.core_automator.browser_manager.restore_window()

        except Exception as e:
            success = False
            message = f"Váratlan hiba a Jófogás kitöltési folyamat előkészítésekor: {e}"
            self._log(logging.CRITICAL, message, exc_info=True)
        finally:
            self.jfFormFillingFinished.emit(success, message, product_data)

    @Slot(dict)
    def run_jf_new_product_fill_flow(self, product_data: Dict[str, Any]):
        """Slot, ami elindítja a Jófogás űrlapkitöltési folyamatot a háttérben."""
        coro = self._run_jf_new_product_fill_flow_async(product_data=product_data)

        def _done(future):
            exc = future.exception()
            if exc:
                self._log(logging.CRITICAL, f"Váratlan hiba a JF űrlapkitöltés közben: {exc}", exc_info=True)
                self.jfFormFillingFinished.emit(False, f"Hiba a művelet során: {exc}", product_data)

        future = self.core_automator.loop_worker.run_coro_threadsafe(coro)
        future.add_done_callback(_done)