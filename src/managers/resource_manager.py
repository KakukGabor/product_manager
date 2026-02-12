# src/managers/resource_manager.py
import os
from pathlib import Path
from copy import deepcopy

class ResourceManager:
    """
    Egy központi osztály az alkalmazás erőforrásainak (ikonok, konfigurációk)
    kezelésére. Inicializáláskor megkapja az alkalmazás gyökérútvonalát,
    és relatív útvonalakból teljes, használható útvonalakat generál.
    """
    def __init__(self, app_root_path: Path):
        self.app_root_path = app_root_path
        self.icon_base_path = str(self.app_root_path / "res" / "icons") + os.sep

        self._TOOLBAR_CONFIG_POOL = {
            "main_horizontal": [
                {"id": "ftp_toggle", "type": "two_state",
                 "icon_off_path": "ftp_off.png", "icon_on_path": "ftp_on.png",
                 "tooltip": "FTP csatlakozás/leválasztás"},
                {"id": "browser_toggle", "type": "two_state",
                 "icon_off_path": "chrome_off.png", "icon_on_path": "chrome_on.png",
                 "tooltip": "Böngésző indítása/leállítása"},
                {"id": "gs_auto_btn", "type": "simple_push",
                 "icon_path": "gs_auto.png", "tooltip": "Galéria Savaria automatizálás"},
                {"id": "jf_auto_btn", "type": "simple_push",
                 "icon_path": "jf_auto.png", "tooltip": "Jófogás automatizálás"},
                {"id": "fb_auto_btn", "type": "simple_push",
                 "icon_path": "fb_auto.png", "tooltip": "Facebook automatizálás"},
                {"id": "add_product_btn", "type": "simple_push",
                 "icon_path": "add_product.png", "tooltip": "Új termék hozzáadása"},
                {"id": "check_database_btn", "type": "simple_push",
                 "icon_path": "check_database.png", "tooltip": "Adatbázis ellenőrzése és karbantartása"}, 
                {"id": "text_editor_toggle", "type": "two_state",
                 "icon_off_path": "text_editor_off.png", "icon_on_path": "text_editor_on.png",
                 "tooltip": "Szövegszerkesztő nyitása/zárása"},
                 {"id": "ai_generate_desc", "type": "simple_push",
                 "icon_path": "ai_magic.png", "tooltip": "Termékleírás generálása AI-val"},
                 {"id": "settings_toggle", "type": "two_state",
                 "icon_off_path": "settings_off.png", "icon_on_path": "settings_on.png",
                 "tooltip": "Beállítások megnyitása/bezárása"},
            ],
            
            "text_editor_toolbar": [
                 {"id": "load_btn", "type": "simple_push", "icon_path": "folder_open.png", "tooltip": "Fájl betöltése"},
                 {"id": "save_btn", "type": "simple_push", "icon_path": "save.png", "tooltip": "Fájl mentése"},
                 {"id": "bold_btn", "type": "two_state", "icon_off_path": "bold_off.png", "icon_on_path": "bold_on.png", "tooltip": "Félkövér"},
                 {"id": "special_chr_btn", "type": "simple_push", "icon_path": "special_chr.png", "tooltip": "Speciális karakterek beszúrása"},
            ],

            "list_view_toolbar": [
                {"id": "filter_btn", "type": "two_state",
                 "icon_off_path": "filter_off.png", "icon_on_path": "filter_on.png",
                 "tooltip": "Szűrőfeltételek megadása"},
                
                {"id": "search_btn", "type": "two_state",
                 "icon_off_path": "search_off.png", "icon_on_path": "search_on.png",
                 "tooltip": "Keresés szöveg alapján"},
                
                {"id": "mark_btn", "type": "two_state",
                 "icon_off_path": "list_mark_off.png", "icon_on_path": "list_mark_on.png",
                 "tooltip": "Termékek megjelölése állapot szerint"},

                {"id": "list_plus_btn", "type": "simple_push", "icon_path": "plus.png", "tooltip": "Lista nagyítása"},
                {"id": "list_minus_btn", "type": "simple_push", "icon_path": "minus.png", "tooltip": "Lista kicsinyítése"},
            ]
        }
        
        self._DIALOG_ICONS = {
            "warning": "warning_icon.png",
            "error": "error_icon.png",
            "info": "info_icon.png",
            "question": "question_icon.png",
            "console_down": "console_down.png",
            "console_up": "console_up.png",
            "arrow_up": "arrow_up.png",
            "arrow_down": "arrow_down.png",
            "trash": "trash.png"
        }

    def get_toolbar_config(self, toolbar_name: str) -> list[dict]:
        """
        Visszaadja egy adott nevű eszköztár teljes, feldolgozott konfigurációját.
        """
        raw_config = self._TOOLBAR_CONFIG_POOL.get(toolbar_name, [])
        if not raw_config:
            return []

        processed_config = deepcopy(raw_config)

        for item in processed_config:
            for key, value in item.items():
                if key.startswith("icon_") and isinstance(value, str):
                    item[key] = self.icon_base_path + value
        
        return processed_config

    def get_icon_path(self, icon_name: str) -> str:
        """
        Visszaadja egy általános célú ikon teljes elérési útvonalát.
        """
        relative_path = self._DIALOG_ICONS.get(icon_name)
        if relative_path:
            return self.icon_base_path + relative_path
        return ""