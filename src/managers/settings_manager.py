# managers/settings_manager.py
import os
import json
import logging
from datetime import datetime
from pathlib import Path
from config.app_folders import APP_FOLDER_STRUCTURE
from config.app_settings import get_default_settings
from config.app_folders import (
    FOLDER_APP_DATA,
    FOLDER_CHROME_PROFILE,
)

logger = logging.getLogger(__name__)

class SettingsManager:
    """
    A beállítások kezelésére szolgáló osztály, amely JSON fájlba menti/tölti be
    a beállításokat, biztosítva a hordozhatóságot.
    """
    def __init__(self, filename="settings.json", app_root_path: Path = None):
        """
        Inicializálja a SettingsManager osztályt.
        """
        self.app_root_path = app_root_path if app_root_path else Path(os.getcwd())
        self.recursive_create_dirs(self.app_root_path, APP_FOLDER_STRUCTURE)
        self.filepath = self.app_root_path / filename 
        self.settings = {}
      
        self._default_settings = self._get_default_settings_structure() 

        if not self.filepath.exists():
            logger.info(f"Beállítás fájl nem található ({self.filepath}). Alapértelmezett beállítások létrehozása.")
            self.settings = self._default_settings.copy()
            self.save_settings()
        else:
            self.load_settings()
            self.settings = self._merge_settings(self._default_settings.copy(), self.settings)
        
        self.save_settings()

    def load_settings(self):
        """
        Betölti a beállításokat a JSON fájlból.
        """
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                loaded_settings = json.load(f)
                self.settings = loaded_settings
            logger.debug(f"Beállítások sikeresen betöltve: {self.filepath}")
        except json.JSONDecodeError:
            logger.error(f"Érvénytelen JSON formátum a beállítás fájlban: {self.filepath}. Alapértelmezett beállítások létrehozása.")
            self.settings = self._default_settings.copy()
            self.save_settings()
        except IOError:
            logger.error(f"Nem olvasható beállítás fájl: {self.filepath}. Alapértelmezett beállítások létrehozása.")
            self.settings = self._default_settings.copy()
            self.save_settings()

    def save_settings(self):
        """
        Elmenti az aktuális beállításokat a JSON fájlba.
        """
        try:
            # Gondoskodunk róla, hogy a szülőkönyvtár létezzen, mielőtt írunk bele
            self.filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=4, ensure_ascii=False)
            logger.debug(f"Beállítások sikeresen mentve: {self.filepath}")
        except IOError as e:
            logger.error(f"Nem sikerült menteni a beállítás fájlt: {self.filepath}. Hiba: {e}")

    def get_setting(self, path: str, default=None):
        """
        Beállítás lekérdezése a megadott útvonal alapján.
        A pontokkal elválasztott útvonalakat (pl. "group.subgroup.key") kezeli.

        Args:
            path (str): A beállítás útvonala (pl. "client_settings.download_folder").
            default: Az alapértelmezett érték, ha a beállítás nem található.

        Returns:
            Az eltárolt érték, vagy az alapértelmezett érték.
        """
        keys = path.split('.')
        current_level = self.settings
        for key in keys:
            if isinstance(current_level, dict) and key in current_level:
                current_level = current_level[key]
            else:
                return default
        return current_level

    def set_setting(self, path: str, value):
        """
        Beállítás mentése a megadott útvonalra.
        A pontokkal elválasztott útvonalakat (pl. "group.subgroup.key") kezeli,
        és létrehozza a hiányzó szótárakat az útvonal mentén.

        Args:
            path (str): A beállítás útvonala.
            value: Az eltárolandó érték.
        """
        keys = path.split('.')
        current_level = self.settings
        for i, key in enumerate(keys):
            if i == len(keys) - 1:
                if isinstance(current_level, dict):
                    current_level[key] = value
                else:
                    raise TypeError(f"A '{key}' kulcs nem szótárban van az útvonalban: {path}. Frissítés sikertelen.")
            else:
                if isinstance(current_level, dict):
                    if key not in current_level or not isinstance(current_level[key], dict):
                        current_level[key] = {}
                    current_level = current_level[key]
                else:
                    raise TypeError(f"A '{key}' kulcs nem szótárban van az útvonalban: {path}. Hiányzó köztes szótár nem hozható létre.")
        self.save_settings()

    def _merge_settings(self, default: dict, current: dict):
        """
        Rekurzívan összefésüli az alapértelmezett beállításokat a jelenlegi beállításokkal.
        Az alapértelmezett értékek hozzáadódnak, ha hiányoznak a jelenlegi beállításokból,
        de a meglévő értékek nem íródnak felül.
        """
        for key, default_value in default.items():
            if key not in current:
                current[key] = default_value
            elif isinstance(default_value, dict) and isinstance(current.get(key), dict):
                current[key] = self._merge_settings(default_value, current[key])
        return current

    def _get_default_settings_structure(self):
        """
        Visszaadja az alapértelmezett beállítások struktúráját.
        """
        return get_default_settings(self.app_root_path)

    @property
    def is_first_run(self) -> bool:
        """
        Visszaadja, hogy ez az alkalmazás első futása-e a 'general_settings.is_first_run' alapján.
        """
        return self.get_setting("general_settings.is_first_run", True)

    @is_first_run.setter
    def is_first_run(self, value: bool):
        """
        Beállítja a 'general_settings.is_first_run' értékét.
        """
        self.set_setting("general_settings.is_first_run", value)

    @property
    def app_root(self) -> Path:
        """
        Az alkalmazás gyökérkönyvtárának elérési útja (Path objektumként).
        """
        return self.app_root_path
    
    @property
    def browser_profile_path(self) -> Path:
        """Visszaadja a böngésző profil mappájának teljes, hordozható útvonalát."""
        return self.app_root_path / FOLDER_APP_DATA / FOLDER_CHROME_PROFILE

    def recursive_create_dirs(self, base_path: Path, structure: dict):
        """
        Rekurzívan bejárja a 'structure' szótárat és létrehozza a mappákat
        a 'base_path' könyvtáron belül.
        """
        for folder_name, sub_structure in structure.items():
            current_path = base_path / folder_name
            try:
                current_path.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                logger.error(f"Hiba a mappa létrehozásakor '{current_path}': {e}")
                # Hiba esetén a rekurzió nem folytatódik ezen az ágon
                continue

            # Ha vannak almappák, hívjuk meg önmagunkat az új útvonallal
            if isinstance(sub_structure, dict) and sub_structure:
                self.recursive_create_dirs(current_path, sub_structure)