# src/managers/ai_manager.py
import logging
from typing import Optional

from PySide6.QtCore import QObject, Signal, Slot
import google.generativeai as genai

from managers.settings_manager import SettingsManager
from automation.core.async_loop_worker import AsyncLoopWorker

logger = logging.getLogger(__name__)

class AIManager(QObject):
    descriptionGenerated = Signal(str, bool, str) # Leírás, Siker, Üzenet
    statusUpdated = Signal(str, int, object)

    def __init__(self, settings_manager: SettingsManager, loop_worker: AsyncLoopWorker, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.loop_worker = loop_worker
        self._model = None
        self._initialize_model()

    def _initialize_model(self):
        api_key = self.settings_manager.get_setting("ai_settings.google_api_key")
        if not api_key:
            self.statusUpdated.emit("AI: Google API kulcs hiányzik, az AI funkciók nem elérhetőek.", logging.WARNING, "orange")
            return

        try:
            genai.configure(api_key=api_key)
            self._model = genai.GenerativeModel('gemini-pro-latest')
            self.statusUpdated.emit("AI: Google Gemini modell sikeresen inicializálva.", logging.INFO, "green")
        except Exception as e:
            self.statusUpdated.emit(f"AI: Hiba az AI modell inicializálásakor: {e}", logging.ERROR, "red")
            logger.error(f"Hiba az AI modell inicializálásakor: {e}", exc_info=True)

    @Slot(str)
    def generate_description(self, product_title: str):
        if not self._model:
            self.descriptionGenerated.emit("", False, "AI modell nincs inicializálva. Ellenőrizze az API kulcsot!")
            return

        async def generation_task():
            prompt = (
                f"Viselkedj profi marketingesként, aki antik bútorokra specializálódott. "
                f"Írj egy rövid, de megnyerő, 3-4 mondatos termékleírást magyarul "
                f"a következő termékhez: '{product_title}'. Koncentrálj a stílusra, az eleganciára és a minőségre."
            )
            try:
                # Az API hívás blokkoló, ezért egy háttérszálon kell futtatni
                response = await self.loop_worker._loop.run_in_executor(
                    None, lambda: self._model.generate_content(prompt)
                )
                self.descriptionGenerated.emit(response.text, True, "AI: Leírás sikeresen generálva.")
            except Exception as e:
                logger.error(f"Hiba az AI válasz generálásakor: {e}", exc_info=True)
                self.descriptionGenerated.emit("", False, f"AI hiba: {e}")

        self.loop_worker.run_coro_threadsafe(generation_task())