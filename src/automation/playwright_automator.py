# src/automation/playwright_automator.py

import asyncio
import logging
from typing import Any, Optional

from playwright.async_api import Page
from PySide6.QtCore import QObject, QMetaObject, Qt, Signal, Slot, Q_ARG

from .core.async_loop_worker import AsyncLoopWorker
from .core.browser_manager import PlaywrightBrowserManager

logger = logging.getLogger(__name__)

class PlaywrightAutomator(QObject):
    statusUpdated = Signal(str, int, object)
    automationFinished = Signal(bool, str)
    browserManuallyClosed = Signal()
    workerShutdownCompleted = Signal()
    browserActiveStateChanged = Signal(bool)
    loopStarted = Signal()
    dataExtractionFinished = Signal(str, list, bool, str)
    browserLivenessChanged = Signal(bool)
    browserWindowStateChanged = Signal(str)
    newPageOpened = Signal(str)
    pageNavigated = Signal(str)

    def __init__(self, app_root_dir: str, settings_manager: Any, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.app_root_dir = app_root_dir
        self.settings_manager = settings_manager

        # --- BELSŐ ÁLLAPOTVÁLTOZÓ A BÖNGÉSZŐ ÁLLAPOTÁNAK KÖVETÉSÉRE ---
        self._is_browser_active = False

        self.loop_worker = AsyncLoopWorker()
        self.browser_manager = PlaywrightBrowserManager(
            app_root_dir, settings_manager,
            on_close_callback=self._on_manual_browser_close_from_worker,
            on_new_page_callback=self._on_new_page_from_worker,
            on_navigation_callback=self._on_page_navigated_from_worker
        )
        self._automation_future: Optional[asyncio.Future] = None

        # --- KAPCSOLAT A BELSŐ ÁLLAPOT FRISSÍTÉSÉHEZ ---
        # Ha a böngészőt manuálisan bezárják, frissítjük a belső állapotot és a UI-t
        self.browserManuallyClosed.connect(self._handle_browser_state_changed_to_inactive)

    @Slot()
    def _handle_browser_state_changed_to_inactive(self):
        """
        Ez a slot biztosítja, hogy a belső állapot és a UI frissüljön, ha a böngésző leáll.
        """
        if self._is_browser_active:
            logger.debug("Böngésző leállt, belső állapot frissítve INAKTÍV-ra.")
            self._is_browser_active = False
            self.browserActiveStateChanged.emit(False) # Jelezzük a UI-nak is!

    def start_event_loop(self) -> None:
        try:
            self.loop_worker.start()
            QMetaObject.invokeMethod(self, "loopStarted", Qt.QueuedConnection)
        except Exception as e:
            logger.exception("Nem sikerült elindítani az event loop-ot: %s", e)

    async def start_browser_for_background_task(self) -> bool:
        """
        KÖZPONTI METÓDUS: Biztosítja, hogy a böngésző fusson egy háttérfeladathoz.
        1. Elindítja, ha még nem fut.
        2. Ha az állapot OFF-ról ON-ra változott, értesíti a UI-t.
        3. A végén minimalizálja az ablakot.
        """
        success = await self.browser_manager.start_browser()

        if success:
            # Csak akkor jelezzük a UI-nak az állapot VÁLTOZÁSÁT, ha tényleg változott.
            if not self._is_browser_active:
                logger.debug("Böngésző elindult, belső állapot frissítve AKTÍV-ra.")
                self._is_browser_active = True
                self.browserActiveStateChanged.emit(True)

            # A szándéknak megfelelően minimalizáljuk a böngészőt.
            if not self.settings_manager.get_setting("browser_settings.headless", False):
                await asyncio.sleep(0.5)
                await self.browser_manager.minimize_window()
        else:
            # Ha a start_browser hibát ad vissza, biztosítjuk, hogy az állapot inaktív legyen.
            self._handle_browser_state_changed_to_inactive()
        
        return success

    def start_browser_only(self) -> None:
        """
        Elindítja a böngészőt a Toolbar gombjáról, háttérfeladatra optimalizálva.
        """
        try:
            # Az új, központi metódust ütemezzük. A UI értesítéséről már az gondoskodik.
            fut = self.loop_worker.run_coro_threadsafe(self.start_browser_for_background_task())
            
            def _done(future: asyncio.Future):
                try:
                    ok = future.result()
                    # Az 'automationFinished' jelzést továbbra is küldjük, hátha másnak kell.
                    self.automationFinished.emit(bool(ok), "StartBrowserOnly finished")
                except Exception as e:
                    self.automationFinished.emit(False, str(e))
            fut.add_done_callback(_done)
        except Exception as e:
            logger.exception("Hiba a 'start_browser_only' metódus ütemezésekor: %s", e)
            self.automationFinished.emit(False, str(e))
            self._handle_browser_state_changed_to_inactive()
            
    def close_browser(self, final_shutdown: bool = False) -> None:
        """Kezdeményezi a böngésző aszinkron bezárását."""
        try:
            fut = self.loop_worker.run_coro_threadsafe(self.browser_manager.close_browser(final_shutdown))
            def _done(future: asyncio.Future):
                try: future.result()
                except Exception as e: logger.exception("close_browser hiba: %s", e)
                # A tényleges állapotváltást a _on_manual_browser_close_from_worker callback indítja
            fut.add_done_callback(_done)
        except Exception as e: logger.exception("Hiba a 'close_browser' metódus ütemezésekor: %s", e)

    def _on_manual_browser_close_from_worker(self) -> None:
        """
        Ez a callback hívódik meg a böngésző kontextusának 'close' eseményére.
        """
        # A QueuedConnection biztosítja, hogy a jel a fő szálon kerüljön feldolgozásra.
        QMetaObject.invokeMethod(self, "browserManuallyClosed", Qt.QueuedConnection)

    def minimize_browser(self):
        if not self.loop_worker.is_running:
            return
        future = self.loop_worker.run_coro_threadsafe(
            self.browser_manager.minimize_window()
        )
        def on_done(fut):
            if not fut.cancelled() and not fut.exception():
                if fut.result():
                    self.browserWindowStateChanged.emit("minimized")
        future.add_done_callback(on_done)

    def restore_browser(self):
        if not self.loop_worker.is_running:
            return
        future = self.loop_worker.run_coro_threadsafe(
            self.browser_manager.restore_window()
        )
        def on_done(fut):
            if not fut.cancelled() and not fut.exception():
                if fut.result():
                    self.browserWindowStateChanged.emit("restored")
        future.add_done_callback(on_done)

    @Slot(str, int, object)
    def emit_status_update(self, message: str, level: int, color_override: Optional[Any] = None):
        """
        A külső modulok (pl. GS, FTP) hívják meg, hogy üzenetet küldjenek a GUI státuszbárjára.
        """
        self.statusUpdated.emit(message, level, color_override)

    @Slot()
    def stop_worker(self):
        if not self.loop_worker:
            logger.warning("LoopWorker nem inicializált – leállítás kihagyva.")
            self.workerShutdownCompleted.emit()
            return
        try:
            if self.loop_worker.is_running and self.browser_manager:
                future = self.loop_worker.run_coro_threadsafe(
                    self.browser_manager.close_browser(final_shutdown=True)
                )
                def on_done(_fut):
                    try: _fut.result()
                    except Exception as e: logger.warning(f"Leállítás közben hiba (böngésző bezárás): {e}")
                    finally:
                        self.loop_worker.request_stop()
                        self.workerShutdownCompleted.emit()
                future.add_done_callback(on_done)
            else:
                self.loop_worker.request_stop()
                self.workerShutdownCompleted.emit()
        except Exception as e:
            logger.exception(f"Váratlan hiba a stop_worker ütemezésekor: {e}")
            if self.loop_worker: self.loop_worker.request_stop()
            self.workerShutdownCompleted.emit()

    @Slot()
    def manual_close_browser(self):
        try:
            if not self.browser_manager:
                logger.warning("BrowserManager nem inicializált — kihagyva."); return
            if self.loop_worker and self.loop_worker.is_running:
                # Elindítjuk a bezárási folyamatot. Az állapotfrissítés a callback-en keresztül történik.
                self.close_browser(final_shutdown=False)
            else:
                logger.warning("Loop nem fut — a böngésző bezárása nem lehetséges.")
        except Exception as e: logger.exception(f"Hiba a manual_close_browser során: {e}")

    async def start_browser_and_navigate_for_task(self, url: str) -> tuple[bool, Optional[Page]]:
        """
        Elindítja a böngészőt, elnavigál a megadott URL-re, majd minimalizálja az ablakot.
        Ez egy atomi művelet a háttérfeladatok előkészítésére.
        Visszaad egy (siker, page_objektum) tuple-t.
        """
        # 1. Böngésző indításának biztosítása (de még nem minimalizáljuk!)
        success = await self.browser_manager.start_browser()
        if not success:
            self._handle_browser_state_changed_to_inactive()
            return False, None

        if not self._is_browser_active:
            self._is_browser_active = True
            self.browserActiveStateChanged.emit(True)

        # 2. Új, tiszta lap lekérése és navigáció
        try:
            page = await self.browser_manager._create_or_get_page(force_new=True)
            if not page:
                return False, None
            
            default_navigation_timeout = self.settings_manager.get_setting("browser_settings.default_navigation_timeout_ms", 30000)
            await page.goto(url, timeout=default_navigation_timeout, wait_until="load")

            # 3. Ablakcím visszaállítása és MINIMALIZÁLÁS a navigáció UTÁN
            if not self.settings_manager.get_setting("browser_settings.headless", False):
                automation_title = self.browser_manager._AUTOMATION_WINDOW_TITLE
                await page.evaluate(f"document.title = '{automation_title}'")
                await self.browser_manager.minimize_window()
            
            return True, page
        except Exception as e:
            logger.error(f"Hiba a navigáció és minimalizálás során ({url}): {e}", exc_info=True)
            return False, None
        
    async def ensure_browser_is_running_and_visible(self) -> bool:
        original_headless_setting = self.settings_manager.get_setting("browser_settings.headless", False)
        self.settings_manager.set_setting("browser_settings.headless", False)
        
        success = await self.browser_manager.start_browser()
        
        self.settings_manager.set_setting("browser_settings.headless", original_headless_setting)

        if success:
            if not self._is_browser_active:
                self._is_browser_active = True
                self.browserActiveStateChanged.emit(True)
            
            # Biztosítjuk, hogy az ablak ne legyen minimalizálva
            await self.browser_manager.restore_window()
            return True
        else:
            self._handle_browser_state_changed_to_inactive()
            return False
        
    @Slot(str)
    def _on_new_page_from_worker(self, url: str):
        """
        Ez a metódus a worker szálról hívódik. Feladata, hogy szálbiztosan
        kibocsássa a `newPageOpened` jelet a GUI szál felé.
        """
        QMetaObject.invokeMethod(
            self,
            "newPageOpened",
            Qt.QueuedConnection,
            Q_ARG(str, url)
        )

    @Slot(str)
    def _on_page_navigated_from_worker(self, url: str):
        """Szálbiztosan kibocsátja a pageNavigated jelet."""
        QMetaObject.invokeMethod(
            self,
            "pageNavigated",
            Qt.QueuedConnection,
            Q_ARG(str, url)
        )

    @Slot()
    def close_all_pages(self):
        """
        Elindítja az összes böngészőlap aszinkron bezárását a háttérszálon.
        """
        if not self.loop_worker.is_running:
            logger.warning("A háttérszál nem fut, a lapok bezárása nem lehetséges.")
            return
            
        try:
            # Ütemezzük a browser_manager-ben lévő új metódus futtatását
            future = self.loop_worker.run_coro_threadsafe(
                self.browser_manager.close_all_pages_async()
            )
            
            def on_done(fut: asyncio.Future):
                """Callback a művelet befejeződésekor."""
                exc = fut.exception()
                if exc:
                    logger.error(f"Hiba történt az összes lap bezárása közben: {exc}", exc_info=True)
                    self.statusUpdated.emit(f"Hiba a lapok bezárásakor: {exc}", logging.ERROR, "red")
                else:
                    logger.info("Minden böngészőlap sikeresen bezárva.")
                    self.statusUpdated.emit("Minden böngészőlap bezárva.", logging.INFO, "green")
            
            future.add_done_callback(on_done)
            
        except Exception as e:
            logger.exception("Hiba az 'close_all_pages' metódus ütemezésekor: %s", e)