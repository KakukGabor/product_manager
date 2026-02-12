# controllers/main_controller.py
import logging
import asyncio
import os
from typing import Optional, Dict, List, Callable, Coroutine
from PySide6.QtCore import QObject, Signal, Slot, QTimer, Qt
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from automation.playwright_automator import PlaywrightAutomator
from managers.ai_manager import AIManager
from managers.product_manager import ProductManager
from automation.sites.gs_automator import GaleriaSavariaAutomator
from automation.sites.jofogas_automator import JofogasAutomator
from automation.sites.fb_automator import FacebookAutomator
from gui.settings_dialog import SettingsDialog
from managers.ftp_manager import FtpManager
from gui.product_list_view.product_list_view import ProductListView
from gui.product_detail_widget.product_detail_widget import ProductDetailWidget
from gui.image_gallery_widget.image_gallery_widget import ImageGalleryWidget
from gui.product_list_view.search_dialog import SearchDialog
from gui.product_list_view.filter_dialog import FilterDialog
from gui.product_list_view.mark_dialog import MarkDialog
from models.product_model import Product
from controllers.text_editor_controller import TextEditorController 
from gui.product_detail_widget.pdw_states import NewGsProductState
from gui.product_detail_widget.remove_from_markets_dialog import RemoveFromMarketsDialog
from playwright.async_api import Page, TimeoutError
from gui.database_check_dialog import DatabaseCheckDialog
from gui.product_detail_widget.description_format_dialog import DescriptionFormatDialog
from managers.email_manager import EmailManager
from gui.email_dialog import EmailDialog
from gui.upload_database_dialog import UploadDatabaseDialog

logger = logging.getLogger(__name__)

class MainController(QObject):
    updateToolbarButtonState = Signal(str, bool, bool)
    updateStatusBar = Signal(str, int, object)

    def __init__(self, playwright_automator: PlaywrightAutomator, product_manager: ProductManager,
                  gs_automator: GaleriaSavariaAutomator, jf_automator: JofogasAutomator,
                  fb_automator: FacebookAutomator,
                  ai_manager: AIManager, 
                  ftp_manager: FtpManager, 
                  email_manager: EmailManager,
                  text_editor_controller: TextEditorController,
                  parent=None):
        super().__init__(parent)

        self._settings_dialog: Optional[SettingsDialog] = None
        self.playwright_automator = playwright_automator
        self.product_manager = product_manager
        self.gs_automator = gs_automator
        self.jofogas_automator = jf_automator
        self.fb_automator = fb_automator
        self.ai_manager = ai_manager
        self.ftp_manager = ftp_manager
        self.email_manager = email_manager
        self.text_editor_controller = text_editor_controller

        self._product_list_view: Optional[ProductListView] = None
        self._product_detail_widget: Optional[ProductDetailWidget] = None
        self._image_gallery_widget: Optional[ImageGalleryWidget] = None
        self._filter_dialog: Optional[FilterDialog] = None
        self._search_dialog: Optional[SearchDialog] = None
        self._mark_dialog: Optional[MarkDialog] = None
        self._current_marking: str = "none"
        self._last_selected_product_id: Optional[str] = None
        self._current_filters: Dict = {}
        self._is_batch_processing = False
        self._last_sort_column = 0
        self._last_sort_order = Qt.AscendingOrder
        self._pending_gs_validation_product: Optional[Product] = None
        self._jofogas_deletion_task: Optional[asyncio.Task] = None
        self._currently_watched_product_id: Optional[str] = None
        self._database_check_dialog: Optional[DatabaseCheckDialog] = None
        self._upload_database_dialog: Optional[UploadDatabaseDialog] = None
        self._description_format_dialog: Optional[DescriptionFormatDialog] = None
       
        # --- SZIGNÁL-SLOT KAPCSOLATOK ---
        self.playwright_automator.browserActiveStateChanged.connect(self._handle_browser_active_state_changed)
        self.playwright_automator.browserManuallyClosed.connect(self._handle_browser_manually_closed)
        self.playwright_automator.statusUpdated.connect(self.updateStatusBar)
        self.playwright_automator.automationFinished.connect(self._handle_automation_finished)

        self.ai_manager.statusUpdated.connect(self.updateStatusBar)
        self.ai_manager.descriptionGenerated.connect(self._handle_ai_description_generated)

        self.ftp_manager.statusUpdated.connect(self.updateStatusBar)
        self.ftp_manager.connectionStateChanged.connect(self._handle_ftp_connection_state_changed)
        
        self.email_manager.emailSent.connect(self._handle_email_sent)

        self.product_manager.productsLoaded.connect(self._handle_products_loaded)
        self.product_manager.productAdded.connect(self._handle_product_added)
        self.product_manager.productUpdated.connect(self._handle_product_updated)
        self.product_manager.productDeleted.connect(self._handle_product_deleted)
        self.product_manager.productsBatchProcessed.connect(self._on_products_batch_processed)
        self.ftp_manager.ftpOperationFinished.connect(self._handle_ftp_operation_finished)
        self.text_editor_controller.editorClosed.connect(self._on_text_editor_closed)
        self.product_manager.gsProcessingReportReady.connect(self._handle_gs_report)
        self.product_manager.jfProcessingReportReady.connect(self._handle_jf_report)
        self.gs_automator.gsFormFillingFinished.connect(self._handle_gs_form_filling_finished)
        self.gs_automator.gsProductValidationFinished.connect(self._handle_gs_product_validation_finished)
        self.playwright_automator.newPageOpened.connect(self._handle_new_browser_page)
        self.playwright_automator.pageNavigated.connect(self._handle_page_navigation)
        self.gs_automator.gsSemiAutoLocateFinished.connect(self._handle_gs_product_semi_auto_locate_finished)
        self.product_manager.reportGenerated.connect(self._handle_report_generated)
        self.fb_automator.fbPostFinished.connect(self._handle_fb_post_finished)
        self.product_manager.productLoadingErrors.connect(self._handle_product_loading_errors)

    def set_main_widgets(self, list_view, detail_widget, gallery_widget):
        self._product_list_view = list_view
        self._product_detail_widget = detail_widget
        self._image_gallery_widget = gallery_widget
        
        self._product_list_view.productSelected.connect(self._on_product_selected)
        self._product_detail_widget.productUpdated.connect(self._on_product_save_request)
        self._product_detail_widget.categoryChanged.connect(self.product_manager.change_product_category_sync)
        self._product_detail_widget.newProductModeCancelled.connect(self._on_new_product_cancelled)
        self._product_detail_widget.productMarkedAsSold.connect(self._on_product_mark_as_sold)
        self._product_detail_widget.productUploadRequested.connect(self.handle_product_upload_request)
        self._product_list_view.sortOrderChanged.connect(self._save_sort_order)
        self._product_detail_widget.formModeChanged.connect(self._handle_form_mode_change)
        self.ftp_manager.connectionStateChanged.connect(self._product_detail_widget.update_toolbar_state)
        self._product_detail_widget.productReactivated.connect(self.product_manager.reactivate_product_sync)
        self._product_detail_widget.productPermanentlyDeleted.connect(self.product_manager.delete_product_permanently_sync)
        self._product_detail_widget.gsNewProductFillRequested.connect(self.gs_automator.run_gs_new_product_fill_flow)
        self._product_detail_widget.jfNewProductFillRequested.connect(self.jofogas_automator.run_jf_new_product_fill_flow)
        self._product_detail_widget.gsNewProductValidateRequested.connect(self._handle_gs_validation_request)
        self._product_detail_widget.removeFromMarketsRequested.connect(self._handle_remove_from_markets_request)
        self._product_detail_widget.refreshJofogasAdRequested.connect(self._handle_refresh_jofogas_ad_request)
        self._product_detail_widget.descriptionFormatRequested.connect(self.handle_description_format_request)
        self._product_detail_widget.detailToolbar.buttonClicked.connect(self._handle_detail_toolbar_click)
        self._product_detail_widget.productExportRequested.connect(self.handle_product_export_request)
        self._product_detail_widget.fbPostRequested.connect(self.fb_automator.start_fb_post_flow)

    def set_filter_dialog(self, dialog: FilterDialog):
        self._filter_dialog = dialog
        self._filter_dialog.applyFilters.connect(self._apply_detailed_filters)
        self._filter_dialog.clearFilters.connect(self.clear_filters)

    def set_settings_dialog(self, dialog: SettingsDialog):
        self._settings_dialog = dialog

    def _update_filter_button_states(self):
        """
        Ellenőrzi az aktív szűrőket, és kölcsönösen kizáró módon frissíti
        a filter/search gombok állapotát (ON/OFF és Engedélyezett/Letiltott).
        """
        
        # 1. Állapotok megállapítása
        is_search_active = "search_term" in self._current_filters
        
        search_keys = {"search_term", "search_in_title", "search_in_description"}
        is_filter_active = any(key not in search_keys for key in self._current_filters)
        
        # 2. Engedélyezettségi állapotok kiszámítása a kölcsönös kizárás alapján
        # A keresőgomb csak akkor engedélyezett, ha a részletes szűrő NEM aktív.
        search_btn_is_enabled = not is_filter_active
        # A szűrőgomb csak akkor engedélyezett, ha a szöveges keresés NEM aktív.
        filter_btn_is_enabled = not is_search_active
        
        # 3. Jelek kibocsátása a frissített állapotokkal
        # A jel harmadik paramétere (is_action_enabled) vezérli az engedélyezettséget.
        self.updateToolbarButtonState.emit("search_btn", is_search_active, search_btn_is_enabled)
        self.updateToolbarButtonState.emit("filter_btn", is_filter_active, filter_btn_is_enabled)

    @Slot(str)
    def _handle_form_mode_change(self, mode: str):
        """
        Kezeli a termékadatlap állapotváltozását (pl. szerkesztés, új, nézet).
        Letiltja az "Új termék" gombot, ha a felhasználó már szerkeszt egy terméket.
        """
        is_editing_or_new = mode in ("new_product", "editing_existing")
        is_enabled = not is_editing_or_new
        self.updateToolbarButtonState.emit("add_product_btn", False, is_enabled)
        
        logger.debug(f"Form mode changed to '{mode}'. 'Add Product' button enabled: {is_enabled}")

    @Slot()
    def handle_text_editor_request(self):
        logger.info("Szövegszerkesztő kérés kezelése...")
        self.updateToolbarButtonState.emit("text_editor_toggle", True, True) # Gombot bekapcsoljuk
        self.text_editor_controller.show_editor()

    # <-- JAVÍTÁS: Új slot, ami visszaállítja a gombot, ha a dialógus bezárul
    @Slot()
    def _on_text_editor_closed(self):
        logger.info("Szövegszerkesztő bezárult, toolbar gomb frissítése.")
        self.updateToolbarButtonState.emit("text_editor_toggle", False, True) # Gombot kikapcsoljuk

    # --- A fájl többi része változatlan ---
    
    @Slot()
    def handle_settings_request(self):
        if not self._settings_dialog:
            logger.error("A beállítások dialógusablak nincs beállítva a controllerben!")
            return
        self.updateToolbarButtonState.emit("settings_toggle", True, False)
        self._settings_dialog._load_settings_to_ui()
        self._settings_dialog.exec()
        self.updateToolbarButtonState.emit("settings_toggle", False, True)

    @Slot(bool)
    def handle_browser_button_click(self, should_be_on: bool):
        self.updateToolbarButtonState.emit("browser_toggle", should_be_on, False)
        if should_be_on:
            self.playwright_automator.start_browser_only()
        else:
            self.playwright_automator.manual_close_browser()

    @Slot(bool)
    def _handle_browser_active_state_changed(self, is_active: bool):
        self.updateToolbarButtonState.emit("browser_toggle", is_active, True)
    
    @Slot()
    def _handle_browser_manually_closed(self):
        self.updateToolbarButtonState.emit("browser_toggle", False, True)

    @Slot()
    def handle_app_shutting_down(self):
        self.playwright_automator.stop_worker()

    @Slot(list, bool, str)
    def _handle_products_loaded(self, products: list, success: bool, message: str):
        if success:
            # A rendezési beállítások beolvasása
            self._last_sort_column = self.playwright_automator.settings_manager.get_setting("client_settings.list_view_sort_column", 6)
            sort_order_int = self.playwright_automator.settings_manager.get_setting("client_settings.list_view_sort_order", 1)
            self._last_sort_order = Qt.SortOrder(sort_order_int)
            
            if self._product_list_view:
                id_to_reselect = self._last_selected_product_id

                self._product_list_view.set_products(
                    products,
                    # Átadjuk a mentett ID-t a metódusnak.
                    product_id_to_select=id_to_reselect,
                    initial_sort_column=self._last_sort_column,
                    initial_sort_order=self._last_sort_order
                )
        else:
            logger.error(f"Controller: Termékbetöltési hiba: {message}")
            self.updateStatusBar.emit(f"Termékbetöltési hiba: {message}", logging.ERROR, "red")

    @Slot(bool, str)
    def _handle_automation_finished(self, success: bool, message: str):
        logger.debug(f"Automatizálási feladat befejeződött. Siker: {success}, Üzenet: {message}")

    @Slot()
    def start_gs_data_extraction(self):
        logger.info("Controller: Parancs kiadva a teljes GS adatkinyerési folyamat végrehajtására.")
        self._is_batch_processing = True # <-- MÓDOSÍTÁS
        gs_products_url = self.playwright_automator.settings_manager.get_setting("site_configs.galeria_savaria.products_url")
        
        if gs_products_url:
            self.gs_automator.run_full_extraction_flow(gs_products_url)
        else:
            logger.error("A Galéria Savaria termék URL nincs beállítva a settings.json-ben!")
            self._is_batch_processing = False # Hiba esetén kapcsoljuk ki
            
    @Slot()
    def start_jf_data_extraction(self):
        logger.info("Controller: Parancs kiadva a Jófogás adatkinyerési folyamat végrehajtására.")
        self.jofogas_automator.extract_jofogas_ads()

    @Slot(bool)
    def handle_ftp_toggle_click(self, should_be_on: bool):
        self.updateToolbarButtonState.emit("ftp_toggle", should_be_on, False)
        if should_be_on:
            self.ftp_manager.connect_ftp_slot()
        else:
            self.ftp_manager.disconnect_ftp_slot()
            
    @Slot(bool)
    def _handle_ftp_connection_state_changed(self, is_connected: bool):
        self.updateToolbarButtonState.emit("ftp_toggle", is_connected, True)

    @Slot()
    def handle_generate_description_click(self):
        example_product = "Restaurált Alt Deutsch tálalószekrény"
        self.updateStatusBar.emit(f"AI: Leírás generálása ehhez: '{example_product}'...", logging.INFO, "blue")
        self.ai_manager.generate_description(example_product)

    @Slot(str, bool, str)
    def _handle_ai_description_generated(self, description: str, success: bool, message: str):
        if success:
            logger.info(f"AI által generált leírás:\n---\n{description}\n---")
            self.updateStatusBar.emit(message, logging.INFO, "green")
        else:
            self.updateStatusBar.emit(message, logging.ERROR, "red")

    @Slot(Product, bool, str)
    def _handle_product_added(self, product: Product, success: bool, message: str):
        """Kezeli, amikor egy ÚJ termék kerül hozzáadásra."""
        if self._is_batch_processing:
            return

        if success:
            logger.info(f"Controller: Új termék hozzáadva ({product.id}). Lista frissítése.")
            if self._product_list_view:
                # A helyes metódus hívása: add_product
                self._product_list_view.add_product(product, success, message)
                # Időzített kiválasztás, hogy a táblázatnak legyen ideje frissülni
                QTimer.singleShot(100, lambda: self._product_list_view.select_product_by_id(product.id, force_scroll_to_top=True))

    @Slot(Product, bool, str)
    def _handle_product_updated(self, product: Product, success: bool, message: str):
        """Kezeli, amikor egy MEGLÉVŐ termék frissül."""
        if self._is_batch_processing:
            return
        
        if success:
            logger.info(f"Controller: Meglévő termék frissítve ({product.id}). Lista frissítése.")
            if self._product_list_view:
                # A helyes metódus hívása: update_product
                self._product_list_view.update_product(product, success, message)
                # Itt is biztosíthatjuk a kiválasztást, ha esetleg megváltozna
                QTimer.singleShot(100, lambda: self._product_list_view.select_product_by_id(product.id, force_scroll_to_top=False))

        if self._product_detail_widget and self._last_selected_product_id == product.id:
                logger.info(f"A jelenleg megjelenített termék ({product.id}) frissült a háttérben. A részletező nézet újratöltése.")
                # A set_product metódus újratölti az adatokat és frissíti a gombok állapotát is.
                self._product_detail_widget.set_product(product)

    @Slot(str)
    def _on_product_selected(self, product_id: Optional[str]):
        if self._jofogas_deletion_task and not self._jofogas_deletion_task.done():
            self._jofogas_deletion_task.cancel()
            self._jofogas_deletion_task = None
            self._currently_watched_product_id = None
            self.updateStatusBar.emit("Jófogás törlés figyelése megszakítva a termékváltás miatt.", logging.INFO, "red")
            logger.info("A futó Jófogás törlésfigyelő leállítva a termékváltás miatt.")

        self._last_selected_product_id = product_id
        logger.debug(f"Controller: Termék kiválasztva a listában: {product_id}")
        if self._product_detail_widget:
            self._product_detail_widget.set_product_by_id(product_id)
        if self._image_gallery_widget:
            self._image_gallery_widget.set_product_id(product_id)
            
    @Slot(Product, bool, str)
    def _on_product_save_request(self, product: Product, success: bool, message: str):
        if success:
            logger.info(f"Controller: Mentési kérés érkezett a DetailWidget-től a '{product.id or 'ÚJ'}' termékre.")
            self.product_manager.add_or_update_product_sync(product)

    @Slot()
    def handle_add_product_request(self):
        if self._image_gallery_widget:
            self._image_gallery_widget.clear_temporary_images()
        if self._product_detail_widget and self._product_detail_widget.is_form_active_for_editing_or_new():
            self.updateStatusBar.emit("Kérjük, fejezze be az aktuális szerkesztést, mielőtt újat kezdene.", logging.WARNING, "orange")
            return

        # Mentsük el az aktuális ID-t, mielőtt bármit csinálnánk
        if self._product_list_view:
            self._last_selected_product_id = self._product_list_view.get_selected_product_id()
            logger.debug(f"Controller: 'Új termék' mód előtt az utolsó kijelölt ID elmentve: {self._last_selected_product_id}")
            
            # --- JAVÍTÁS ---
            # Töröljük a kijelölést a listából a vizuális konzisztencia érdekében.
            self._product_list_view.table_widget.clearSelection()

        # --- JAVÍTÁS ---
        # Explicit módon állítsuk be mindkét widgetet "Új termék" (None) módba.
        # Ez a legbiztosabb módja annak, hogy az állapotuk szinkronban legyen.
        if self._product_detail_widget:
            self._product_detail_widget.set_product(None)
        if self._image_gallery_widget:
            # Ez a kulcsfontosságú hívás, ami a képkezelőt ideiglenes módba kapcsolja.
            self._image_gallery_widget.set_product_id(None)

    @Slot()
    def _on_new_product_cancelled(self):
        logger.info("Controller: 'Új termék' mód visszavonva, előző vagy első termék visszaállítása.")
        if self._image_gallery_widget:
            self._image_gallery_widget.clear_temporary_images()
        if self._product_list_view:
            id_to_select = self._last_selected_product_id
            
            # Ha valamiért nincs utolsó ID, válasszuk a lista legelső elemét
            if id_to_select is None and self._product_list_view.table_widget.rowCount() > 0:
                id_to_select = self._product_list_view.get_product_id_at_row(0)

            # 1. Állítsuk vissza a kijelölést a listában.
            self._product_list_view.select_product_by_id(id_to_select)
            
            # 2. JAVÍTÁS: Explicit módon frissítsük az adatlapot és a képgalériát,
            #    mivel a select_product_by_id nem feltétlenül vált ki jelet.
            if self._product_detail_widget:
                self._product_detail_widget.set_product_by_id(id_to_select)
            if self._image_gallery_widget:
                self._image_gallery_widget.set_product_id(id_to_select)
        
    @Slot(str, bool)
    def _on_product_mark_as_sold(self, product_id: str, delete_permanently: bool):
        product_object = self.product_manager.get_product_by_id(product_id)
        if not product_object:
            QMessageBox.critical(None, "Hiba", "A művelethez szükséges termék nem található.")
            return

        future = None
        if delete_permanently:
            self.updateStatusBar.emit(f"Szerver oldali végleges törlés indítása: '{product_object.title}'...", logging.INFO, "processing")
            # A metódus hívása JAVÍTVA (nincs aláhúzás)
            future = self.playwright_automator.loop_worker.run_coro_threadsafe(
                self.ftp_manager.delete_product_from_ftp_async(product_object)
            )
        else:
            self.updateStatusBar.emit(f"Termék eladása a szerveren: '{product_object.title}'...", logging.INFO, "processing")
            future = self.playwright_automator.loop_worker.run_coro_threadsafe(
                self._run_sell_product_flow(product_object)
            )

        def on_sell_flow_finished(fut: asyncio.Future):
            try:
                success, message, operation_id, is_error = fut.result()
                
                if message == "Connection Failed":
                    self._handle_ftp_connection_state_changed(False)
                    reply = QMessageBox.question(
                        None, "FTP Kapcsolódási Hiba",
                        "Nem sikerült csatlakozni az FTP szerverhez.\n\nSzeretné a műveletet csak helyben végrehajtani?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No
                    )
                    if reply == QMessageBox.StandardButton.Yes:
                        if delete_permanently:
                             self.updateStatusBar.emit("Figyelem: A termék csak helyben lett véglegesen törölve!", logging.WARNING, "orange")
                             self.product_manager.delete_product_permanently_sync(product_id)
                        else:
                            self._handle_offline_sell(product_id)
                    else:
                        self.updateStatusBar.emit("Művelet megszakítva.", logging.INFO, None)
                    return

                self._handle_ftp_connection_state_changed(True)
                if self._product_detail_widget:
                    self._product_detail_widget.update_toolbar_state()

                if operation_id != f"delete_{product_object.id}":
                    return

                if success and not is_error:
                    if delete_permanently:
                        self.product_manager.delete_product_permanently_sync(product_id)
                        self.updateStatusBar.emit(f"'{product_object.title}' véglegesen törölve.", logging.INFO, "green")
                    else:
                        self.product_manager.mark_product_as_sold_sync(product_id)
                        self.updateStatusBar.emit(f"'{product_object.title}' eladva és a szerverről eltávolítva.", logging.INFO, "green")
                else:
                    self.updateStatusBar.emit(f"Hiba a szerver oldali művelet közben: {message}", logging.ERROR, "red")

            except Exception as e:
                self.updateStatusBar.emit(f"Kritikus hiba az eladási folyamat során: {e}", logging.CRITICAL, "red")
        
        future.add_done_callback(on_sell_flow_finished)

    @Slot()
    def handle_filter_request(self):
        if self._filter_dialog:
            logger.info("Controller: Szűrő dialógus megjelenítése.")
            self._filter_dialog.set_current_filters(self._current_filters)
            
            result = self._filter_dialog.exec()
            
            if result == QDialog.Accepted:
                pass
            else:
                logger.info("Controller: Szűrő dialógus elvetve, gombok állapotának újraszinkronizálása.")
                self._update_filter_button_states()

    @Slot(dict)
    def apply_filters(self, filters: dict):
        """Ez a slot mostantól csak a szöveges keresésért felel."""
        logger.info(f"Controller: Szöveges keresés alkalmazása: {filters}")
        
        # Először töröljük a régi keresési feltételeket
        self._current_filters.pop("search_term", None)
        self._current_filters.pop("search_in_title", None)
        self._current_filters.pop("search_in_description", None)
        
        # Majd hozzáadjuk az újakat
        self._current_filters.update(filters)
        
        self.product_manager.apply_filters(self._current_filters)
        self._update_filter_button_states()

    @Slot(dict)
    def _apply_detailed_filters(self, filters: dict):
        """ÚJ SLOT: Ez kifejezetten a FilterDialog-ból érkező szűrőket kezeli."""
        logger.info(f"Controller: Részletes szűrők alkalmazása: {filters}")

        # 1. Definiáljuk az összes kulcsot, ami a FilterDialog-ból jöhet
        detailed_filter_keys = [
            "id", "price_min", "price_max", "main_category_slug", 
            "sub_category_slug", "product_type_slug", "is_gs_dependent", "is_sold"
        ]

        # 2. Kitöröljük az összes régi részletes szűrőt a `_current_filters`-ből
        for key in detailed_filter_keys:
            self._current_filters.pop(key, None)

        # 3. Hozzáadjuk az új szűrőfeltételeket
        self._current_filters.update(filters)
        
        # 4. Lefuttatjuk a szűrést és frissítjük a gombokat
        self.product_manager.apply_filters(self._current_filters)
        self._update_filter_button_states()

    @Slot()
    def clear_filters(self):
        logger.info("Controller: Szűrők és keresés törlése.")
        self._current_filters = {}
        self.product_manager.apply_filters(self._current_filters)
        self._update_filter_button_states()

    @Slot(str, bool, str)
    def _handle_product_deleted(self, product_id: str, success: bool, message: str):
        if self._is_batch_processing:
            return # Kötegelt feldolgozás alatt nem csinálunk semmit
        
        if success and self._product_list_view:
            self._product_list_view.remove_product(product_id, success, message)

    @Slot(list, bool, str)
    def _on_products_batch_processed(self, products: list, success: bool, message: str):
        logger.info("Controller: Kötegelt feldolgozás befejeződött. A teljes lista frissítése...")
        self._is_batch_processing = False # Kapcsoljuk ki a "batch mode"-ot
        
        # A productsLoaded jel kibocsátása a ProductManagerből egy teljes, szűrt listával
        # a legtisztább módja a lista frissítésének.
        self.product_manager.apply_filters(self._current_filters)

    @Slot(int, Qt.SortOrder)
    def _save_sort_order(self, column: int, order: Qt.SortOrder):
        """Elmenti a felhasználó által választott rendezési állapotot."""
        self._last_sort_column = column
        self._last_sort_order = order
        self.playwright_automator.settings_manager.set_setting("client_settings.list_view_sort_column", column)
        self.playwright_automator.settings_manager.set_setting("client_settings.list_view_sort_order", order.value) # Az enum értékét (0 vagy 1) mentjük
        logger.info(f"Rendezési sorrend elmentve: Oszlop={column}, Sorrend={order.name}")

    @Slot()
    def handle_search_request(self):
        """Megnyitja a szöveges kereső dialógusablakot."""
        if not self._search_dialog:
            main_window = QApplication.activeWindow()
            self._search_dialog = SearchDialog(parent=main_window)
            self._search_dialog.applySearch.connect(self.apply_filters)
            self._search_dialog.clearSearch.connect(self._handle_clear_search)
        
        self._search_dialog.set_current_search(self._current_filters)
        
        result = self._search_dialog.exec()
        
        if result == QDialog.Accepted:
            pass
        else:
            logger.info("Controller: Kereső dialógus elvetve, gombok állapotának újraszinkronizálása.")
            self._update_filter_button_states()

    @Slot()
    def _handle_clear_search(self):
        logger.info("Controller: Szöveges keresés törlése.")
        self._current_filters.pop("search_term", None)
        self._current_filters.pop("search_in_title", None)
        self._current_filters.pop("search_in_description", None)
        self.product_manager.apply_filters(self._current_filters)
        self._update_filter_button_states()

    @Slot()
    def handle_product_upload_request(self):
        product_id = self._product_list_view.get_selected_product_id()
        if not product_id:
            QMessageBox.warning(None, "Nincs termék", "Nincs kiválasztva termék a feltöltéshez.")
            return
            
        product = self.product_manager.get_product_by_id(product_id)
        if not product:
            QMessageBox.critical(None, "Hiba", f"A(z) '{product_id}' azonosítójú termék nem található a feltöltéshez.")
            return

        # --- ÚJ RÉSZ: Ellenőrizzük a 'mixed_' képek számát ---
        if product.num_mixed_images == 0:
            QMessageBox.critical(
                None,  # Szülő ablak
                "Feltöltés Megszakítva",  # Az ablak címe
                "Nem lehet feltölteni a terméket, mert nincs hozzá mixed_ tagú kép!",  # Az üzenet
                QMessageBox.StandardButton.Ok  # Csak egy "Oké" gomb
            )
            # A return miatt a függvény itt leáll, semmi más nem történik.
            return
        # --- MÓDOSÍTÁS VÉGE ---

        # --- ÚJ RÉSZ: Megerősítő dialógusablak megjelenítése ---
        reply = QMessageBox.question(
            None,  # Szülő ablak
            "Feltöltés megerősítése",  # Az ablak címe
            f"Biztosan fel szeretné tölteni a(z) '{product.title}' terméket a szerverre?",  # A kérdés
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,  # Gombok
            QMessageBox.StandardButton.No  # Alapértelmezett gomb
        )

        # Ha a felhasználó az "Igen"-re kattintott, folytatjuk a műveletet
        if reply == QMessageBox.StandardButton.Yes:
            self.updateStatusBar.emit(f"Feltöltés előkészítése: '{product.title}'...", logging.INFO, "processing")
            self.playwright_automator.loop_worker.run_coro_threadsafe(
                self._ensure_ftp_connection_and_execute(
                    action_coroutine=self.ftp_manager._upload_product_data_async(product),
                    product=product
                )
            )
        else:
            # Ha a felhasználó a "Nem"-re kattint, vagy bezárja az ablakot
            self.updateStatusBar.emit("Feltöltés megszakítva.", logging.INFO, None)

    @Slot(bool, str, str, bool)
    def _handle_ftp_operation_finished(self, success: bool, message: str, operation_id: str, is_error: bool):
        # 1. Hibaüzeneteket mindig azonnal megjelenítjük.
        if is_error:
            self.updateStatusBar.emit(message, logging.ERROR, "red")
        
        # 2. A sikeres FELTÖLTÉSI üzeneteket is megjelenítjük, mert azoknak nincs külön kezelője.
        elif success and not is_error and operation_id.startswith("upload_"):
            self.updateStatusBar.emit(message, logging.INFO, "green")
        
        # 3. A sikeres TÖRLÉSI üzenetekkel itt már nem foglalkozunk,
        #    mert azokat a saját, dedikált eseménykezelőik (pl. _run_sell_product_flow) kezelik.

        # 4. A háttérlogika futtatása (állapotfrissítések)
        if success and not is_error and operation_id.startswith("upload_"):
            product_id = operation_id.replace("upload_", "")
            product = self.product_manager.get_product_by_id(product_id)
            if product:
                product.needs_upload = False
                self.product_manager.add_or_update_product_sync(product)

    @Slot(str)
    def _handle_gs_report(self, report_html: str):
        self.text_editor_controller.show_editor(initial_content=report_html)

    @Slot(str)
    def _handle_jf_report(self, report_html: str):
        self.text_editor_controller.show_editor(initial_content=report_html)

    @Slot(bool, str, dict)
    def _handle_gs_form_filling_finished(self, success: bool, message: str, product_data: dict):
        logger.info(f"GS űrlapkitöltés befejeződött. Siker: {success}. Üzenet: {message}")
        if self._product_detail_widget:
            new_state = NewGsProductState.FORM_FILLED if success else NewGsProductState.IDLE
            self._product_detail_widget.set_gs_new_product_state(new_state, message)

    @Slot(Product)
    def _handle_gs_validation_request(self, product_to_validate: Product):
        self._pending_gs_validation_product = product_to_validate
        self.gs_automator.run_gs_new_product_validate_flow(
            original_product_id="NEW_GS_PRODUCT",
            local_product_title=product_to_validate.title,
            local_price_numeric=product_to_validate.price_numeric
        )

    @Slot(bool, str, dict, str)
    def _handle_gs_product_validation_finished(self, success: bool, message: str, extracted_on_site_data: dict, original_id: str):
        if original_id != "NEW_GS_PRODUCT":
            return

        if success and self._pending_gs_validation_product:
            # 1. Termék véglegesítése és mentése
            self.product_manager.finalize_gs_new_product(extracted_on_site_data, self._pending_gs_validation_product)
            
            # 2. Visszajelzés a felhasználónak
            self.updateStatusBar.emit("Új GS termék sikeresen érvényesítve és elmentve.", logging.INFO, "green")
            
            # 3. Böngésző minimalizálása
            self.playwright_automator.minimize_browser()

            if self._image_gallery_widget:
                # 4. Ideiglenes képek törlése
                self._image_gallery_widget.clear_temporary_images()
            
            # === A HIÁNYZÓ LÉPÉS HOZZÁADÁSA ===
            # 5. Explicit módon jelezzük az adatlapnak, hogy a GS munkafolyamat
            #    befejeződött és visszaállhat alaphelyzetbe.
            if self._product_detail_widget:
                self._product_detail_widget.set_gs_new_product_state(NewGsProductState.IDLE)
            # ==================================

        else: # Hiba esetén
            if self._product_detail_widget:
                self._product_detail_widget.set_gs_new_product_state(NewGsProductState.FORM_FILLED, "Validálás sikertelen, próbálja újra!")

        # A végén a függőben lévő termék törlése
        self._pending_gs_validation_product = None


    async def _ensure_ftp_connection_and_execute(
        self, 
        action_coroutine: Coroutine, 
        offline_fallback_action: Optional[Callable] = None, 
        product: Optional[Product] = None
    ):
        if not self.ftp_manager.is_ftp_connected():
            success = await self.ftp_manager.connect_async()
            if not success:
                reply = QMessageBox.question(
                    None,
                    "FTP Kapcsolódási Hiba",
                    "Nem sikerült csatlakozni az FTP szerverhez.\n\nSzeretné folytatni a műveletet kapcsolat nélkül? (A változások csak helyben lesznek elmentve, és később manuálisan kell szinkronizálni.)",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    if offline_fallback_action and product:
                        offline_fallback_action(product.id)
                    else:
                        self.updateStatusBar.emit("Offline művelet végrehajtva.", logging.INFO, "orange")
                else:
                    self.updateStatusBar.emit("Művelet megszakítva.", logging.INFO, None)
                return

        await action_coroutine

    def _handle_offline_sell(self, product_id: str):
        product = self.product_manager.get_product_by_id(product_id)
        if product:
            product.is_sold = True
            product.needs_upload = True
            self.product_manager.add_or_update_product_sync(product)
            self.updateStatusBar.emit(f"'{product.title}' offline eladva. Szinkronizálás szükséges.", logging.WARNING, "orange")
            self.product_manager.productDeleted.emit(product_id, True, "Termék offline eladva.")

    @Slot()
    def _handle_remove_from_markets_request(self):
        """Kezeli a 'Termék eltávolítása a piacterekről' gombnyomást."""
        product = self.product_manager.get_product_by_id(self._product_list_view.get_selected_product_id())
        if not product:
            return

        ### MÓDOSÍTÁS KEZDETE ###
        dialog = RemoveFromMarketsDialog(product, parent=None) # A product.title helyett a teljes objektumot adjuk át
        ### MÓDOSÍTÁS VÉGE ###
        
        if dialog.exec() == QDialog.Accepted:
            selected_markets = dialog.get_selected_markets()
            
            self.playwright_automator.loop_worker.run_coro_threadsafe(
                self._run_semi_automatic_removal_flow(product, selected_markets)
            )
        else:
            self.updateStatusBar.emit("Eltávolítási művelet megszakítva.", logging.INFO, None)

    async def _run_semi_automatic_removal_flow(self, product: Product, markets: List[str]):
        """
        Végigvezényli a félautomata eltávolítási folyamatot:
        1. Biztosítja a látható böngészőt.
        2. Újrahasznosítja vagy megnyitja a szükséges oldalakat.
        3. Futtatja a piactér-specifikus megkereső automatizálást.
        """
        try:
            browser_ready = await self.playwright_automator.ensure_browser_is_running_and_visible()
            if not browser_ready:
                raise RuntimeError("Nem sikerült a böngészőt előkészíteni.")

            await self.playwright_automator.browser_manager.close_all_pages_async()
            
            market_map = {
                "Galéria Savaria": {
                    "url": self.playwright_automator.settings_manager.get_setting("site_configs.galeria_savaria.products_url"),
                    "automator_slot": self.gs_automator.run_gs_semi_auto_locate_flow
                },
                "Jófogás": {
                    "url": self.playwright_automator.settings_manager.get_setting("site_configs.jofogas.products_url"),
                    "automator_slot": self.jofogas_automator.run_jf_semi_auto_locate_flow
                }
            }
            
            opened_pages: Dict[str, Page] = {}
            browser_context = self.playwright_automator.browser_manager._context

            for market_name in markets:
                config = market_map.get(market_name)
                if not config or not config["url"]:
                    self.updateStatusBar.emit(f"'{market_name}' URL nincs konfigurálva, kihagyva.", logging.WARNING, "red")
                    continue

                target_url = config["url"]
                page = None

                for p in browser_context.pages:
                    if p.url.startswith(target_url):
                        page = p
                        break
                
                if page is None:
                    page = await browser_context.new_page()
                    await page.goto(target_url)
                
                opened_pages[market_name] = page

            for market_name, page in opened_pages.items():
                automator_slot = market_map[market_name].get("automator_slot")
                if automator_slot:
                    await page.bring_to_front()
                    
                    automator_slot(page, product)
        except Exception as e:
            self.updateStatusBar.emit(f"Hiba az eltávolítási folyamat során: {e}", logging.ERROR, "red")


    @Slot(bool, str, str)
    def _handle_gs_product_semi_auto_locate_finished(self, success: bool, message: str, product_id: str):
        """
        Fogadja a GS félautomata megkeresés befejezéséről szóló jelzést.
        A GUI frissítéséről már az automator _log() metódusa gondoskodott,
        így itt már nem kell updateStatusBar-t hívni.
        """
        # Csak egy belső logbejegyzést készítünk a hibakereséshez.
        if success:
            logger.info(f"MainController: Visszajelzés érkezett a '{product_id}' sikeres GS megkereséséről.")
        else:
            logger.warning(f"MainController: Hiba visszajelzés érkezett a '{product_id}' GS megkereséséről.")

    @Slot()
    def _handle_refresh_jofogas_ad_request(self):
        """Kezeli a 'Jófogás hirdetés frissítése' gombnyomást."""
        product = self.product_manager.get_product_by_id(self._product_list_view.get_selected_product_id())
        if not product:
            return

        reply = QMessageBox.question(
            None, "Jófogás frissítés megerősítése",
            f"Biztosan frissíti a(z) '{product.title}' termék hirdetését a Jófogáson?\n\n(Ez a funkció még nincs implementálva.)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.updateStatusBar.emit(f"'{product.title}' Jófogás hirdetésének frissítése (szimuláció)...", logging.INFO, "processing")
            logger.info(f"Parancs: '{product.title}' (ID: {product.id}) Jófogás hirdetésének frissítése.")

    @Slot(Page, bool, str, str)
    def _handle_jf_product_semi_auto_locate_finished(self, page: Page, success: bool, message: str, product_id: str):
        """
        Fogadja a Jófogás félautomata megkeresés befejezéséről szóló jelzést.
        A jelzés most már a 'page' objektumot is tartalmazza.
        """
        if not success:
            logger.warning(f"MainController: Hiba a '{product_id}' Jófogás megkereséséről.")
            return

        logger.info(f"MainController: Visszajelzés érkezett a '{product_id}' sikeres Jófogás megkereséséről.")
        
        # Ellenőrizzük, hogy megkaptuk-e a 'page' objektumot.
        if not page:
            logger.error("Hiba: A termékkeresés sikeres volt, de a böngészőlap objektum (page) nem érkezett meg a jelzéssel.")
            return

        self.updateStatusBar.emit(f"Figyelő aktív: Várakozás a '{product_id}' manuális törlésére a böngészőben...", logging.INFO, "processing")

        if self._jofogas_deletion_task and not self._jofogas_deletion_task.done():
            self._jofogas_deletion_task.cancel()

        self._currently_watched_product_id = product_id
        # A figyelőt a jelzésben kapott 'page' objektummal indítjuk el
        self._jofogas_deletion_task = self.playwright_automator.loop_worker.run_coro_threadsafe(
            self._watch_for_jofogas_deletion_success(page, product_id)
        )

    @Slot(str)
    def _handle_new_browser_page(self, url: str):
        """Ez a slot most már csak az IGAZÁN ÚJ lapok megnyitását jelzi."""
        message = f"Észleltem egy új böngészőlap megnyitását! Cím: {url}"
        # logger.info(message)
        # self.updateStatusBar.emit(f"Új lap nyílt: {url}", logging.INFO, "blue")

    @Slot(str)
    def _handle_page_navigation(self, url: str):
        """
        Ez a slot hívódik meg MINDEN navigáció után egy meglévő lapon.
        Itt ellenőrizzük a GS validálási feltételt, és most már automatikusan
        elindítjuk az érvényesítést.
        """
        # logger.debug(f"Navigáció észlelve, új URL: {url}")
        
        if not self._product_detail_widget:
            return

        current_gs_state = self._product_detail_widget.get_gs_new_product_state()

        if current_gs_state == NewGsProductState.FORM_FILLED:
            gs_products_url = self.playwright_automator.settings_manager.get_setting("site_configs.galeria_savaria.products_url")

            if gs_products_url and url.strip('/') == gs_products_url.strip('/'):
                logger.info("Feltételek teljesültek az automatikus GS validáláshoz. Folyamat indítása...")
                
                try:
                    product_to_validate = self._product_detail_widget.get_product_data_for_validation()
                    if not product_to_validate:
                        return

                    self._pending_gs_validation_product = product_to_validate

                    self._product_detail_widget.set_gs_new_product_state(NewGsProductState.VALIDATING_IN_PROGRESS, "Automatikus érvényesítés...")
                  
                    self.gs_automator.run_gs_new_product_validate_flow(
                        original_product_id="NEW_GS_PRODUCT",
                        local_product_title=product_to_validate.title,
                        local_price_numeric=product_to_validate.price_numeric
                    )
                except (ValueError, RuntimeError) as e:
                    QMessageBox.critical(self, "Hiba", f"Nem sikerült elindítani az automatikus érvényesítést: {e}")
                    self._product_detail_widget.set_gs_new_product_state(NewGsProductState.FORM_FILLED, "Hiba az adatokban.")

        # === A JÓFOGÁS SIKER URL ELLENŐRZÉSE - DINAMIKUS MÓDSZERREL ===
        # 1. Beolvassuk a teljes URL-t a beállításokból
        full_confirm_url = self.playwright_automator.settings_manager.get_setting("site_configs.jofogas.upload_success_url")

        # 2. Ellenőrizzük, hogy van-e beállított URL
        if full_confirm_url:
            try:
                # 3. Levágjuk a változó részt (az utolsó '/' utáni karaktereket)
                # Az rfind('/') megkeresi az utolsó perjelet, és +1-gyel adjuk hozzá, hogy a perjel is benne maradjon.
                last_slash_index = full_confirm_url.rfind('/')
                if last_slash_index > 8: # Biztosítjuk, hogy a "https://" utáni perjelet találjuk meg
                    base_confirm_url = full_confirm_url[:last_slash_index + 1]

                    # 4. Az így kapott "alap" URL-lel hasonlítjuk össze a böngésző aktuális címét
                    if url.startswith(base_confirm_url):
                        logger.info(f"Sikeres Jófogás termékfeladás észlelve (URL: {url}). A pozíciók frissítése elindítva.")
                        
                        # A további logika változatlan
                        self.product_manager.increment_all_jofogas_positions_sync()
                        self.updateStatusBar.emit("Jófogás feltöltés sikeres, a pozíciók frissítve.", logging.INFO, "green")
                        self.playwright_automator.minimize_browser()
            except Exception as e:
                # Hibakezelés, ha valamiért a string-művelet hibára futna
                logger.error(f"Hiba a Jófogás siker URL feldolgozása közben: {e}")
            
    @Slot(str)
    def _handle_manual_jf_deletion_confirmation(self, product_id: str):
        """A felhasználó manuálisan rákattintott a megerősítő gombra."""
        self.updateStatusBar.emit("Manuális megerősítés fogadva. Folyamat leállítása és frissítés...", logging.INFO, "blue")
        
        # Leállítjuk a háttérfigyelőt, ha még fut
        if self._jofogas_deletion_task and not self._jofogas_deletion_task.done():
            self._jofogas_deletion_task.cancel()
        
        # Lefuttatjuk a sorszámcsökkentést
        self.product_manager.decrement_jofogas_positions_after_sync(product_id)
        
        # Visszaállítjuk a UI-t
        if self._product_detail_widget:
            self._product_detail_widget.set_awaiting_jf_deletion_mode(False)
            
        # Töröljük a hivatkozásokat
        self._jofogas_deletion_task = None
        self._currently_watched_product_id = None

    # === A FIGYELŐ METÓDUS MÓDOSÍTÁSA ===
    async def _watch_for_jofogas_deletion_success(self, page: Page, product_id: str):
        success_dialog_selector = 'div[data-testid="success-alert-dialog"]'
        timeout_ms = 300000 
        logger.info(f"Figyelő aktív: Várakozás a '{product_id}' manuális törlésére a böngészőben...")

        try:
            await page.wait_for_selector(success_dialog_selector, state="visible", timeout=timeout_ms)
            
            if self._currently_watched_product_id != product_id: return
        
            self.product_manager.decrement_jofogas_positions_after_sync(product_id)
        except asyncio.CancelledError:
            logger.info(f"A(z) '{product_id}' termék törlésfigyelője szándékosan leállítva.")
            pass
        except TimeoutError:
             self.updateStatusBar.emit("A törlésfigyelő időtúllépés miatt leállt.", logging.WARNING, "red")
        except Exception as e:
            self.updateStatusBar.emit(f"Hiba a törlésfigyelés közben: {e}", logging.ERROR, "red")
        finally:
            if self._currently_watched_product_id == product_id:
                self._jofogas_deletion_task = None
                self._currently_watched_product_id = None

    async def _run_sell_product_flow(self, product: Product):
        """
        Orchesztrálja a teljes eladási folyamatot a háttérszálon.
        Először megpróbál csatlakozni, majd elindítja a törlést.
        Visszaadja a törlési művelet végeredményét, vagy egy speciális
        hibát, ha a csatlakozás sem sikerült.
        """
        try:
            if not self.ftp_manager.is_ftp_connected():
                is_connected_now = await self.ftp_manager.connect_async()
                if not is_connected_now:
                    return (False, "Connection Failed", f"delete_{product.id}", True)

            # A metódus hívása JAVÍTVA (nincs aláhúzás)
            result = await self.ftp_manager.delete_product_from_ftp_async(product)
            return result

        except Exception as e:
            return (False, f"Hiba az eladási folyamat során: {e}", f"delete_{product.id}", True)

        def on_ftp_sold_finished(fut: asyncio.Future):
            try:
                success, message, operation_id, is_error = fut.result()

                if operation_id != f"delete_{product.id}":
                    return
                
                if success and not is_error:
                    self.product_manager.mark_product_as_sold_sync(product.id)
                    self.updateStatusBar.emit(f"'{product.title}' eladva és a szerverről eltávolítva.", logging.INFO, "green")
                else:
                    self.updateStatusBar.emit(f"Hiba a(z) '{product.title}' szerverről való törlésekor. A helyi állapot nem változott.", logging.ERROR, "red")
            except Exception as e:
                self.updateStatusBar.emit(f"Kritikus hiba az eladási folyamat során: {e}", logging.CRITICAL, "red")

        future.add_done_callback(on_ftp_sold_finished)            

    @Slot()
    def handle_database_check_request(self):
        """
        Megnyitja az adatbázis-ellenőrző dialógusablakot és a választás alapján
        elindítja a megfelelő (szinkron vagy aszinkron) ellenőrzést.
        """
        if not self._database_check_dialog:
            main_window = QApplication.activeWindow()
            self._database_check_dialog = DatabaseCheckDialog(parent=main_window)
            # A checkRequested jelzést most egy új, központi kezelőhöz kötjük
            self._database_check_dialog.checkRequested.connect(self._process_database_check_request)
        
        self.updateStatusBar.emit("Adatbázis karbantartó megnyitva.", logging.INFO, None)
        self._database_check_dialog.open()


    @Slot(str)
    def _handle_report_generated(self, report_html: str):
        """
        Fogadja a ProductManager által generált riportot és megnyitja a szövegszerkesztőben,
        időzítve a fókuszproblémák elkerülése érdekében.
        """
        self.updateStatusBar.emit("Jelentés elkészült, megnyitás a szerkesztőben...", logging.INFO, "blue")

        # A QTimer.singleShot biztosítja, hogy a szövegszerkesztő dialógus
        # csak azután jelenjen meg, hogy a jelenlegi esemény (pl. a gombnyomás) feldolgozása befejeződött,
        # elkerülve ezzel a fókuszvesztési problémákat.
        QTimer.singleShot(0, lambda: self.text_editor_controller.show_editor(initial_content=report_html))

    @Slot(str)
    def _process_database_check_request(self, check_type: str):
        """
        Feldolgozza a DatabaseCheckDialog-ból érkező kéréseket.
        """
        # A dialógust mindenképp bezárjuk a kérés után
        if self._database_check_dialog:
            self._database_check_dialog.close()

        if check_type == "server_client_sync_check":
            # Ez egy ASZINKRON kérés, a Controller indítja a háttérszálon.
            self.updateStatusBar.emit("Szerver-kliens szinkronizáció ellenőrzése...", logging.INFO, "processing")
            self.playwright_automator.loop_worker.run_coro_threadsafe(
                self._run_server_client_sync_check_async()
            )
        elif check_type == "server_duplicate_id_check":
            self.updateStatusBar.emit("Szerveroldali duplikátumok keresése...", logging.INFO, "processing")
            self.playwright_automator.loop_worker.run_coro_threadsafe(
                self._run_server_duplicate_check_async()
            )
        elif check_type == "upload_database_to_server":
            self.handle_upload_database_request()
        else:
            # A többi kérés SZINKRON, ezeket továbbítjuk a ProductManagernek.
            self.product_manager.run_database_integrity_check_sync(check_type)


    # --- MÓDOSÍTÁS: Az aszinkron logika áthelyezése ide ---
    async def _run_server_client_sync_check_async(self):
        """
        Elvégzi a kliens és szerver közötti összehasonlítást és legenerálja a riportot.
        Ezt a metódust a MainController futtatja a háttérszálon.
        """
        try:
            local_ids = self.product_manager.get_all_product_ids()
            remote_ids = await self.ftp_manager._get_all_remote_product_ids_async()
            
            if remote_ids is None:
                report_html = self.product_manager.generate_sync_report_html(set(), set(), error=True)
                self.product_manager.reportGenerated.emit(report_html)
                return

            local_only = local_ids - remote_ids
            remote_only = remote_ids - local_ids

            report_html = self.product_manager.generate_sync_report_html(local_only, remote_only)
            self.product_manager.reportGenerated.emit(report_html)

        except Exception as e:
            logger.critical(f"Váratlan hiba a szerver-kliens szinkronizáció ellenőrzésekor: {e}", exc_info=True)
            error_report = f"<h1>Hiba</h1><p>Váratlan hiba történt az ellenőrzés során: {e}</p>"
            # A riportot továbbra is a ProductManageren keresztül bocsátjuk ki a konzisztencia érdekében
            self.product_manager.reportGenerated.emit(error_report)

    @Slot()
    def handle_description_format_request(self):
        """Megjeleníti a leírásformázó dialógusablakot és kezeli az eredményt."""
        if not self._product_detail_widget or self._product_detail_widget.description_edit.isReadOnly():
            self.updateStatusBar.emit("A formázás csak szerkesztési módban érhető el.", logging.WARNING, "orange")
            return

        if not self._description_format_dialog:
            main_window = QApplication.activeWindow()
            self._description_format_dialog = DescriptionFormatDialog(parent=main_window)
            self._description_format_dialog.undoRequested.connect(self._handle_description_undo_request)
        
        can_undo = self._product_detail_widget._undo_buffer is not None
        self._description_format_dialog.undo_button.setEnabled(can_undo)

        if self._description_format_dialog.exec() == QDialog.Accepted:
            ### JAVÍTÁS KEZDETE ###
            # A dialógus már egy kész 'options' szótárat ad vissza.
            # Nem kell újra becsomagolni, csak közvetlenül továbbadjuk.
            options = self._description_format_dialog.get_selected_option()
            if options:
                self._product_detail_widget.format_description(options)
                self.updateStatusBar.emit("Leírás formázva.", logging.INFO, "green")
            ### JAVÍTÁS VÉGE ###
        else:
            pass

    # --- ÚJ SLOT A FÁJL VÉGÉRE ---
    @Slot()
    def _handle_description_undo_request(self):
        """Kezeli a visszavonási kérést."""
        if self._product_detail_widget:
            self._product_detail_widget.undo_last_format()
            self.updateStatusBar.emit("Formázás visszavonva.", logging.INFO, "blue")
        
        # Bezárja a dialógust a művelet után
        if self._description_format_dialog:
            self._description_format_dialog.close()

    @Slot(str)
    def _handle_detail_toolbar_click(self, button_id: str):
        if button_id == "email_btn":
            self.handle_send_email_request()

    @Slot()
    def handle_send_email_request(self):
        """Kezeli a levélküldési kérést: megnyitja a dialógust és továbbítja az adatokat."""
        if not self._product_detail_widget or not self._product_detail_widget._current_product:
            self.updateStatusBar.emit("Nincs kiválasztott termék az email küldéséhez.", logging.WARNING, "orange")
            return
            
        product = self._product_detail_widget._current_product
        default_recipient = self.email_manager.settings_manager.get_setting("email_settings.recipient_email", "")

        main_window = QApplication.activeWindow()
        self._email_dialog = EmailDialog(product.title, default_recipient, parent=main_window)
        
        if self._email_dialog.exec() == QDialog.Accepted:
            recipient = self._email_dialog.get_recipient()
            if not recipient:
                self.updateStatusBar.emit("A küldés megszakítva: a címzett nem lehet üres.", logging.WARNING, "orange")
                return

            attachment_paths = self.product_manager.get_mixed_image_paths(product.id)
            
            if not attachment_paths:
                self.updateStatusBar.emit(f"Figyelem: '{product.title}' email elküldve képek nélkül (nincs 'mixed_' kép).", logging.WARNING, "orange")
            else:
                 self.updateStatusBar.emit(f"Email küldésének előkészítése: '{product.title}' ({len(attachment_paths)} kép)...", logging.INFO, "processing")

            self.email_manager.send_product_email_with_attachments_slot(product, recipient, attachment_paths)
        else:
            self.updateStatusBar.emit("Email küldése megszakítva.", logging.INFO, None)

    @Slot(bool, str)
    def _handle_email_sent(self, success: bool, message: str):
        """Kezeli az EmailManager visszajelzését a küldés eredményéről."""
        if success:
            self.updateStatusBar.emit(message, logging.INFO, "green")
        else:
            self.updateStatusBar.emit(message, logging.ERROR, "red")

    @Slot()
    def handle_upload_database_request(self):
        """Megnyitja a teljes adatbázis feltöltését vezérlő dialógust."""
        if not self._upload_database_dialog:
            main_window = QApplication.activeWindow()
            self._upload_database_dialog = UploadDatabaseDialog(parent=main_window)

        if self._upload_database_dialog.exec() == QDialog.Accepted:
            options = self._upload_database_dialog.get_upload_options()
            
            if not options["upload_json"] and not options["upload_images"]:
                self.updateStatusBar.emit("Nincs kiválasztva feltöltési opció, a művelet megszakítva.", logging.WARNING, "orange")
                return

            reply = QMessageBox.question(
                None, "Feltöltés megerősítése",
                "Biztosan felülírja a teljes adatbázist a szerveren a helyi adatokkal?\nEz a művelet nem vonható vissza!",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                self.updateStatusBar.emit("Teljes adatbázis feltöltése a szerverre...", logging.INFO, "processing")
                self.ftp_manager.upload_full_database_slot(options["upload_json"], options["upload_images"])
            else:
                self.updateStatusBar.emit("Adatbázis feltöltése megszakítva.", logging.INFO, None)

    @Slot(str)
    def handle_product_export_request(self, product_id: str):
        """Kezeli a termékmappa exportálási kérését."""
        product = self.product_manager.get_product_by_id(product_id)
        if not product:
            self.updateStatusBar.emit(f"Exportálási hiba: A(z) '{product_id}' ID-jű termék nem található.", logging.ERROR, "red")
            return

        download_folder = self.playwright_automator.settings_manager.get_setting("client_settings.download_folder")
        if not download_folder or not os.path.isdir(download_folder):
            self.updateStatusBar.emit("Exportálási hiba: Érvénytelen letöltési mappa van beállítva.", logging.ERROR, "red")
            QMessageBox.critical(None, "Hiba", "A beállításokban megadott letöltési mappa nem létezik vagy érvénytelen.")
            return

        reply = QMessageBox.question(
            None, "Exportálás megerősítése",
            f"Biztosan exportálja a(z) '{product.title}' termék teljes mappáját a következő helyre?\n\n{download_folder}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.updateStatusBar.emit(f"'{product.title}' exportálása...", logging.INFO, "processing")
            success, message = self.product_manager.export_product_folder_sync(product_id)
            if success:
                self.updateStatusBar.emit(message, logging.INFO, "green")
            else:
                self.updateStatusBar.emit(message, logging.ERROR, "red")
        else:
            self.updateStatusBar.emit("Exportálás megszakítva.", logging.INFO, None)

    async def _run_server_duplicate_check_async(self):
        """
        Elvégzi a szerveroldali duplikátum-ellenőrzést és legeneráltatja a riportot.
        """
        try:
            # 1. Lekérjük a duplikátumokat az FtpManager-től
            duplicates = await self.ftp_manager.find_duplicate_products_on_server_async()
            
            # 2. Átadjuk az eredményt a ProductManager-nek riport generálásra
            # A 'duplicates' lehet None is, ha hiba történt, a riportgeneráló kezeli ezt.
            report_html = self.product_manager.generate_server_duplicate_report_html(duplicates)
            
            # 3. Kibocsátjuk a jelet, hogy a riport megjelenjen a szövegszerkesztőben
            self.product_manager.reportGenerated.emit(report_html)

        except Exception as e:
            logger.critical(f"Váratlan hiba a szerveroldali duplikátum-ellenőrzés során: {e}", exc_info=True)
            error_report = f"<h1>Hiba</h1><p>Váratlan hiba történt az ellenőrzés során: {e}</p>"
            self.product_manager.reportGenerated.emit(error_report)

    @Slot()
    def handle_marking_request(self):
        """Megnyitja a jelölő dialógusablakot."""
        if not self._mark_dialog:
            main_window = QApplication.activeWindow()
            self._mark_dialog = MarkDialog(parent=main_window)
            self._mark_dialog.applyMarking.connect(self._apply_marking)
        
        self._mark_dialog.set_current_marking(self._current_marking)
        self._mark_dialog.exec()

    @Slot(str)
    def _apply_marking(self, marking: str):
        """Alkalmazza a kiválasztott jelölést a terméklistára."""
        if self._current_marking == marking:
            return

        self._current_marking = marking
        is_active = marking != "none"
        self.updateToolbarButtonState.emit("mark_btn", is_active, True)
        
        if self._product_list_view:
            self._product_list_view.reapply_styles(self._current_marking)
            
        status_map = {
            "none": "Jelölés törölve.",
            "posted_fb": "Jelölés: Facebook posztolt termékek.",
            "ad_created_fb": "Jelölés: Facebook hirdetett termékek.",
            # --- ÚJ BEJEGYZÉS ---
            "inactive_jf": "Jelölés: Jófogáson inaktív termékek."
            # --------------------
        }
        self.updateStatusBar.emit(status_map.get(marking, ""), logging.INFO, "blue")

    @Slot(bool, str, str)
    def _handle_fb_post_finished(self, success: bool, message: str, product_id: str):
        """
        Ez a metódus hívódik meg, amikor a FacebookAutomator végzett (akár siker, akár hiba).
        """
        if success:
            self.updateStatusBar.emit(message, logging.INFO, "green")
            
            # 1. Megkeressük a terméket az ID alapján
            product = self.product_manager.get_product_by_id(product_id)
            
            if product:
                # 2. Mivel az Automator már átállította a memóriában az is_posted flaget,
                #    most elmentjük a JSON fájlba is a változást.
                self.product_manager.add_or_update_product_sync(product, run_filter_and_emit=False)
                
                # 3. Ha éppen ezt a terméket nézzük a felületen, frissítjük a checkboxokat
                if self._product_detail_widget._current_product and self._product_detail_widget._current_product.id == product_id:
                    # A set_product újrahívása frissíti a UI elemeket (checkboxokat)
                    self._product_detail_widget.set_product(product)
                    
        else:
            self.updateStatusBar.emit(message, logging.ERROR, "red")
            QMessageBox.warning(None, "Facebook Hiba", message)

    @Slot(list)
    def _handle_product_loading_errors(self, errors: list):
        """
        Felugró ablakot jelenít meg a termékbetöltés során talált hibák listájával.
        Egy időzítőt használ, hogy a dialógus csak a főablak teljes megjelenése után jelenjen meg.
        """
        def show_error_dialog():
            error_details = "\n\n- ".join(errors)
            QMessageBox.warning(
                None,
                "Hiba a termékek betöltésekor",
                f"Az alábbi hibák történtek a termékadatbázis betöltése közben:\n\n- {error_details}"
            )
        
        # A dialógust egy rövid késleltetés után jelenítjük meg, hogy a főablak biztosan látható legyen.
        QTimer.singleShot(500, show_error_dialog)