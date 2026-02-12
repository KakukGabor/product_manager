# src/automation/core/browser_manager.py
import asyncio
import logging
import os
import pygetwindow as gw
import time
from typing import Any, Optional, Callable

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Slot
from playwright.async_api import async_playwright, BrowserContext, Page, Playwright

logger = logging.getLogger(__name__)

class WindowController:
    """
    Egy egyszerű segédosztály a böngésző ablakának kezelésére (minimalizálás, visszaállítás)
    a pygetwindow könyvtár segítségével.
    """
    def __init__(self, window_title_substring: str):
        # A keresendő, specifikus ablakcím
        self._window_title_substring = window_title_substring
        self._window: Optional[gw.Win32Window] = None

    def _find_window(self) -> Optional[gw.Win32Window]:
        """Megkeresi a böngésző ablakát a PONTOS címszöveg-részlet alapján."""
        try:
            # A getWindowsWithTitle pontos egyezést keres, ami most már megbízható
            windows = gw.getWindowsWithTitle(self._window_title_substring)
            if windows:
                self._window = windows[0]
                return self._window

        except Exception as e:
            logger.warning(f"WindowController: Hiba az ablak keresése közben ('{self._window_title_substring}'): {e}")
        
        return None

    def minimize(self) -> bool:
        """Minimalizálja a megtalált böngésző ablakot."""
        # Adjunk egy kis időt, hogy az ablak biztosan megjelenjen a címmel együtt
        time.sleep(0.2)
        window = self._find_window()
        if window:
            try:
                window.minimize()
                logger.info(f"Ablak '{window.title}' sikeresen minimalizálva.")
                return True
            except gw.PyGetWindowException as e:
                logger.warning(f"WindowController: Nem sikerült minimalizálni az ablakot: {e}")
        else:
            logger.warning(f"WindowController: Nem található a '{self._window_title_substring}' című böngésző ablak a minimalizáláshoz.")
        return False

    def restore(self) -> bool:
        """Visszaállítja a megtalált böngésző ablakot."""
        window = self._find_window()
        if window:
            try:
                window.restore()
                logger.info(f"Ablak '{window.title}' sikeresen visszaállítva.")
                return True
            except gw.PyGetWindowException as e:
                logger.warning(f"WindowController: Nem sikerült visszaállítani az ablakot: {e}")
        else:
            logger.warning(f"WindowController: Nem található a '{self._window_title_substring}' című böngésző ablak a visszaállításhoz.")
        return False


class PlaywrightBrowserManager:
    """Playwright indítás/lezárás, persistent context kezelése."""
    # --- JAVÍTÁS 1: Egyedi, konstans azonosító az ablaknak ---
    _AUTOMATION_WINDOW_TITLE = "ProductManager::AutomatedBrowserSession"

    def __init__(self, app_root_dir: str, settings_manager: Any, 
                 on_close_callback: Optional[Callable] = None,
                 on_new_page_callback: Optional[Callable] = None,
                 on_navigation_callback: Optional[Callable] = None):
        self.app_root_dir = app_root_dir
        self.settings_manager = settings_manager
        self._on_close_callback = on_close_callback
        self._playwright: Optional[Playwright] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._liveness_interval_s = 2.0
        self._liveness_task: Optional[asyncio.Task] = None
        self._on_new_page_callback = on_new_page_callback
        self._on_navigation_callback = on_navigation_callback
        
        # --- JAVÍTÁS 2: A WindowController már az egyedi címmel jön létre ---
        self.window_controller = WindowController(window_title_substring=self._AUTOMATION_WINDOW_TITLE)

    async def start_browser(self) -> bool:
        """
        Elindítja a böngészőt a beállítások alapján.
        A böngésző vagy headless módban, vagy láthatóan, maximalizálva indul.
        """
        if self._context and not getattr(self._context, "is_closed", lambda: False)():
            if self._page is None or getattr(self._page, "is_closed", lambda: False)():
                await self._create_or_get_page(force_new=False)
            return True
        try:
            if self._playwright is None: self._playwright = await async_playwright().start()
            
            chrome_profile_dir = str(self.settings_manager.browser_profile_path)
            os.makedirs(chrome_profile_dir, exist_ok=True)
            headless_mode = self.settings_manager.get_setting("browser_settings.headless", False)

            base_args = [
                "--hide-crash-restore-bubble", "--no-first-run", "--no-default-browser-check",
                "--enable-automation", "--disable-infobars", "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process", "--disable-site-isolation-trials",
            ]

            launch_args = base_args
            if not headless_mode:
                launch_args.append("--start-maximized")

            self._context = await self._playwright.chromium.launch_persistent_context(
                user_data_dir=chrome_profile_dir, 
                headless=headless_mode,
                args=launch_args, 
                viewport=None
            )
            
            if self._context: 
                self._context.on("close", self._handle_context_closed)
                self._context.on("page", self._handle_new_page)

            page = await self._create_or_get_page(force_new=False)
        
            # --- KIEGÉSZÍTÉS: AZ ELSŐ LAPRA IS RÁKÖTJÜK A FIGYELŐT ---
            if page:
                await self._attach_navigation_listener_async(page)
            
            
            await self._context.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
            if self._liveness_task is None: 
                self._liveness_task = asyncio.create_task(self._liveness_loop())
            
            return True
        except Exception as e:
            logger.exception("PlaywrightBrowserManager: Hiba a böngésző indításakor: %s", e)
            await self._cleanup_on_error()
            return False

    async def close_browser(self, final_shutdown: bool = False, timeout_s: int = 5) -> None:
        if self._liveness_task:
            self._liveness_task.cancel()
            try: await asyncio.wait_for(self._liveness_task, timeout=1.0)
            except Exception: pass
            self._liveness_task = None
        async def _safe_close(obj_coro, name: str):
            try: await asyncio.wait_for(obj_coro, timeout=timeout_s)
            except asyncio.TimeoutError: logger.warning("%s bezárása túllépte az időt (%ss).", name, timeout_s)
            except Exception as e: logger.exception("Hiba a %s bezárásakor: %s", name, e)
        if self._page and not self._page.is_closed(): await _safe_close(self._page.close(), "lap")
        self._page = None
        if self._context: await _safe_close(self._context.close(), "böngésző kontextus")
        self._context = None
        if self._playwright: await _safe_close(self._playwright.stop(), "Playwright")
        self._playwright = None

    async def _create_or_get_page(self, force_new: bool = False) -> Optional[Page]:
        """
        Létrehoz egy új lapot vagy visszaadja a meglévőt, és beállítja a környezetét.
        JAVÍTVA: A `force_new=True` eset nem zárja be a meglévő lapot, hogy elkerülje
                 az utolsó lap bezárása miatti hibát.
        """
        if not self._context or getattr(self._context, "is_closed", lambda: False)():
            logger.error("Nincs aktív böngésző kontextus."); return None
        
        page_to_configure: Optional[Page] = None
        
        # Ha új lapot kényszerítünk, egyszerűen hozzunk létre egyet.
        if force_new:
            try:
                page_to_configure = await self._context.new_page()
            except Exception as e:
                logger.exception("Hiba új lap (force_new=True) létrehozásakor: %s", e)
                return None
        # Egyébként próbáljuk meg újrahasznosítani a meglévőt.
        else:
            if self._page and not self._page.is_closed():
                page_to_configure = self._page
            else:
                pages = self._context.pages
                if pages:
                    page_to_configure = pages[0]
                else:
                    try:
                        page_to_configure = await self._context.new_page()
                    except Exception as e:
                        logger.exception("Hiba új lap (no existing pages) létrehozásakor: %s", e)
                        return None
        
        # A kiválasztott (új vagy újrahasznosított) lapot beállítjuk aktívnak
        self._page = page_to_configure

        # A lap alaphelyzetbe állítása és konfigurálása
        try:
            if self._page.url != "about:blank":
                await self._page.goto("about:blank")
            
            await self._page.evaluate(f"document.title = '{self._AUTOMATION_WINDOW_TITLE}'")

            if not self.settings_manager.get_setting("browser_settings.headless", False):
                screen = QApplication.primaryScreen()
                if screen:
                    screen_geom = screen.availableGeometry()
                    await self._page.set_viewport_size({"width": screen_geom.width(), "height": screen_geom.height()})
                    logger.debug(f"Viewport mérete beállítva: {screen_geom.width()}x{screen_geom.height()}")
        except Exception as e:
            logger.warning(f"Nem sikerült beállítani a lap környezetét: {e}")
            return None
                
        return self._page

    async def _liveness_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(self._liveness_interval_s)
                if not self._context: break
                try: pages = self._context.pages
                except Exception: break
                if pages is None: break
        except asyncio.CancelledError: pass
        except Exception as e: logger.exception("Liveness loop hiba: %s", e)

    async def _cleanup_on_error(self):
        try:
            if self._context: await self._context.close()
        except Exception: pass
        try:
            if self._playwright: await self._playwright.stop()
        except Exception: pass
        self._context = None; self._playwright = None; self._page = None

    async def _handle_context_closed(self, context: BrowserContext) -> None:
        if self._on_close_callback: self._on_close_callback()
        self._context = None; self._page = None
        if self._liveness_task and not self._liveness_task.done(): self._liveness_task.cancel()

    async def minimize_window(self):
        """Async wrapper, amit Qt-ból vagy automatorból is hívhatsz."""
        return await asyncio.to_thread(self.window_controller.minimize)

    async def restore_window(self):
        """Biztonságos async visszaállítás."""
        return await asyncio.to_thread(self.window_controller.restore)
    
    async def _on_page_navigated(self, page: Page):
        """Callback, ami lefut, ha egy figyelt oldal 'load' eseménye bekövetkezik."""
        # logger.debug(f"Navigáció észlelve a lapon. Új URL: {page.url}")
        if self._on_navigation_callback:
            self._on_navigation_callback(page.url)

    async def _attach_navigation_listener_async(self, page: Page):
        if page and not page.is_closed():
            # A 'self._on_page_navigated' egy async függvény, ezért a loop workerrel kell futtatni
            # A lambda p=page trükk biztosítja, hogy a helyes 'page' objektum kerüljön átadásra
            page.on('load', lambda p=page: asyncio.create_task(self._on_page_navigated(p)))


    async def _handle_new_page(self, page: Page):
        """
        Ez a metódus hívódik meg, amikor a kontextusban új lap jön létre.
        """
        try:
            await page.wait_for_load_state('domcontentloaded', timeout=5000)
            # logger.info(f"Új lap nyílt meg a böngészőben! URL: {page.url}")

            # --- KIEGÉSZÍTÉS: AZ ÚJ LAPRA IS RÁKÖTJÜK A NAVIGÁCIÓFIGYELŐT ---
            await self._attach_navigation_listener_async(page)
            
            if self._on_new_page_callback:
                self._on_new_page_callback(page.url)
        except Exception as e:
            logger.warning(f"Nem sikerült lekérni az új lap állapotát: {e}")

            
    async def close_all_pages_async(self) -> None:
        """
        Bezárja az összes lapot, kivéve egyet, amit 'about:blank'-ra navigál,
        hogy a böngésző kontextus ne záródjon be.
        """
        if not self._context or getattr(self._context, "is_closed", lambda: False)():
            logger.warning("close_all_pages_async: Nincs aktív böngésző kontextus, nincs mit bezárni.")
            return

        try:
            all_pages = self._context.pages
            page_count = len(all_pages)
            logger.info(f"Lapok 'takarítása' indítva. Jelenlegi lapszám: {page_count}")

            if page_count == 0:
                self._page = None
                logger.info("Nincsenek nyitott lapok, a takarítás befejezve.")
                return
            
            # Megtartjuk az első lapot, a többit zárjuk be
            page_to_keep = all_pages[0]

            if page_count > 1:
                # A többi lapot párhuzamosan zárjuk be a hatékonyságért
                tasks = [page.close() for page in all_pages[1:] if not page.is_closed()]
                if tasks:
                    await asyncio.gather(*tasks)
                    logger.info(f"{len(tasks)} felesleges lap bezárva.")

            # A megmaradt egyetlen lapot "tisztítsuk ki"
            if not page_to_keep.is_closed():
                if page_to_keep.url != "about:blank":
                    await page_to_keep.goto("about:blank")
                # Biztosítjuk, hogy a belső hivatkozás erre a lapra mutasson
                self._page = page_to_keep
                logger.info("Egy lap megmaradt és 'about:blank'-ra navigálva.")
            else:
                self._page = None
                logger.warning("A megtartani kívánt lap időközben bezáródott.")

        except Exception as e:
            logger.exception(f"Hiba történt a lapok 'takarítása' közben: {e}")
            self._page = None