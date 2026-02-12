# src/managers/ftp_manager.py
import asyncio
import collections
import logging
import os
from pathlib import Path
from typing import Optional, List, Dict, Any, TYPE_CHECKING

import pysftp
import stat

from PySide6.QtCore import QObject, Signal, Slot

from managers.settings_manager import SettingsManager
from models.product_model import Product, _sanitize_for_slug
from managers.product_manager import ProductManager

if TYPE_CHECKING:
    from automation.playwright_automator import PlaywrightAutomator

logger = logging.getLogger(__name__)

class FtpManager(QObject):
    ftpOperationFinished = Signal(bool, str, str, bool)
    statusUpdated = Signal(str, int, object)
    connectionStateChanged = Signal(bool)

    def __init__(self, core_automator: 'PlaywrightAutomator', settings_manager: SettingsManager, product_manager: ProductManager, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.core_automator = core_automator
        self.settings_manager = settings_manager
        self.product_manager = product_manager
        self._sftp_connection: Optional[pysftp.Connection] = None
        self._is_connected = False

    def _log(self, level: int, message: str, *args, color_override: Optional[str] = None, emit_status_signal: bool = True, **kwargs):
        logger.log(level, f"[SFTP] {message}", *args, **kwargs)
        if emit_status_signal:
            try:
                gui_message = message % args if args else message
            except TypeError:
                gui_message = message
            self.statusUpdated.emit(gui_message, level, color_override)

    def is_ftp_connected(self) -> bool:
        return self._is_connected

    async def _connect_sftp_async(self):
        host = self.settings_manager.get_setting("server_settings.ftp_host")
        user = self.settings_manager.get_setting("server_settings.ftp_user")
        passwd = self.settings_manager.get_setting("server_settings.ftp_pass")
        port = self.settings_manager.get_setting("server_settings.ftp_port", 22)

        if not all([host, user, passwd]):
            raise ValueError("Hiányzó SFTP beállítások (host, user, vagy pass).")

        cnopts = pysftp.CnOpts()
        cnopts.hostkeys = None

        def connect_action():
            return pysftp.Connection(host=host, username=user, password=passwd, port=port, cnopts=cnopts)

        self._sftp_connection = await asyncio.to_thread(connect_action)
        self._is_connected = True
        # A GUI-t frissítő jelkibocsátás ELTÁVOLÍTVA. Csak a logba írunk.
        self._log(logging.INFO, f"Sikeres SFTP csatlakozás a(z) '{host}:{port}' szerverhez.", emit_status_signal=False)
        # self.connectionStateChanged.emit(True)  <-- EZT A SORT TÖRÖLD KI VAGY KOMMENTELD KI

    async def _disconnect_sftp_async(self):
        if not self._is_connected or not self._sftp_connection:
            return

        await asyncio.to_thread(self._sftp_connection.close)
        self._sftp_connection = None
        self._is_connected = False
        # A GUI-t frissítő jelkibocsátás ELTÁVOLÍTVA.
        self._log(logging.INFO, "SFTP kapcsolat bontva.", emit_status_signal=False)
        # self.connectionStateChanged.emit(False) <-- EZT A SORT TÖRÖLD KI VAGY KOMMENTELD KI

    async def _ensure_remote_dir_async(self, remote_dir: str) -> bool:
        if not self._sftp_connection:
            return False
        cleaned_remote_dir = remote_dir.replace("\\", "/").strip("/")
        try:
            await asyncio.to_thread(self._sftp_connection.makedirs, cleaned_remote_dir)
            return True
        except Exception as e:
            self._log(logging.ERROR, f"Hiba a távoli könyvtár létrehozása során '{cleaned_remote_dir}': {e}", color_override="red")
            return False

    async def _upload_file_async(self, local_path: Path, full_remote_path: str) -> bool:
        if not self._sftp_connection:
            return False
        try:
            remote_path_cleaned = full_remote_path.replace("\\", "/")
            await asyncio.to_thread(self._sftp_connection.put, str(local_path), remote_path_cleaned)
            return True
        except Exception as e:
            self._log(logging.ERROR, f"SFTP fájlfeltöltési hiba '{local_path.name}'-hoz ide: '{full_remote_path}': {e}", color_override="red")
            return False

    async def _upload_product_data_async(self, product: Product):
        operation_id = f"upload_{product.id}"
        
        try:
            await self._connect_sftp_async()

            # --- 1. ÚTVONALAK DEFINIÁLÁSA (változatlan) ---
            local_product_dir = self.product_manager._get_product_path_from_product_object(product)
            local_json_path = self.product_manager._get_product_json_path(local_product_dir)
            if not local_json_path.exists():
                raise FileNotFoundError(f"A termék adatfájlja (JSON) nem található: {local_json_path}")

            relative_local_path = local_product_dir.relative_to(self.product_manager._base_product_dir)
            remote_product_path = Path("product_manager") / "product" / relative_local_path
            remote_product_dir_str = str(remote_product_path).replace("\\", "/")
            remote_images_dir_str = str(remote_product_path / "images").replace("\\", "/")

            # --- 2. MAPPÁK LÉTREHOZÁSA ÉS VÁRAKOZÁS (változatlan, de a sleep itt marad) ---
            if not await self._ensure_remote_dir_async(remote_images_dir_str):
                raise IOError("Nem sikerült létrehozni a távoli könyvtárakat.")
            
            # Ez a várakozás a biztonság kedvéért itt marad, hátha a mappalétrehozás lassú.
            await asyncio.sleep(1)

            # --- 3. JSON FÁJL FELTÖLTÉSE (változatlan) ---
            remote_json_path = f"{remote_product_dir_str}/{local_json_path.name}"
            if not await self._upload_file_async(local_json_path, remote_json_path):
                raise IOError(f"'{product.title}' adatfájljának (JSON) feltöltése sikertelen.")
            self._log(logging.DEBUG, f"Termék JSON sikeresen feltöltve: {remote_json_path}", emit_status_signal=False)

            # === JAVÍTOTT LOGIKA KEZDETE: Először feltöltünk, utána takarítunk ===

            # --- 4. ÚJ 'mixed_' KÉPEK FELTÖLTÉSE ---
            local_images_dir = local_product_dir / "images"
            local_mixed_images = [f for f in local_images_dir.iterdir() if f.is_file() and f.name.lower().startswith("mixed_")] if local_images_dir.exists() else []
            
            images_to_upload_count = len(local_mixed_images)
            images_success_count = 0
            if images_to_upload_count > 0:
                self._log(logging.INFO, f"Új 'mixed_' képek feltöltése ({images_to_upload_count} db)...", emit_status_signal=False)
                for image_path in local_mixed_images:
                    remote_image_path = f"{remote_images_dir_str}/{image_path.name}"
                    if await self._upload_file_async(image_path, remote_image_path):
                        images_success_count += 1
            
            if images_success_count != images_to_upload_count:
                raise IOError(f"'{product.title}': Részleges képfeltöltés: {images_success_count}/{images_to_upload_count}.")

            # --- 5. SZERVER OLDALI TAKARÍTÁS (RÉGI KÉPEK TÖRLÉSE) ---
            self._log(logging.INFO, f"Szerver oldali takarítás: régi 'mixed_' képek keresése...", emit_status_signal=False)
            try:
                # Most, hogy a feltöltés befejeződött, biztonságosan listázhatunk.
                remote_files_on_server = await asyncio.to_thread(self._sftp_connection.listdir, remote_images_dir_str)
                local_mixed_filenames = {f.name for f in local_mixed_images}
                
                delete_tasks = []
                for filename in remote_files_on_server:
                    # Csak azokat a 'mixed_' fájlokat töröljük, amik nincsenek a helyi listában.
                    if filename.lower().startswith("mixed_") and filename not in local_mixed_filenames:
                        full_remote_path_to_delete = f"{remote_images_dir_str}/{filename}"
                        self._log(logging.DEBUG, f"Régi kép törlésre jelölve: {full_remote_path_to_delete}", emit_status_signal=False)
                        delete_tasks.append(
                            asyncio.to_thread(self._sftp_connection.remove, full_remote_path_to_delete)
                        )
                
                if delete_tasks:
                    await asyncio.gather(*delete_tasks)
                    self._log(logging.INFO, f"{len(delete_tasks)} db elavult 'mixed_' kép sikeresen törölve a szerverről.", emit_status_signal=False)

            except Exception as e:
                # Ha a takarítás nem sikerül, az már nem blokkolja a sikeres feltöltés jelzését.
                self._log(logging.WARNING, f"Hiba a szerver oldali takarítás során (a feltöltés sikeres volt): {e}", color_override="orange")

            # === JAVÍTOTT LOGIKA VÉGE ===

            self.ftpOperationFinished.emit(True, f"'{product.title}' adatai és képei ({images_success_count} db) sikeresen feltöltve.", operation_id, False)

        except Exception as e:
            msg = f"Hiba a(z) '{product.title}' feltöltésekor: {e}"
            self._log(logging.ERROR, msg, color_override="red")
            self.ftpOperationFinished.emit(False, msg, operation_id, True)
        finally:
            await self._disconnect_sftp_async()

        async def _delete_product_from_ftp_async(self, product: Product) -> tuple[bool, str, str, bool]:
            """
            Biztonságosan, egy háttérszálon törli a termék mappáját az SFTP szerverről.
            NEM bocsát ki jelet, hanem egy tuple-ben visszaadja az eredményt a hívónak.
            Visszatérési érték: (siker, üzenet, operation_id, hiba_történt_e)
            """
            operation_id = f"delete_{product.id}"

            def _sync_delete_worker() -> tuple[bool, str, bool]:
                """Belső worker függvény, ami a blokkoló I/O műveletet végzi."""
                sftp_conn = None
                try:
                    host = self.settings_manager.get_setting("server_settings.ftp_host")
                    user = self.settings_manager.get_setting("server_settings.ftp_user")
                    passwd = self.settings_manager.get_setting("server_settings.ftp_pass")
                    port = self.settings_manager.get_setting("server_settings.ftp_port", 22)
                    if not all([host, user, passwd]):
                        raise ValueError("Hiányzó SFTP beállítások.")

                    cnopts = pysftp.CnOpts(); cnopts.hostkeys = None
                    sftp_conn = pysftp.Connection(host=host, username=user, password=passwd, port=port, cnopts=cnopts)
                    
                    remote_product_dir = self.product_manager._get_product_path_from_product_object(product)
                    relative_path = remote_product_dir.relative_to(self.product_manager._base_product_dir)
                    remote_path_str = str(Path("product_manager") / "product" / relative_path).replace('\\', '/')

                    def _recursive_delete(path_to_delete: str):
                        for item in sftp_conn.listdir_attr(path_to_delete):
                            full_item_path = f"{path_to_delete}/{item.filename}"
                            if stat.S_ISDIR(item.st_mode): _recursive_delete(full_item_path)
                            else: sftp_conn.remove(full_item_path)
                        sftp_conn.rmdir(path_to_delete)

                    try:
                        sftp_conn.listdir(remote_path_str)
                        _recursive_delete(remote_path_str)
                        msg = f"'{product.title}' sikeresen törölve az SFTP szerverről."
                        return (True, msg, False)
                    except IOError:
                        msg = f"'{product.title}' nem található az SFTP-n, törlés sikeresnek tekintve."
                        return (True, msg, False)
                except Exception as e:
                    msg = f"SFTP hiba a(z) '{product.title}' törlésekor: {e}"
                    self._log(logging.ERROR, msg, exc_info=True, emit_status_signal=False)
                    return (False, msg, True)
                finally:
                    if sftp_conn: sftp_conn.close()

            try:
                success, message, is_error = await asyncio.to_thread(_sync_delete_worker)
                return success, message, operation_id, is_error
            except Exception as e:
                msg = f"Váratlan hiba a törlési szál indításakor: {e}"
                self._log(logging.CRITICAL, msg, exc_info=True, emit_status_signal=False)
                return False, msg, operation_id, True

    @Slot()
    def connect_ftp_slot(self):
        async def test_connection():
            try:
                await self._connect_sftp_async()
                self.statusUpdated.emit(f"Sikeres SFTP tesztkapcsolat.", logging.INFO, "green")
            except Exception as e:
                self._log(logging.ERROR, f"SFTP kapcsolódási hiba: {e}", color_override="red")
            finally:
                await self._disconnect_sftp_async()
        
        self.core_automator.loop_worker.run_coro_threadsafe(test_connection())

    async def connect_async(self) -> bool:
        try:
            await self._connect_sftp_async()
            # A metódus egyszerűen csak visszaadja, hogy sikerült-e.
            return True
        except Exception as e:
            self._log(logging.ERROR, f"SFTP kapcsolódási hiba: {e}", color_override="red")
            self._is_connected = False
            # Nem bocsátunk ki jelet, a hívó kezeli a hibát.
            # self.connectionStateChanged.emit(False) <-- BIZTOSAN NE LEGYEN ITT
            return False

    @Slot()
    def disconnect_ftp_slot(self):
        self.core_automator.loop_worker.run_coro_threadsafe(self._disconnect_sftp_async())

    @Slot(Product)
    def upload_product_data_slot(self, product: Product):
        self.core_automator.loop_worker.run_coro_threadsafe(self._upload_product_data_async(product))

    @Slot(Product)
    def delete_product_from_ftp_slot(self, product: Product):
        self._log(logging.INFO, f"Parancs érkezett a(z) '{product.title}' törlésére az SFTP szerverről.", color_override="blue")
        self.core_automator.loop_worker.run_coro_threadsafe(self._delete_product_from_ftp_async(product))

    async def delete_product_from_ftp_async(self, product: Product) -> tuple[bool, str, str, bool]:
        """
        Biztonságosan, egy háttérszálon törli a termék mappáját az SFTP szerverről.
        NEM bocsát ki jelet, hanem egy tuple-ben visszaadja az eredményt a hívónak.
        Visszatérési érték: (siker, üzenet, operation_id, hiba_történt_e)
        """
        operation_id = f"delete_{product.id}"

        def _sync_delete_worker() -> tuple[bool, str, bool]:
            """Belső worker függvény, ami a blokkoló I/O műveletet végzi."""
            sftp_conn = None
            try:
                host = self.settings_manager.get_setting("server_settings.ftp_host")
                user = self.settings_manager.get_setting("server_settings.ftp_user")
                passwd = self.settings_manager.get_setting("server_settings.ftp_pass")
                port = self.settings_manager.get_setting("server_settings.ftp_port", 22)
                if not all([host, user, passwd]):
                    raise ValueError("Hiányzó SFTP beállítások.")

                cnopts = pysftp.CnOpts(); cnopts.hostkeys = None
                sftp_conn = pysftp.Connection(host=host, username=user, password=passwd, port=port, cnopts=cnopts)
                
                remote_product_dir = self.product_manager._get_product_path_from_product_object(product)
                relative_path = remote_product_dir.relative_to(self.product_manager._base_product_dir)
                remote_path_str = str(Path("product_manager") / "product" / relative_path).replace('\\', '/')

                def _recursive_delete(path_to_delete: str):
                    for item in sftp_conn.listdir_attr(path_to_delete):
                        full_item_path = f"{path_to_delete}/{item.filename}"
                        if stat.S_ISDIR(item.st_mode): _recursive_delete(full_item_path)
                        else: sftp_conn.remove(full_item_path)
                    sftp_conn.rmdir(path_to_delete)

                try:
                    sftp_conn.listdir(remote_path_str)
                    _recursive_delete(remote_path_str)
                    msg = f"'{product.title}' sikeresen törölve az SFTP szerverről."
                    return (True, msg, False)
                except IOError:
                    msg = f"'{product.title}' nem található az SFTP-n, törlés sikeresnek tekintve."
                    return (True, msg, False)
            except Exception as e:
                msg = f"SFTP hiba a(z) '{product.title}' törlésekor: {e}"
                self._log(logging.ERROR, msg, exc_info=True, emit_status_signal=False)
                return (False, msg, True)
            finally:
                if sftp_conn: sftp_conn.close()

        try:
            success, message, is_error = await asyncio.to_thread(_sync_delete_worker)
            return success, message, operation_id, is_error
        except Exception as e:
            msg = f"Váratlan hiba a törlési szál indításakor: {e}"
            self._log(logging.CRITICAL, msg, exc_info=True, emit_status_signal=False)
            return False, msg, operation_id, True

    def _recursive_find_product_ids_on_thread(self, sftp_conn: pysftp.Connection, remote_path: str, found_ids: set):
        """
        Rekurzívan bejár egy távoli könyvtárat az SFTP kapcsolaton keresztül,
        és összegyűjti az összes 'product_*' nevű mappa ID-ját.
        """
        try:
            for attr in sftp_conn.listdir_attr(remote_path):
                current_item_path = f"{remote_path}/{attr.filename}"
                if stat.S_ISDIR(attr.st_mode):
                    if attr.filename.startswith("product_"):
                        product_id = attr.filename.replace("product_", "")
                        if product_id:
                            found_ids.add(product_id)
                    elif attr.filename not in ('.', '..'):
                        self._recursive_find_product_ids_on_thread(sftp_conn, current_item_path, found_ids)
        except Exception as e:
            self._log(logging.WARNING, f"Hiba a(z) '{remote_path}' távoli mappa olvasásakor: {e}", emit_status_signal=False)

    async def _get_all_remote_product_ids_async(self) -> Optional[set]:
        """
        Végigpásztázza a távoli 'product_manager/product' könyvtárat, és visszaadja
        az összes talált termék ID-t egy set-ben. Hiba esetén None-t ad vissza.
        JAVÍTVA: A megbízhatatlan walktree helyett rekurzív listdir_attr hívást használ.
        """
        self._log(logging.INFO, "Távoli termék ID-k listázása a szerverről...", color_override="processing")
        try:
            await self._connect_sftp_async()
            if not self._sftp_connection:
                raise ConnectionError("SFTP kapcsolat nem jött létre.")
            remote_base_dir = "product_manager/product"
            if not await asyncio.to_thread(self._sftp_connection.exists, remote_base_dir):
                self._log(logging.WARNING, f"A távoli alapkönyvtár ('{remote_base_dir}') nem létezik.", color_override="orange")
                return set()
            remote_product_ids = set()
            await asyncio.to_thread(
                self._recursive_find_product_ids_on_thread,
                self._sftp_connection,
                remote_base_dir,
                remote_product_ids
            )
            self._log(logging.INFO, f"{len(remote_product_ids)} termék ID azonosítva a szerveren.", emit_status_signal=False)
            return remote_product_ids
        except Exception as e:
            self._log(logging.ERROR, f"Hiba a távoli termék ID-k listázása közben: {e}", color_override="red")
            return None
        finally:
            await self._disconnect_sftp_async()

    # --- ÚJ RÉSZ ---
    @Slot(bool, bool)
    def upload_full_database_slot(self, upload_json: bool, upload_images: bool):
        """Slot, ami elindítja a teljes adatbázis aszinkron feltöltését."""
        self.core_automator.loop_worker.run_coro_threadsafe(
            self.upload_full_database_async(upload_json, upload_images)
        )

    async def upload_full_database_async(self, upload_json: bool, upload_images: bool):
        """
        Végigmegy az összes nem eladott terméken, és a paramétereknek megfelelően
        feltölti az adatfájlokat és/vagy a 'mixed_' képeket.
        JAVÍTVA: A képek feltöltése előtt törli a távoli 'images' mappa tartalmát.
        """
        all_products = [p for p in self.product_manager.get_all_products() if not p.is_sold]
        total_products = len(all_products)
        self._log(logging.INFO, f"Teljes adatbázis feltöltése indítva ({total_products} aktív termék). JSON: {upload_json}, Képek: {upload_images}", color_override="processing")

        success_count = 0
        error_count = 0

        try:
            await self._connect_sftp_async()

            for i, product in enumerate(all_products):
                self._log(logging.INFO, f"Feldolgozás ({i+1}/{total_products}): '{product.title}' (ID: {product.id})", emit_status_signal=False)
                
                try:
                    local_product_dir = self.product_manager._get_product_path_from_product_object(product)
                    relative_local_path = local_product_dir.relative_to(self.product_manager._base_product_dir)
                    remote_product_path = Path("product_manager") / "product" / relative_local_path
                    remote_product_dir_str = str(remote_product_path).replace("\\", "/")
                    remote_images_dir_str = str(remote_product_path / "images").replace("\\", "/")

                    await self._ensure_remote_dir_async(remote_images_dir_str)

                    # Termék adatlap (.json) feltöltése
                    if upload_json:
                        local_json_path = self.product_manager._get_product_json_path(local_product_dir)
                        if local_json_path.exists():
                            remote_json_path = f"{remote_product_dir_str}/{local_json_path.name}"
                            await self._upload_file_async(local_json_path, remote_json_path)
                        else:
                            self._log(logging.WARNING, f"A(z) '{product.id}' JSON fájlja hiányzik, kihagyva.", emit_status_signal=False)
                    
                    # Szerkesztett képek ('mixed_') feltöltése
                    if upload_images:
                        
                        # <<< JAVÍTÁS KEZDETE: Törlés a feltöltés előtt >>>
                        try:
                            self._log(logging.DEBUG, f"Távoli képmappa tartalmának törlése: {remote_images_dir_str}", emit_status_signal=False)
                            # Lekérdezzük a fájlokat és egyenként töröljük őket
                            for filename in await asyncio.to_thread(self._sftp_connection.listdir, remote_images_dir_str):
                                await asyncio.to_thread(self._sftp_connection.remove, f"{remote_images_dir_str}/{filename}")
                            self._log(logging.DEBUG, f"Távoli képmappa sikeresen kiürítve.", emit_status_signal=False)
                        except Exception as delete_error:
                            # Nem baj, ha a mappa nem létezik vagy üres, a listdir hibát dobhat. Ezt figyelmen kívül hagyjuk.
                            self._log(logging.DEBUG, f"A távoli képmappa kiürítése nem volt szükséges (valószínűleg üres): {delete_error}", emit_status_signal=False)
                        # <<< JAVÍTÁS VÉGE >>>
                        
                        local_images_dir = local_product_dir / "images"
                        if local_images_dir.exists():
                            local_mixed_images = [f for f in local_images_dir.iterdir() if f.is_file() and f.name.lower().startswith("mixed_")]
                            
                            for image_path in local_mixed_images:
                                remote_image_path = f"{remote_images_dir_str}/{image_path.name}"
                                await self._upload_file_async(image_path, remote_image_path)
                    
                    success_count += 1

                except Exception as product_error:
                    self._log(logging.ERROR, f"Hiba a(z) '{product.id}' termék feltöltésekor: {product_error}", color_override="red")
                    error_count += 1
            
            final_message = f"Adatbázis feltöltése befejeződött. Sikeres: {success_count}, Hibás: {error_count}."
            final_color = "green" if error_count == 0 else "orange"
            self._log(logging.INFO, final_message, color_override=final_color)

        except Exception as e:
            self._log(logging.CRITICAL, f"Kritikus hiba az adatbázis-feltöltés során: {e}", color_override="red")
        finally:
            await self._disconnect_sftp_async()
            # A folyamat végén a lista frissítése, hogy a státuszok (pl. needs_upload) megjelenjenek
            self.product_manager.load_all_products_sync()
    
    def _recursive_find_product_locations_on_thread(self, sftp_conn: pysftp.Connection, remote_path: str, id_locations: dict):
        """
        Rekurzívan bejár egy távoli könyvtárat, és feltölti az id_locations szótárat
        a talált 'product_*' mappák ID-jaival és útvonalaival.
        """
        try:
            for attr in sftp_conn.listdir_attr(remote_path):
                current_item_path = f"{remote_path}/{attr.filename}"
                if stat.S_ISDIR(attr.st_mode):
                    if attr.filename.startswith("product_"):
                        product_id = attr.filename.replace("product_", "")
                        if product_id:
                            # A gyökérhez képesti relatív útvonalat tároljuk
                            relative_path = current_item_path.replace("product_manager/product/", "", 1)
                            id_locations[product_id].append(relative_path)
                    elif attr.filename not in ('.', '..'):
                        # Csak akkor megyünk mélyebbre, ha nem egy termékmappában vagyunk
                        self._recursive_find_product_locations_on_thread(sftp_conn, current_item_path, id_locations)
        except Exception as e:
            self._log(logging.WARNING, f"Hiba a(z) '{remote_path}' távoli mappa olvasásakor: {e}", emit_status_signal=False)

    async def find_duplicate_products_on_server_async(self) -> Optional[Dict[str, List[str]]]:
        """
        Végigpásztázza a távoli szervert, és visszaad egy szótárat, amely a duplikált
        termék ID-ket és a hozzájuk tartozó útvonal-listákat tartalmazza.
        Hiba esetén None-t ad vissza.
        """
        self._log(logging.INFO, "Szerveroldali duplikált termék ID-k keresése...", color_override="processing")
        try:
            await self._connect_sftp_async()
            if not self._sftp_connection:
                raise ConnectionError("SFTP kapcsolat nem jött létre.")
            
            remote_base_dir = "product_manager/product"
            if not await asyncio.to_thread(self._sftp_connection.exists, remote_base_dir):
                self._log(logging.WARNING, f"A távoli alapkönyvtár ('{remote_base_dir}') nem létezik.", color_override="orange")
                return {}

            id_locations = collections.defaultdict(list)
            await asyncio.to_thread(
                self._recursive_find_product_locations_on_thread,
                self._sftp_connection,
                remote_base_dir,
                id_locations
            )
            
            duplicates = {id: paths for id, paths in id_locations.items() if len(paths) > 1}
            self._log(logging.INFO, f"{len(duplicates)} db duplikált termék ID azonosítva a szerveren.", emit_status_signal=False)
            return duplicates

        except Exception as e:
            self._log(logging.ERROR, f"Hiba a szerveroldali duplikátumok keresése közben: {e}", color_override="red")
            return None
        finally:
            await self._disconnect_sftp_async()