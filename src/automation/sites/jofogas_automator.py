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
        page = await self.core_automator.browser_manager._create_or_get_page(force_new=force_new)
        if not page:
            self._log(logging.ERROR, "Nincs aktív böngésző kontextus a Jófogás oldalhoz.", color_override="red")
            return None
        self._jf_page = page
        return page


    async def _run_jofogas_flow_async(self):
        default_navigation_timeout = self.settings_manager.get_setting("browser_settings.default_navigation_timeout_ms", 30000)

        if not self.core_automator.browser_manager._context:
            self._log(logging.INFO, "Böngésző indítása a Jófogás adatgyűjtéshez.", color_override="blue")
            if not await self.core_automator.start_browser_for_background_task():
                self.jfFlowFinished.emit(False, "Nem sikerült elindítani a böngészőt a Jófogás adatgyűjtéshez.")
                return

        await self.core_automator.browser_manager.close_all_pages_async()
        self._jf_page = await self._get_or_create_jf_page_async(force_new=False)
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

    async def _scrape_ads_from_current_tab(self, page: Page, is_archived: bool) -> List[Dict[str, Any]]:
        extracted_ads_data: List[Dict[str, Any]] = []
        current_page_num = 1
        absolute_position_counter = 1
        last_page_names = []

        while True:
            self._log(logging.DEBUG, f"Adatok kinyerése az {current_page_num}. oldalról (archív: {is_archived})...", color_override="darkblue")
            
            # Biztosítjuk a betöltődést és a lustán (lazy load) betöltő elemeket
            try:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(3)
            except Exception:
                pass

            # --- 1. LÉPÉS: SZÖVEG MÁSOLÁSA ÉS FELDOLGOZÁSA ---
            try:
                body_text = await page.inner_text("body")
            except Exception as e:
                self._log(logging.ERROR, f"Hiba az oldal szövegének kinyerésekor: {e}")
                break

            lines = [line.strip() for line in body_text.split('\n') if line.strip()]
            page_ads = []
            
            for i, line in enumerate(lines):
                # Keressük az árat a sor végén (pl. "1 650 000 Ft" vagy "1.650.000 Ft")
                price_match = re.match(r'^([\d\s\u00A0\.,]+)\s*Ft$', line, re.IGNORECASE)
                
                if price_match and i > 0:
                    name = lines[i-1]
                    
                    # Fals pozitív találatok kiszűrése
                    invalid_keywords = ["kiemelés", "előresorolás", "ajánlat", "kredit", "összesen", "megtekintés", "szállítás", "foxpost", "gls", "csomag", "napi"]
                    if any(kw in name.lower() for kw in invalid_keywords):
                        continue
                        
                    # Túl rövid, vagy csak számos nevek szűrése
                    if len(name) < 3 or re.match(r'^[\d\s\u00A0\.,]+$', name):
                        continue
                        
                    # Kategória prefixek eltávolítása a pontos egyezésért a belső adatbázissal
                    name = re.sub(r'^(Antik Bútor|Lakáskiegészítő)\s*-\s*', '', name, flags=re.IGNORECASE).strip()
                        
                    price_raw = line
                    try:
                        price_numeric = float(re.sub(r'[^\d]', '', price_raw))
                    except ValueError:
                        price_numeric = 0.0
                        
                    expires_in_days = "N/A"
                    views = "N/A"
                    
                    # Nézzük át az ár utáni következő maximum 10 sort statisztikákért
                    for j in range(1, 11):
                        if i+j >= len(lines):
                            break
                        lookahead_line = lines[i+j]
                        
                        # Ha egy újabb hirdetés árába botlunk, akkor álljunk meg!
                        if re.match(r'^([\d\s\u00A0\.,]+)\s*Ft$', lookahead_line, re.IGNORECASE):
                            prev_look = lines[i+j-1].lower()
                            if not any(kw in prev_look for kw in invalid_keywords):
                                break
                                
                        if expires_in_days == "N/A":
                            exp_match = re.search(r'(\d+)\s*nap múlva', lookahead_line, re.IGNORECASE)
                            if exp_match:
                                expires_in_days = int(exp_match.group(1))
                                
                        if views == "N/A":
                            views_match = re.search(r'(\d+)\s*ember látta', lookahead_line, re.IGNORECASE)
                            if views_match:
                                views = int(views_match.group(1))
                                
                    ad_data = {
                        "name": name,
                        "price_raw": price_raw,
                        "price_numeric": price_numeric,
                        "expires_in_days": expires_in_days,
                        "views": views,
                        "position": absolute_position_counter,
                        "is_archived": is_archived
                    }
                    
                    page_ads.append(ad_data)
                    absolute_position_counter += 1

            # --- VÉGTELEN CIKLUS VÉDELEM ÉS LEÁLLÁS ---
            if not page_ads:
                self._log(logging.WARNING, f"Nem található érvényes hirdetés ezen az oldalon a szöveg alapján (archív: {is_archived}).", color_override="orange")
                break

            current_page_names = [ad["name"] for ad in page_ads]
            if current_page_num > 1 and current_page_names == last_page_names:
                self._log(logging.INFO, f"A tartalom nem változott a lapozás után (végére értünk), vége a beolvasásnak (archív: {is_archived}).", color_override="navy")
                break
            last_page_names = current_page_names

            extracted_ads_data.extend(page_ads)
            self._log(logging.INFO, f"{len(page_ads)} db hirdetés sikeresen beolvasva a(z) {current_page_num}. oldalról (archív: {is_archived}).", color_override="green")
            
            # --- 2. LÉPÉS: LAPOZÁS KERESÉSE MINDEN MEGOLDÁSSAL ---
            next_page_js = """
                () => {
                    // 1. Keresés szöveg/aria-label alapján
                    const links = Array.from(document.querySelectorAll('a, button, [role="button"]'));
                    for (const el of links) {
                        const text = (el.textContent || "").trim().toLowerCase();
                        const aria = (el.getAttribute('aria-label') || "").toLowerCase();
                        const title = (el.getAttribute('title') || "").toLowerCase();
                        const classText = (el.className || "").toString().toLowerCase();
                        
                        if ((text === 'következő' || text === '›' || text === '»' || aria.includes('következő') || title.includes('következő') || text === '>' || classText.includes('icon-arrow-right')) && 
                            !el.hasAttribute('disabled') && 
                            (!el.closest || !el.closest('.disabled')) &&
                            !el.classList.contains('disabled')) {
                            el.click();
                            return true;
                        }
                    }
                    
                    // 2. Keresés URL minta alapján (Jófogás: ?page=2 vagy ?o=2)
                    let nextNum = 2;
                    const urlParams = new URLSearchParams(window.location.search);
                    if (urlParams.has('page')) nextNum = parseInt(urlParams.get('page')) + 1;
                    else if (urlParams.has('o')) nextNum = parseInt(urlParams.get('o')) + 1;
                    else if (window.location.href.includes('/hirdeteseim')) nextNum = 2; // Ha nincs param, de a 1. oldalon vagyunk
                    
                    const pageLinks = Array.from(document.querySelectorAll('a'));
                    for (const a of pageLinks) {
                        try {
                            const hrefUrl = new URL(a.href, window.location.origin);
                            if (hrefUrl.searchParams.get('page') == nextNum || hrefUrl.searchParams.get('o') == nextNum) {
                                a.click();
                                return true;
                            }
                        } catch(e) {}
                    }
                    
                    // 3. Fallback a klasszikus DOM elemhez
                    const nextLi = document.querySelector('li.pagination-next:not(.disabled) a');
                    if (nextLi) {
                        nextLi.click();
                        return true;
                    }
                    
                    return false;
                }
            """
            
            try:
                clicked = await page.evaluate(next_page_js)
                if clicked:
                    self._log(logging.INFO, f"Lapozás a {current_page_num + 1}. oldalra...", color_override="darkblue")
                    try:
                        await page.wait_for_load_state("networkidle", timeout=5000)
                    except Exception:
                        pass
                    await asyncio.sleep(2)
                    current_page_num += 1
                else:
                    self._log(logging.INFO, f"Nincs több oldal a lapozáshoz (Minden hirdetés beolvasva, archív: {is_archived}).", color_override="navy")
                    break
            except Exception as e:
                self._log(logging.ERROR, f"Hiba lapozás közben: {e}. Beolvasás vége (archív: {is_archived}).", color_override="red")
                break

        return extracted_ads_data


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

        if not page or page.is_closed():
            self.jfDataExtractionFinished.emit("Hiba", [], False, "Nincs aktív Jófogás lap az adatok kinyeréséhez.")
            return []

        # 1. Aktív hirdetések beolvasása
        self._log(logging.INFO, "Aktív hirdetések beolvasása indult...", color_override="blue")
        active_ads = await self._scrape_ads_from_current_tab(page, is_archived=False)
        extracted_ads_data.extend(active_ads)

        # 2. Archivált (törlés alatt) hirdetések beolvasása
        self._log(logging.INFO, "Archivált hirdetések beolvasása indult...", color_override="blue")
        jf_archived_url = self.settings_manager.get_setting(
            "site_configs.jofogas.archived_products_url", 
            "https://www.jofogas.hu/fiok/hirdeteseim/archivalt-torles-alatt"
        )
        default_navigation_timeout = self.settings_manager.get_setting("browser_settings.default_navigation_timeout_ms", 30000)
        
        try:
            await page.goto(jf_archived_url, timeout=default_navigation_timeout, wait_until="load")
            archived_ads = await self._scrape_ads_from_current_tab(page, is_archived=True)
            extracted_ads_data.extend(archived_ads)
        except Exception as e:
            self._log(logging.ERROR, f"Hiba az archivált hirdetések beolvasásakor: {e}", color_override="red")

        if extracted_ads_data:
            self._save_raw_jf_data(extracted_ads_data)

        self.jfDataExtractionFinished.emit("Siker", extracted_ads_data, True, "Jófogás adatok (aktív és archivált) sikeresen kinyerve.")
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
            self._jf_page = await self._get_or_create_jf_page_async(force_new=False)
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