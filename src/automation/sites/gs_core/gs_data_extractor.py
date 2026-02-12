import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import re # <-- Szükséges import

from playwright.async_api import Page, TimeoutError

from config.app_folders import FOLDER_APP_DATA, FOLDER_RAW, FOLDER_RAW_GS
from managers.settings_manager import SettingsManager

logger = logging.getLogger(__name__)


class GaleriaSavariaDataExtractor:
   
    def __init__(self, settings_manager: SettingsManager, app_root_dir: str, log_callback=None):
        self.settings_manager = settings_manager
        self.app_root_dir = app_root_dir
        self.log_callback = log_callback

    def _log(self, level: int, message: str, *args, **kwargs):
        color_for_callback = kwargs.pop('color_override', None)
        logger.log(level, f"[GS_Extractor] {message}", *args, **kwargs)
        if self.log_callback:
            try:
                gui_message = message % args if args else message
            except TypeError:
                gui_message = message
            self.log_callback(gui_message, level, color_for_callback)

    # === JAVÍTOTT METÓDUS KEZDETE ===
    async def _set_items_per_page_limit_async(self, page: Page, default_navigation_timeout: int, element_visibility_timeout: int) -> bool:
        parent_container_selector = 'div.pager_left.filter_right.pt0'
        
        try:
            # 1. Megkeressük a konténert, amiben a linkek vannak
            parent_container = page.locator(parent_container_selector)
            options_container = parent_container.locator('div.select_options')

            # 2. Közvetlenül kiolvassuk az összes 'a' tag href attribútumát, akkor is, ha rejtve vannak
            all_links = await options_container.locator('a').evaluate_all("elements => elements.map(el => el.href)")

            if not all_links:
                self._log(logging.WARNING, "Nem találhatók tételszám-beállító linkek az oldalon. A program az alapértelmezett beállítással folytatódik.")
                return True # Sikeresnek vesszük, hogy folytatódhasson a futás

            # 3. Kikeressük a legmagasabb limitet adó URL-t
            max_limit = -1
            target_url = None

            for link in all_links:
                match = re.search(r'limit=(\d+)', link)
                if match:
                    limit = int(match.group(1))
                    if limit > max_limit:
                        max_limit = limit
                        target_url = link
            
            # 4. Ha találtunk jobb URL-t, és még nem ott vagyunk, odanavigálunk
            if target_url and max_limit > 0:
                # Ellenőrizzük, hogy a jelenlegi URL-ben már a max limit van-e beállítva
                current_limit_match = re.search(r'limit=(\d+)', page.url)
                current_limit = int(current_limit_match.group(1)) if current_limit_match else 0

                if current_limit < max_limit:
                    self._log(logging.INFO, f"Maximális tételszám beállítása a legmagasabb elérhetőre: {max_limit}. Navigálás...")
                    await page.goto(target_url, timeout=default_navigation_timeout, wait_until="load")
                    # Biztonsági ellenőrzés, hogy a táblázat betöltődött-e az új oldalon
                    await page.wait_for_selector('table.table_full', timeout=element_visibility_timeout)
                else:
                    self._log(logging.INFO, f"A maximális tételszám ({max_limit}) már be van állítva.")
                
                return True # A művelet sikeres

            else:
                self._log(logging.WARNING, "Nem sikerült a maximális tételszámot meghatározni a linkekből.")
                return True # Folytatódjon a futás

        except Exception as e:
            self._log(logging.ERROR, f"Hiba történt a tételszám beállításakor a linkekből: {e}", exc_info=True)
            return False # Hiba esetén jelezzük, de a program tud tovább futni
    # === JAVÍTOTT METÓDUS VÉGE ===

    async def extract_products_from_page(self, page: Page, url: str) -> List[Dict[str, Any]]:
        extracted_products_data: List[Dict[str, Any]] = []
        default_navigation_timeout = self.settings_manager.get_setting("browser_settings.default_navigation_timeout_ms", 30000)
        element_visibility_timeout = self.settings_manager.get_setting("browser_settings.element_visibility_timeout_ms", 5000)

        self._log(logging.INFO, f"Strukturált termékadatok gyűjtésének indítása a(z) '{url}' oldalról...", color_override="processing")

        if page.url != url:
            await page.goto(url, timeout=default_navigation_timeout, wait_until="load")

        try:
            await page.wait_for_selector('table.table_full tbody > tr[class^="prod"]', timeout=default_navigation_timeout)
        except TimeoutError:
            self._log(logging.ERROR, "Hiba: A terméklista kulcseleme nem jelent meg a megadott időn belül.")
            raise

        # Itt hívjuk meg a javított, megbízható metódusunkat
        await self._set_items_per_page_limit_async(
            page, default_navigation_timeout, element_visibility_timeout
        )
        
        # A JS kód, ami beolvassa az oldalon lévő összes terméket, változatlanul jó
        gs_all_products_extraction_js = """
            (selector) => {
                const rows = document.querySelectorAll(selector);
                const allProducts = [];
                rows.forEach(row => {
                    if (!row) return;
                    const product = {};
                    function getText(el, selector) { const targetEl = selector ? el.querySelector(selector) : el; return targetEl ? targetEl.textContent.trim() : ''; }
                    function getAttribute(el, selector, attr) { const targetEl = selector ? el.querySelector(selector) : el; return targetEl ? targetEl.getAttribute(attr) : ''; }
                    try {
                        product.name = getText(row, 'td:nth-child(3) a.title_full'); product.product_url = getAttribute(row, 'td:nth-child(3) a.title_full', 'href'); product.image_url = getAttribute(row, 'td.termekkep img', 'data-src') || getAttribute(row, 'td.termekkep img', 'src');
                        const productCodeAndStatsText = getText(row, 'td:nth-child(3) div.view_full.mt5'); const lines = productCodeAndStatsText.split(/\\r?\\n/).map(l => l.trim()).filter(l => l.length > 0);
                        product.code = ''; product.watchers = 0; product.views = 0;
                        lines.forEach(line => {
                            if (line.startsWith("Termékkód:")) { product.code = line.replace(/[^0-9]/g, ''); }
                            if (line.startsWith("Megfigyelők:")) { product.watchers = parseInt(line.replace(/[^0-9]/g, ''), 10) || 0; }
                            if (line.startsWith("Megtekintések:")) { product.views = parseInt(line.replace(/[^0-9]/g, ''), 10) || 0; }
                        });
                        product.price = getText(row, 'td:nth-child(5) strong.price'); product.price_numeric = parseFloat(product.price.replace(/[^0-9,-]/g, '').replace('.', '').replace(',', '.')) || 0.0; product.upload_date = getText(row, 'td:nth-child(6) strong.date');
                        allProducts.push(product);
                    } catch (e) { console.error("Hiba egy terméksor feldolgozásakor:", e, row.outerHTML); }
                });
                return allProducts;
            }
        """
        extracted_products_data = await page.evaluate(gs_all_products_extraction_js, 'table.table_full tbody > tr[class^="prod"]')

        self._log(logging.INFO, f"Sikeres adatkinyerés, beolvasott termékek száma: {len(extracted_products_data)} db.")
        if extracted_products_data:
            self._save_raw_data(extracted_products_data)
        
        return extracted_products_data

    def _save_raw_data(self, data: List[Dict[str, Any]]):
        try:
            save_dir = (
                Path(self.app_root_dir)
                / FOLDER_APP_DATA
                / FOLDER_RAW
                / FOLDER_RAW_GS
            )
            save_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"gs_data_raw_{timestamp}.json"
            save_path = save_dir / filename
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            self._log(logging.INFO, f"Nyers GS adatok mentve: {filename}", color_override="green")
        except Exception as e:
            self._log(logging.ERROR, f"Hiba a nyers GS adatok mentésekor: {e}", exc_info=True)