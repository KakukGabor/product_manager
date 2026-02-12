import logging
import asyncio
import requests
import os
from pathlib import Path
from datetime import datetime

from PySide6.QtCore import QObject, Signal, Slot

from managers.settings_manager import SettingsManager
from automation.playwright_automator import PlaywrightAutomator
from models.product_model import Product

logger = logging.getLogger(__name__)

class FacebookAutomator(QObject):
    fbPostFinished = Signal(bool, str, str)

    def __init__(self, core_automator: PlaywrightAutomator, settings_manager: SettingsManager, parent=None):
        super().__init__(parent)
        self.core_automator = core_automator # A loop worker miatt kell még
        self.settings_manager = settings_manager

    def _log(self, level: int, message: str, *args, **kwargs):
        color = kwargs.pop('color_override', None)
        logger.log(level, f"[FB_API] {message}", *args, **kwargs)
        try:
            gui_message = message % args if args else message
        except TypeError:
            gui_message = message
        self.core_automator.emit_status_update(gui_message, level, color)

    def _upload_photo_to_fb(self, page_id: str, access_token: str, image_path: str) -> str:
        """
        Feltölt egy képet a Facebookra, de nem teszi közzé (published=False).
        Visszaadja a kép FB ID-ját.
        """
        url = f"https://graph.facebook.com/v21.0/{page_id}/photos"
        
        payload = {
            'access_token': access_token,
            'published': 'false' # Fontos: ne jelenjen meg azonnal, csak gyűjtjük
        }
        
        try:
            with open(image_path, 'rb') as img_file:
                files = {'source': img_file}
                response = requests.post(url, data=payload, files=files)
                
            response_data = response.json()
            
            if response.status_code == 200 and 'id' in response_data:
                return response_data['id']
            else:
                error_msg = response_data.get('error', {}).get('message', 'Ismeretlen hiba')
                raise RuntimeError(f"Képfeltöltési hiba: {error_msg}")
                
        except Exception as e:
            raise RuntimeError(f"Hiba a kép küldésekor ({Path(image_path).name}): {e}")

    async def _run_fb_api_post_async(self, product: Product):
        """Aszinkron wrapper a szinkron requests hívásokhoz."""
        success = False
        message = ""
        
        # Mivel a requests könyvtár blokkoló (szinkron), egy külön szálon futtatjuk,
        # hogy ne fagyassza be a GUI-t.
        try:
            await asyncio.to_thread(self._post_logic_sync, product)
            success = True
            message = "Sikeres posztolás a Facebook API-n keresztül!"
        except Exception as e:
            success = False
            message = f"Facebook API Hiba: {e}"
            self._log(logging.ERROR, message, exc_info=True)
        finally:
            self.fbPostFinished.emit(success, message, product.id)

    def _post_logic_sync(self, product: Product):
        """A tényleges posztolási logika (szinkron módon)."""
        
        # 1. Beállítások betöltése
        page_id = self.settings_manager.get_setting("site_configs.facebook.page_id")
        access_token = self.settings_manager.get_setting("site_configs.facebook.access_token")

        if not page_id or not access_token:
            raise ValueError("Hiányzó Facebook Page ID vagy Access Token! Állítsd be a Beállításokban.")

        # 2. Szöveg összeállítása
        if not product.facebook_data:
            raise ValueError("Nincsenek Facebook adatok a termékhez.")
            
        post_text = product.facebook_data.post_text or ""
        hashtags = product.facebook_data.hashtags or ""
        
        # --- MÓDOSÍTÁS: A poszt szövege CSAK a leírás, hashtagek nélkül ---
        full_message = post_text.strip()
        # -----------------------------------------------------------------

        # 3. Képek összegyűjtése
        selected_images = product.facebook_data.selected_images
        if not selected_images:
            raise ValueError("Nincs kijelölt kép a posztoláshoz.")

        # Kép útvonalak keresése (a Path javítással együtt)
        product_path = Path(self.core_automator.app_root_dir) / "app_data_storage" / "processed" / "product_library" / product.main_category_slug / (product.sub_category_slug or "egyeb") / (product.product_type_slug or "egyeb") / f"product_{product.id}" / "images"
        
        valid_image_paths = []
        for img_name in selected_images:
            full_path = product_path / img_name
            if full_path.exists():
                valid_image_paths.append(str(full_path))
            else:
                self._log(logging.WARNING, f"Kép nem található: {img_name}")

        if not valid_image_paths:
            raise FileNotFoundError("Egyetlen kiválasztott képfájl sem található a lemezen.")

        # 4. Képek feltöltése egyesével
        self._log(logging.INFO, f"{len(valid_image_paths)} db kép feltöltése a Facebook szerverére...", color_override="processing")
        uploaded_photo_ids = []
        
        for i, img_path in enumerate(valid_image_paths):
            self._log(logging.INFO, f"Kép feltöltése ({i+1}/{len(valid_image_paths)})...", color_override="processing")
            photo_id = self._upload_photo_to_fb(page_id, access_token, img_path)
            uploaded_photo_ids.append(photo_id)

        # 5. A végső poszt (Feed) létrehozása a képekkel
        self._log(logging.INFO, "Végleges poszt közzététele...", color_override="processing")
        
        feed_url = f"https://graph.facebook.com/v21.0/{page_id}/feed"
        
        # Az attached_media formátuma: [{"media_fbid": "ID1"}, {"media_fbid": "ID2"}]
        attached_media = [{'media_fbid': pid} for pid in uploaded_photo_ids]
        
        feed_payload = {
            'access_token': access_token,
            'message': full_message,
            'attached_media': attached_media 
        }
        
        response = requests.post(feed_url, json=feed_payload)
        response_data = response.json()
        
        if response.status_code == 200 and 'id' in response_data:
            post_id = response_data['id']
            self._log(logging.INFO, f"Sikeres poszt! ID: {post_id}", color_override="green")
            
            # --- ÚJ RÉSZ: Hashtagek beküldése KOMMENTKÉNT ---
            if hashtags:
                self._log(logging.INFO, "Hashtagek hozzáadása kommentként...", color_override="processing")
                try:
                    comment_url = f"https://graph.facebook.com/v21.0/{post_id}/comments"
                    comment_payload = {
                        'access_token': access_token,
                        'message': hashtags
                    }
                    requests.post(comment_url, data=comment_payload)
                    self._log(logging.INFO, "Hashtagek sikeresen hozzászólásba téve.", color_override="green")
                except Exception as e:
                    # Ha a kommentelés nem sikerül, attól még a poszt sikeres volt, nem dobunk hibát, csak jelzünk
                    self._log(logging.WARNING, f"Nem sikerült a hashtageket kommentelni (a poszt azért kiment): {e}")
            # ------------------------------------------------

            # Adatok frissítése a terméken
            product.facebook_data.is_posted = True
            product.facebook_data.posted_at = datetime.now()
            product.facebook_data.post_id = post_id
            
            # URL generálása
            clean_post_id = post_id.split('_')[-1] # Ha PAGEID_POSTID formátumú
            product.facebook_data.post_url = f"https://www.facebook.com/{clean_post_id}"
            
        else:
            error_msg = response_data.get('error', {}).get('message', 'Ismeretlen hiba')
            raise RuntimeError(f"Hiba a posztoláskor: {error_msg}")

    @Slot(Product)
    def start_fb_post_flow(self, product: Product):
        """Ezt hívja a Controller."""
        self.core_automator.loop_worker.run_coro_threadsafe(
            self._run_fb_api_post_async(product)
        )