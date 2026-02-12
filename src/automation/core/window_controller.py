# src/automation/core/window_controller.py
import time
import logging
import pygetwindow as gw

logger = logging.getLogger(__name__)

class WindowController:
    """Böngésző ablak kezelése (minimize / restore / activate)."""

    def __init__(self, title_hint: str = "Chrome") -> None:
        self.title_hint = title_hint

    def _get_window(self, timeout: float = 10.0):
        """Megkeresi a Chrome/Chromium ablakot, amíg létre nem jön."""
        start = time.time()
        while time.time() - start < timeout:
            wins = gw.getWindowsWithTitle(self.title_hint)
            for w in wins:
                if "Chrome" in w.title or "Chromium" in w.title:
                    return w
            time.sleep(0.25)
        logger.warning(f"Nem találtam meg a '{self.title_hint}' ablakot {timeout}s alatt.")
        return None

    def minimize(self) -> bool:
        w = self._get_window()
        if not w:
            return False
        try:
            w.minimize()
            logger.info("Böngésző minimalizálva.")
            return True
        except Exception as e:
            logger.exception(f"Hiba a minimalizáláskor: {e}")
            return False

    def restore(self) -> bool:
        w = self._get_window()
        if not w:
            return False
        try:
            if w.isMinimized:
                try:
                    w.restore()
                    time.sleep(0.3)
                    w.activate()
                except Exception as e:
                    logger.warning(f"Első restore nem sikerült: {e}, újrapróbálom...")
                    time.sleep(1)
                    w.restore()
                    w.activate()
            logger.info("Böngésző visszaállítva.")
            return True
        except Exception as e:
            logger.exception(f"Hiba a visszaállításkor: {e}")
            return False
