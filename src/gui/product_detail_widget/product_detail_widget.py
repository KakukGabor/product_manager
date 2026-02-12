import logging
import os
from typing import Optional, Dict, Any, List
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QLineEdit, QTextEdit, QPushButton, QSizePolicy, QScrollArea,
    QMessageBox, QCheckBox, QApplication, QDialog
)
from PySide6.QtGui import QColor, QPalette, QDoubleValidator
from PySide6.QtCore import Qt, Signal, Slot, QLocale

from models.product_model import Product, MainCategory, _sanitize_for_slug
from managers.product_category_manager import ProductCategoryManager
from managers.product_manager import ProductManager
from managers.ftp_manager import FtpManager
from gui.image_gallery_widget.image_gallery_widget import ImageGalleryWidget
from utils.formatters import format_numeric_input
from .pdw_states import NewGsProductState
from .confirm_sold_dialog import ConfirmSoldDialog
from .pdw_ui import ProductDetailUi
from .pdw_states import NewGsProductState

logger = logging.getLogger(__name__)

class ProductDetailWidget(QWidget):
    productUpdated = Signal(Product, bool, str)
    categoryChanged = Signal(str, MainCategory, str, str)
    newProductModeCancelled = Signal()
    formModeChanged = Signal(str)
    initialProductLoadedComplete = Signal()
    gsNewProductFillRequested = Signal(dict)
    jfNewProductFillRequested = Signal(dict)
    gsNewProductValidateRequested = Signal(Product)
    newProductModeEntered = Signal()
    productMarkedAsSold = Signal(str, bool)
    productUploadRequested = Signal()
    productReactivated = Signal(str)
    productPermanentlyDeleted = Signal(str)
    removeFromMarketsRequested = Signal()
    refreshJofogasAdRequested = Signal()
    descriptionFormatRequested = Signal()
    productExportRequested = Signal(str)
    fbPostRequested = Signal(object)
   
    def __init__(self, product_manager: ProductManager, category_manager: ProductCategoryManager, ftp_manager: FtpManager, image_gallery_widget: ImageGalleryWidget, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.product_manager = product_manager
        self.category_manager = category_manager
        self.ftp_manager = ftp_manager
        self._image_gallery_widget: Optional[ImageGalleryWidget] = image_gallery_widget
        self._current_product: Optional[Product] = None
        self._is_editing_existing = False
        self._is_new_product_mode = False
        self._gs_new_product_state: NewGsProductState = NewGsProductState.IDLE
        self._undo_buffer: Optional[str] = None
        self._is_fb_mode = False
        self._fb_data_has_changed = False

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setAutoFillBackground(True)
        self.setObjectName("productDetailWidget")

        self._log(logging.DEBUG, "ProductDetailWidget inicializálva.")
        self.ui = ProductDetailUi()
        self.ui.setup_ui(self)

        self._connect_signals()
        self._clear_form()

    def _log(self, level: int, message: str, *args, **kwargs):
        logger.log(level, f"[ProductDetailWidget] {message}", *args, **kwargs)

    def _connect_signals(self):
        """Összeköti az UI elemek szignáljait a widget slotjaival."""
        self.is_gs_dependent_checkbox.stateChanged.connect(self._on_gs_dependent_checkbox_state_changed)
        self.title_edit.returnPressed.connect(self._on_title_edit_return_pressed)
        self.price_numeric_edit.lineEdit().textChanged.connect(self._format_price_input)
        self.edit_button.clicked.connect(lambda: self._set_edit_mode(True))
        self.save_button.clicked.connect(self._save_changes)
        self.gs_fill_validate_button.clicked.connect(self._handle_gs_fill_validate_click)
        self.cancel_button.clicked.connect(self._cancel_changes)
        self.detailToolbar.buttonClicked.connect(self._handle_detail_toolbar_button_click)
        self.reactivate_button.clicked.connect(self._handle_reactivate_click)
        self.delete_permanently_button.clicked.connect(self._handle_delete_permanently_click)

        # --- FŐ NÉZET VÁLTOZÁSFIGYELÉSE ---
        self.title_edit.textChanged.connect(self._on_form_data_changed)
        self.description_edit.textChanged.connect(self._on_form_data_changed)
        self.price_numeric_edit.valueChanged.connect(self._on_form_data_changed)
        self.category_selector.categoryChanged.connect(self._on_form_data_changed)
        
        # --- FB NÉZET VÁLTOZÁSFIGYELÉSE (a slot neve frissítve) ---
        self.fb_mode_toggle_button.itemClicked.connect(self._toggle_fb_mode)
        self.fb_post_text_edit.textChanged.connect(self._on_form_data_changed)
        self.fb_ad_text_edit.textChanged.connect(self._on_form_data_changed)
        self.fb_hashtags_edit.textChanged.connect(self._on_form_data_changed)
        self.fb_post_url_edit.textChanged.connect(self._on_form_data_changed)
        self.fb_is_posted_checkbox.stateChanged.connect(self._on_form_data_changed)
        self.fb_is_ad_created_checkbox.stateChanged.connect(self._on_form_data_changed)
        self.fb_post_button.clicked.connect(self._handle_fb_post_click)
        self.fb_ad_create_button.clicked.connect(self._handle_fb_ad_create_click)

    def _get_validated_data_from_form(self) -> dict:
        """
        Kiolvassa az adatokat az űrlap mezőiből, validálja őket, és egy szótárban
        adja vissza. Hiba esetén ValueError kivételt dob.
        """
        # Adatok kiolvasása
        product_title = self.title_edit.text().strip()
        product_description = self.description_edit.toPlainText().strip()
        
        price_text_cleaned = self.price_numeric_edit.text().replace(QLocale(QLocale.Hungarian).groupSeparator(), '').replace(QLocale(QLocale.Hungarian).decimalPoint(), '.')
        try:
            product_price_numeric = float(price_text_cleaned) if price_text_cleaned else 0.0
        except ValueError:
            raise ValueError("Érvénytelen numerikus ár formátum.")

        ui_selected_main_cat_enum, ui_selected_sub_cat_slug, ui_selected_product_type_slug = self.category_selector.get_category()
        ui_selected_sub_cat_name = self.category_selector.sub_category_combo.currentText()
        ui_selected_product_type_name = self.category_selector.product_type_combo.currentText()

        # Validáció
        if not product_title:
            raise ValueError("A termék címe nem lehet üres.")
        if product_price_numeric <= 0:
            raise ValueError("A numerikus árnak pozitív számnak kell lennie.")
        if len(product_description) < 50:
            raise ValueError("A termék leírásának legalább 50 karakter hosszúnak kell lennie.")
        if ui_selected_main_cat_enum == MainCategory.UNCATEGORIZED:
            raise ValueError("Kérjük, válasszon fő kategóriát a termékhez.")
        if self.category_manager.get_sub_categories_for_main(ui_selected_main_cat_enum) and ui_selected_sub_cat_slug == _sanitize_for_slug("Nincs alkategória"):
            raise ValueError("Kérjük, válasszon alkategóriát a termékhez.")
        if self.category_manager.get_product_types_for_sub(ui_selected_main_cat_enum, ui_selected_sub_cat_name) and ui_selected_product_type_slug == _sanitize_for_slug("Nincs terméktípus"):
            raise ValueError("Kérjük, válasszon terméktípust a termékhez.")
        
        needs_review = (ui_selected_main_cat_enum == MainCategory.UNCATEGORIZED or
                        (self.category_manager.get_sub_categories_for_main(ui_selected_main_cat_enum) and ui_selected_sub_cat_slug == _sanitize_for_slug("Nincs alkategória")) or
                        (self.category_manager.get_product_types_for_sub(ui_selected_main_cat_enum, ui_selected_sub_cat_name) and ui_selected_product_type_slug == _sanitize_for_slug("Nincs terméktípus")))

        return {
            "title": product_title, "description": product_description, "price_numeric": product_price_numeric,
            "main_cat_enum": ui_selected_main_cat_enum, "sub_cat_slug": ui_selected_sub_cat_slug,
            "product_type_slug": ui_selected_product_type_slug, "sub_cat_name": ui_selected_sub_cat_name,
            "product_type_name": ui_selected_product_type_name, "needs_review": needs_review
        }

    def get_gs_new_product_state(self) -> NewGsProductState:
        """Visszaadja a Galéria Savaria új termék munkafolyamat aktuális állapotát."""
        return self._gs_new_product_state

    def double_validator(self):
        validator = QDoubleValidator(0.0, 999999999.0, 2)
        validator.setLocale(QLocale(QLocale.Hungarian))
        return validator

    def is_form_active_for_editing_or_new(self) -> bool:
        return self._is_editing_existing or self._is_new_product_mode

    def _update_form_visual_state(self):
        form_mode_str = "none"
        if self._is_new_product_mode:
            form_mode_str = "new_product"
        elif self._is_editing_existing:
            form_mode_str = "editing_existing"

        # 1. Beállítjuk a dinamikus property-t a QSS számára
        self.setProperty("formMode", form_mode_str)
        if hasattr(self, "scroll_content_widget"):
            self.scroll_content_widget.setProperty("formMode", form_mode_str)

        # 2. Rákényszerítjük a stíluslap újraértékelését és alkalmazását
        # Ez a "hivatalos" módja a stílusok frissítésének property-változás után.
        style = self.style()
        style.unpolish(self)
        style.polish(self)
        if hasattr(self, "scroll_content_widget"):
            style.unpolish(self.scroll_content_widget)
            style.polish(self.scroll_content_widget)

        # 3. Biztosítjuk, hogy a widget újrafesse magát a frissített stílussal
        self.update()
        if hasattr(self, "scroll_content_widget"):
            self.scroll_content_widget.update()
        
        self.formModeChanged.emit(form_mode_str)
        self._log(logging.DEBUG, f"Form visual state updated to: {form_mode_str}")

    def _set_edit_mode(self, editing: bool):
        if self._is_new_product_mode and editing:
            self._log(logging.WARNING, "Érvénytelen 'Szerkesztés' kérés új termék módban.")
            return
        
        self._is_editing_existing = editing
        self._update_form_visual_state()

        # Módváltó gomb letiltása/engedélyezése
        self.fb_mode_toggle_button.setEnabled(not editing)

        # Fő nézet mezői
        self.title_edit.setReadOnly(not editing)
        self.description_edit.setReadOnly(not editing)
        self.price_numeric_edit.setReadOnly(not editing)
        self.category_selector.set_enabled(editing)

        # Facebook nézet mezői
        self.fb_post_text_edit.setReadOnly(not editing)
        self.fb_ad_text_edit.setReadOnly(not editing)
        self.fb_hashtags_edit.setReadOnly(not editing)
        self.fb_post_url_edit.setReadOnly(not editing)
        self.fb_is_posted_checkbox.setEnabled(editing)
        self.fb_is_ad_created_checkbox.setEnabled(editing)

        self._update_action_buttons_visibility()

        # A Mentés gombot letiltjuk a szerkesztés kezdetén
        if editing:
            self.save_button.setEnabled(False)

        # --- ÚJ RÉSZ: FB műveleti gombok tiltása szerkesztés alatt ---
        # Csak akkor engedélyezzük őket, ha NEM szerkesztünk (tehát Olvasó módban vagyunk)
        if hasattr(self, 'fb_post_button'):
            self.fb_post_button.setEnabled(not editing)
        
        if hasattr(self, 'fb_ad_create_button'):
            self.fb_ad_create_button.setEnabled(not editing)

    @Slot(bool)
    def _set_new_product_mode(self, is_new: bool):
        self._is_new_product_mode = is_new
        self._is_editing_existing = False
        self._update_form_visual_state()

        self.fb_mode_toggle_button.setVisible(not is_new)
        self.is_gs_dependent_checkbox.setVisible(is_new)
        self.is_gs_dependent_checkbox.setEnabled(is_new)

        self.product_id_label.setText("ÚJ" if is_new else (self._current_product.id if self._current_product else "N/A"))
        self.product_id_label.setStyleSheet("font-weight: bold; color: #555;" + ("background-color: transparent;" if is_new else "background-color: #f0f0f0;"))

        self.title_edit.setReadOnly(not is_new)
        self.description_edit.setReadOnly(not is_new)
        self.price_numeric_edit.setReadOnly(not is_new)
        self.category_selector.set_enabled(is_new)

        if is_new:
            self._clear_form_for_new_product()
            self.newProductModeEntered.emit()
        else:
            self._set_edit_mode(False)
            self._gs_new_product_state = NewGsProductState.IDLE

        self._update_action_buttons_visibility()

    ### --- MÓDOSÍTÁS KEZDETE: Gomb-kezelés szétbontása --- ###

    def _update_action_buttons_visibility(self):
        """Fő diszpécser metódus, ami meghívja a specializált gomb-frissítő logikákat."""
        is_product_selected = (self._current_product is not None and self._current_product.id != ImageGalleryWidget.TEMP_PRODUCT_ID)
        is_editing_or_new = self._is_new_product_mode or self._is_editing_existing
    
        self._update_main_action_buttons(is_editing_or_new, is_product_selected)
        self._update_gs_workflow_button()
        self._update_detail_toolbar_buttons(is_editing_or_new, is_product_selected)

        self.formModeChanged.emit(self.property('formMode'))
        self._log(logging.DEBUG, f"Action buttons visibility updated. Form mode: {self.property('formMode')}")

    def _update_main_action_buttons(self, is_editing_or_new: bool, is_product_selected: bool):
        """Frissíti a fő akció gombok (Szerkesztés, Mentés, Mégse) láthatóságát."""
        is_sold = self._current_product.is_sold if self._current_product else False

        if is_sold:
            # Ha a termék el van adva, semmilyen szerkesztő gomb nem látszik
            self.edit_button.setVisible(False)
            self.save_button.setVisible(False)
            self.cancel_button.setVisible(False)
        elif self._is_fb_mode:
            # --- ÚJ LOGIKA: Facebook nézetben vagyunk ---
            # A "Szerkesztés" gomb látszik, ha NEM szerkesztünk.
            self.edit_button.setVisible(not is_editing_or_new and is_product_selected)
            # A "Mentés" és "Mégse" gombok látszanak, HA szerkesztünk.
            self.save_button.setVisible(is_editing_or_new)
            self.cancel_button.setVisible(is_editing_or_new)
        else:
            # --- RÉGI LOGIKA: Fő nézetben vagyunk ---
            self.edit_button.setVisible(not is_editing_or_new and is_product_selected)
            self.cancel_button.setVisible(is_editing_or_new)
            
            # A "Mentés" gomb a fő nézetben csak akkor látszik, ha nem GS-függő új termékről van szó
            is_gs_new_mode = self._is_new_product_mode and self.is_gs_dependent_checkbox.isChecked()
            self.save_button.setVisible(is_editing_or_new and not is_gs_new_mode)

        # Az eladott termékek gombjainak logikája változatlan
        self.reactivate_button.setVisible(is_product_selected and is_sold)
        self.delete_permanently_button.setVisible(is_product_selected and is_sold)

    def _update_gs_workflow_button(self):
        """Frissíti a Galéria Savaria munkafolyamat gombjának állapotát."""
        is_gs_new_mode = self._is_new_product_mode and self.is_gs_dependent_checkbox.isChecked()
        self.gs_fill_validate_button.setVisible(is_gs_new_mode)

        if is_gs_new_mode:
            # === MÓDOSÍTÁS KEZDETE ===
            # A szótár kibővítve egy negyedik elemmel a szövegszín számára (pl. "white", "black")
            state_map = {
                NewGsProductState.IDLE: ("Kitöltés", True, "#007bff", "white"),
                NewGsProductState.FILLING_IN_PROGRESS: ("Kitöltés folyamatban...", False, "#87CEEB", "black"),
                NewGsProductState.FORM_FILLED: ("Érvényesítés", True, "#C6FF80", "black"),
                NewGsProductState.VALIDATING_IN_PROGRESS: ("Érvényesítés folyamatban...", False, "#90EE90", "black")
            }
            # A kibővített tuple kicsomagolása
            text, enabled, bg_color_hex, text_color = state_map.get(self._gs_new_product_state, ("", False, "#cccccc", "black"))
            
            self.gs_fill_validate_button.setText(text)
            self.gs_fill_validate_button.setEnabled(enabled)
            
            color = QColor(bg_color_hex)
            
            # A stíluslap beállítása a háttér- ÉS a szövegszínnel
            self.gs_fill_validate_button.setStyleSheet(
                f"QPushButton {{ background-color: {color.name()}; color: {text_color}; }} "
                f"QPushButton:hover {{ background-color: {color.darker(110).name()}; }}"
            )

    def _update_detail_toolbar_buttons(self, is_editing_or_new: bool, is_product_selected: bool):
        """
        Frissíti a Detail Toolbar gombjainak láthatóságát és engedélyezettségét
        a termék aktuális állapota alapján.
        """
        if not self.detailToolbar:
            return

        # 1. Alapvető állapotváltozók begyűjtése
        is_product_sold = self._current_product.is_sold if self._current_product else False

        # Fő szabály: Ha a termék el van adva, minden le van tiltva.
        if is_product_sold:
            self.detailToolbar.setEnabled(False)
            return
        else:
            self.detailToolbar.setEnabled(True)

        # Mivel tudjuk, hogy a termék nincs eladva, a többi állapotot most már lekérdezhetjük.
        product_needs_upload = self._current_product.needs_upload if self._current_product else False
        is_gs_dependent = self._current_product.is_gs_dependent if self._current_product else False
        is_delisted_from_gs = self._current_product.is_delisted_on_gs if self._current_product else False
        is_product_valid = self._current_product.is_valid_for_upload if self._current_product else False
        is_product_in_sync = self._current_product.is_in_sync_and_ready if self._current_product else False

        # 2. Gombok engedélyezési logikájának meghatározása

        # "Eladás" gomb: Akkor aktív, ha van termék és nincs szerkesztés alatt.
        can_sell = is_product_selected and not is_editing_or_new
        self.detailToolbar.set_item_state("sold_btn", is_active_feature=can_sell, is_action_enabled=can_sell)
        sold_btn_item = self.detailToolbar.get_item_by_id("sold_btn")
        if sold_btn_item:
            sold_btn_item.setToolTip("Termék eladottként jelölése" if is_product_selected else "Nincs kiválasztott termék.")

        # "Leírás formázása" gomb: Akkor aktív, ha szerkesztési vagy új termék módban vagyunk.
        can_format_description = is_editing_or_new
        self.detailToolbar.set_item_state("description_format_btn", is_active_feature=can_format_description, is_action_enabled=can_format_description)
        format_btn_item = self.detailToolbar.get_item_by_id("description_format_btn")
        if format_btn_item:
            tooltip = "Leírás formázása"
            if not is_editing_or_new:
                tooltip = "A formázás csak szerkesztési módban érhető el."
            format_btn_item.setToolTip(tooltip)

        # "Feltöltés" gomb: Akkor aktív, ha a termék feltöltésre vár ÉS érvényes állapotú.
        can_upload = is_product_selected and not is_editing_or_new and product_needs_upload and is_product_valid
        self.detailToolbar.set_item_state("product_upload_btn", is_active_feature=can_upload, is_action_enabled=can_upload)
        upload_btn_item = self.detailToolbar.get_item_by_id("product_upload_btn")
        if upload_btn_item:
            tooltip = "Termék feltöltése a szerverre"
            if product_needs_upload and not is_product_valid:
                tooltip = "A feltöltés le van tiltva, mert a termék adatai hiányosak (pl. nincs kép, kategória)."
            elif not product_needs_upload and is_product_selected:
                tooltip = "A termék adatai naprakészek a szerveren, nincs mit feltölteni."
            elif is_editing_or_new:
                tooltip = "A művelethez előbb mentse el a változtatásokat."
            elif not is_product_selected:
                tooltip = "Nincs kiválasztott termék."
            upload_btn_item.setToolTip(tooltip)

        # "Piacterekről eltávolítás" gomb:
        # Akkor aktív, ha a termék szinkronban van, függetlenül attól, hogy GS-függő-e.
        can_remove_from_market = False
        if is_product_selected and not is_editing_or_new:
            # GS-függő termék eltávolítható, ha szinkronban van, vagy ha már törölték a GS-ről (de pl. Jófogásról még nem).
            is_removable_gs_product = is_gs_dependent and (is_product_in_sync or is_delisted_from_gs)
            # Nem GS-függő termék akkor távolítható el, ha szinkronban van (azaz sikeresen fel lett töltve valahova).
            is_removable_non_gs_product = not is_gs_dependent and is_product_in_sync
            
            can_remove_from_market = is_removable_gs_product or is_removable_non_gs_product

        self.detailToolbar.set_item_state("remove_from_markets_btn", is_active_feature=can_remove_from_market, is_action_enabled=can_remove_from_market)
        remove_btn_item = self.detailToolbar.get_item_by_id("remove_from_markets_btn")
        if remove_btn_item:
            tooltip = "Termék eltávolítása a piacterekről"
            if not can_remove_from_market and is_product_selected:
                # Általánosabb hibaüzenet, amely mindkét esetre érvényes.
                tooltip = "A művelet nem engedélyezett, amíg a termék nincs szinkronizálva egy piactérrel sem."
            elif is_editing_or_new:
                tooltip = "A művelethez előbb mentse el a változtatásokat."
            elif not is_product_selected:
                tooltip = "Nincs kiválasztott termék."
            remove_btn_item.setToolTip(tooltip)

        # "Jófogás" gomb logikája
        refresh_btn_item = self.detailToolbar.get_item_by_id("refresh_jf_product_btn")
        if not refresh_btn_item:
            return

        can_use_jf_button = False
        tooltip = "A művelet ebben az állapotban nem érhető el."

        if self._is_new_product_mode:
            # Új termék esetén csak akkor aktív, ha NEM GS-függő
            if not self.is_gs_dependent_checkbox.isChecked():
                can_use_jf_button = True
                tooltip = "Új hirdetés feladása a Jófogásra (űrlapkitöltés)"
        
        elif is_product_selected and not is_editing_or_new:
            # Meglévő termék esetén MINDIG aktív (ha valid a termék)
            if is_product_valid:
                can_use_jf_button = True
                tooltip = "Hirdetés feladása/újrafeladása a Jófogáson"
            else:
                tooltip = "Jófogás feltöltés letiltva, mert a termék adatai hiányosak (pl. nincs kép, kategória)."


        #Export gomb logikája
        can_export = is_product_selected and not is_editing_or_new
        self.detailToolbar.set_item_state("export_product_btn", is_active_feature=can_export, is_action_enabled=can_export)
        export_btn_item = self.detailToolbar.get_item_by_id("export_product_btn")
        if export_btn_item:
            tooltip = "Kiválasztott termék mappájának exportálása"
            if not is_product_selected:
                tooltip = "Nincs kiválasztott termék az exportáláshoz."
            elif is_editing_or_new:
                tooltip = "A művelethez előbb mentse vagy vonja vissza a változtatásokat."
            export_btn_item.setToolTip(tooltip)

        self.detailToolbar.set_item_state("refresh_jf_product_btn", is_active_feature=can_use_jf_button, is_action_enabled=can_use_jf_button)
        refresh_btn_item.setToolTip(tooltip)

    def _clear_form(self):
        self._current_product = None
        self.product_id_label.setText("N/A")
        self.created_at_label.setText("N/A")
        self.title_edit.clear(); self.description_edit.clear(); self.price_numeric_edit.clear()
        self.is_gs_dependent_checkbox.setVisible(False); self.is_gs_dependent_checkbox.setEnabled(False); self.is_gs_dependent_checkbox.setChecked(True)
        self.category_selector.set_category(MainCategory.UNCATEGORIZED, _sanitize_for_slug("Nincs alkategória"), _sanitize_for_slug("Nincs terméktípus"))
        self.category_selector.highlight_fields(False)
        self._gs_new_product_state = NewGsProductState.IDLE
        self._is_new_product_mode = False; self._is_editing_existing = False
        self._update_action_buttons_visibility(); self._update_form_visual_state()

    def _clear_form_for_new_product(self):
        self._current_product = None
        self.product_id_label.setText("..."); self.created_at_label.setText("...")
        self.title_edit.clear(); self.description_edit.clear(); self.price_numeric_edit.clear()
        self.is_gs_dependent_checkbox.setChecked(True); self.is_gs_dependent_checkbox.setEnabled(True); self.is_gs_dependent_checkbox.setVisible(True)
        self.category_selector.set_category(MainCategory.UNCATEGORIZED, _sanitize_for_slug("Nincs alkategória"), _sanitize_for_slug("Nincs terméktípus"))
        self.category_selector.highlight_fields(False)
        self._gs_new_product_state = NewGsProductState.IDLE
        self.fb_post_text_edit.clear()
        self.fb_ad_text_edit.clear()
        self.fb_hashtags_edit.clear()
        self.fb_post_url_edit.clear()
        self.fb_is_posted_checkbox.setChecked(False)
        self.fb_is_ad_created_checkbox.setChecked(False)
        self.fb_is_posted_checkbox.setEnabled(False)
        self.fb_is_ad_created_checkbox.setEnabled(False)

    @Slot(str)
    def set_product_by_id(self, product_id: Optional[str]):
        self._is_new_product_mode = False; self._is_editing_existing = False; self._update_form_visual_state()
        if product_id is None:
            self._clear_form(); self.initialProductLoadedComplete.emit(); return
        product = self.product_manager.get_product_by_id(product_id)
        if product:
            self.set_product(product)
        else:
            self._log(logging.WARNING, f"A '{product_id}' azonosítójú termék nem található."); self._clear_form()
            QMessageBox.warning(self, "Hiba", f"A kiválasztott termék ({product_id}) nem található.")

    def set_product(self, product: Optional[Product]):
        # Megnézzük, hogy ugyanaz-e a termék, mint ami eddig volt
        is_same_product = (self._current_product and product and self._current_product.id == product.id)
        
        self._current_product = product
        
        # A checkboxok letiltása alaphelyzetben
        self.fb_is_posted_checkbox.setEnabled(False)
        self.fb_is_ad_created_checkbox.setEnabled(False)
        
        # --- MÓDOSÍTÁS: Nézet visszaállítása CSAK ha másik termékre váltunk ---
        if not is_same_product:
            self._is_fb_mode = False
            if hasattr(self, 'view_stack'):
                self.view_stack.setCurrentIndex(0)
            self.fb_mode_toggle_button.set_on_state(False)
        else:
            # Ha ugyanaz a termék (pl. mentés után), megtartjuk a jelenlegi módot,
            # de biztosítjuk, hogy a gomb állapota szinkronban legyen
            self.fb_mode_toggle_button.set_on_state(self._is_fb_mode)
        # ---------------------------------------------------------------------

        self._gs_new_product_state = NewGsProductState.IDLE
        
        if product is None:
            self._set_new_product_mode(True)
            self.initialProductLoadedComplete.emit()
            return

        self.fb_mode_toggle_button.setVisible(True)

        # Fő adatlap mezőinek feltöltése
        self._is_new_product_mode = False
        self._is_editing_existing = False
        self.is_gs_dependent_checkbox.setVisible(False)
        self._update_form_visual_state()

        self.product_id_label.setText(product.id)
        self.created_at_label.setText(product.created_at.strftime("%Y.%m.%d %H:%M:%S"))
        self.title_edit.setText(product.title)
        self.description_edit.setText(product.description or "")
        self.price_numeric_edit.setValue(product.price_numeric or 0.0)
        self.category_selector.set_category(product.main_category, product.sub_category_slug, product.product_type_slug)
        self.category_selector.highlight_fields(product.needs_manual_category_review)
        
        # Facebook adatlap mezőinek feltöltése
        fb_data = product.facebook_data
        if fb_data:
            self.fb_post_text_edit.setPlainText(fb_data.post_text or "")
            self.fb_ad_text_edit.setPlainText(fb_data.ad_text or "")
            self.fb_hashtags_edit.setText(fb_data.hashtags or "")
            self.fb_is_posted_checkbox.setChecked(fb_data.is_posted)
            self.fb_is_ad_created_checkbox.setChecked(fb_data.is_ad_created)
            self.fb_post_url_edit.setText(fb_data.post_url or "")
        else:
            self.fb_post_text_edit.clear()
            self.fb_ad_text_edit.clear()
            self.fb_hashtags_edit.clear()
            self.fb_post_url_edit.clear()
            self.fb_is_posted_checkbox.setChecked(False)
            self.fb_is_ad_created_checkbox.setChecked(False)

        # A metódus végén beállítjuk a csak olvasható módot
        self._set_edit_mode(False)
        self.initialProductLoadedComplete.emit()

    def _save_changes(self):
        # --- ÚJ LOGIKA: Mentés FB módban ---
        if self._is_fb_mode:
            if not self._current_product: return
            
            try:
                self._current_product.facebook_data.post_text = self.fb_post_text_edit.toPlainText().strip()
                self._current_product.facebook_data.ad_text = self.fb_ad_text_edit.toPlainText().strip()
                self._current_product.facebook_data.hashtags = self.fb_hashtags_edit.text().strip()
                self._current_product.facebook_data.is_posted = self.fb_is_posted_checkbox.isChecked()
                self._current_product.facebook_data.is_ad_created = self.fb_is_ad_created_checkbox.isChecked()
                self._current_product.facebook_data.post_url = self.fb_post_url_edit.text().strip() or None

                self.productUpdated.emit(self._current_product, True, "Facebook adatok frissítve.")
                
                self._set_edit_mode(False)
            except Exception as e:
                QMessageBox.critical(self, "Hiba", f"Hiba a Facebook adatok mentésekor: {e}")
            return

        # --- RÉGI LOGIKA, VISSZAHELYEZVE A TRY...EXCEPT BLOKKBA ---
        try:
            if self._is_new_product_mode and self.is_gs_dependent_checkbox.isChecked():
                QMessageBox.warning(self, "Mentési hiba", "Ez a termék GS függő. Használja a 'Kitöltés' / 'Érvényesítés' gombot.")
                return
            
            validated_data = self._get_validated_data_from_form()
            
            if self._is_new_product_mode:
                if not self.is_gs_dependent_checkbox.isChecked():
                    if self.product_manager.check_if_product_exists(validated_data["title"], validated_data["price_numeric"]):
                        QMessageBox.warning(self, "Duplikált Termék", 
                                            "Már létezik aktív termék ezzel a névvel és árral.\n"
                                            "Kérjük, módosítsa az adatokat a mentés előtt.")
                        return # Megszakítjuk a mentést
                    if self._image_gallery_widget and self._image_gallery_widget.get_temporary_image_count() == 0:
                        raise ValueError("Legalább egy 'mixed_' képet fel kell tölteni az új, nem GS függő termékhez.")
                    
                    new_product = Product(
                        id="",
                        title=validated_data["title"],
                        description=validated_data["description"],
                        price_numeric=validated_data["price_numeric"],
                        price_raw="",
                        main_category=validated_data["main_cat_enum"],
                        main_category_slug=validated_data["main_cat_enum"].to_slug(),
                        sub_category_slug=validated_data["sub_cat_slug"],
                        product_type=validated_data["product_type_name"],
                        product_type_slug=validated_data["product_type_slug"],
                        is_gs_dependent=False,
                        is_sold=False,
                        needs_manual_category_review=validated_data["needs_review"],
                        needs_upload=True,
                        created_at=datetime.now()
                    )
                    self.productUpdated.emit(new_product, True, "Új termék mentése kezdeményezve.")
                    self._is_new_product_mode = False
                    self._update_action_buttons_visibility()
            
            else: # Meglévő termék frissítése
                if not self._current_product:
                    raise RuntimeError("Mentési hiba: Nincs aktuális termék a frissítéshez.")

                category_changed = (
                    validated_data["main_cat_enum"] != self._current_product.main_category or
                    validated_data["sub_cat_slug"] != self._current_product.sub_category_slug or
                    validated_data["product_type_slug"] != self._current_product.product_type_slug
                )

                if category_changed:
                    self.categoryChanged.emit(self._current_product.id, validated_data["main_cat_enum"], validated_data["sub_cat_slug"], validated_data["product_type_slug"])
                else:
                    self._current_product.title = validated_data["title"]
                    self._current_product.description = validated_data["description"]
                    self._current_product.price_numeric = validated_data["price_numeric"]
                    self._current_product.needs_manual_category_review = validated_data["needs_review"]
                    
                    if not self._current_product.needs_upload:
                        self._current_product.needs_upload = True
                    
                    self.productUpdated.emit(self._current_product, True, f"Termék '{self._current_product.id}' adatai frissítve.")
            
            self._set_edit_mode(False)
            self.category_selector.highlight_fields(validated_data["needs_review"])

        except (ValueError, RuntimeError) as e:
            QMessageBox.critical(self, "Hiba", f"Nem sikerült menteni a termék adatait: {e}")
            self.productUpdated.emit(self._current_product, False, f"Hiba a mentés során: {e}")

    @Slot()
    def _cancel_changes(self):
        if self._is_new_product_mode: self.newProductModeCancelled.emit()
        elif self._current_product: self.set_product_by_id(self._current_product.id)
        else: self._clear_form()
        self._is_editing_existing = False; self._is_new_product_mode = False; self._gs_new_product_state = NewGsProductState.IDLE
        self._update_action_buttons_visibility();
        self._update_form_visual_state()

    @Slot(str)
    def _handle_detail_toolbar_button_click(self, button_id: str):
        """
        Kezeli a toolbar gombjainak kattintásait. A refresh_jf_product_btn
        most már egységesen az űrlapkitöltést indítja.
        """
        if button_id == "sold_btn":
            self._handle_mark_as_sold_click()
        elif button_id == "product_upload_btn":
            self.productUploadRequested.emit()
        elif button_id == "remove_from_markets_btn":
            self.removeFromMarketsRequested.emit()
        elif button_id == "refresh_jf_product_btn":
            # A gomb funkciója most már EGYETLEN: elindítani a Jófogás űrlapkitöltést.
            self._handle_jf_fill_click()
        elif button_id == "description_format_btn":
            self.descriptionFormatRequested.emit()
        elif button_id == "export_product_btn":
            if self._current_product:
                self.productExportRequested.emit(self._current_product.id)

    @Slot()
    def _handle_mark_as_sold_click(self):
        if not self._current_product: QMessageBox.warning(self, "Nincs termék", "Nincs kiválasztva termék."); return
        if self._current_product.is_sold: QMessageBox.information(self, "Termék már eladva", "Ez a termék már eladottként van jelölve."); return
        confirm_dialog = ConfirmSoldDialog(self._current_product.title, self)
        if confirm_dialog.exec() == QDialog.Accepted: self.productMarkedAsSold.emit(self._current_product.id, confirm_dialog.should_delete_permanently())

    @Slot()
    def _handle_gs_fill_validate_click(self):
        if not self._is_new_product_mode or not self.is_gs_dependent_checkbox.isChecked(): return
        if self._gs_new_product_state == NewGsProductState.IDLE: self._initiate_gs_form_filling()
        elif self._gs_new_product_state == NewGsProductState.FORM_FILLED: self._initiate_gs_validation()

    def _initiate_gs_form_filling(self):
        try:
            title_to_check = self.title_edit.text().strip()
            price_to_check = self.price_numeric_edit.value()
            if self.product_manager.check_if_product_exists(title_to_check, price_to_check):
                QMessageBox.warning(self, "Duplikált Termék", 
                                    "Már létezik aktív termék ezzel a névvel és árral.\n"
                                    "Kérjük, módosítsa az adatokat a folytatás előtt.")
                return # Megszakítjuk a műveletet
            validated_data = self._get_validated_data_from_form()
            if not self._image_gallery_widget or self._image_gallery_widget.get_temporary_image_count() == 0:
                raise ValueError("Legalább egy 'mixed_' képet fel kell tölteni a termékhez.")
            prepared_data = {"title": validated_data["title"], "description": validated_data["description"], "price_numeric": validated_data["price_numeric"], "main_category_name": validated_data["main_cat_enum"].display_name, "main_category_enum_value": validated_data["main_cat_enum"].value, "sub_category_name": validated_data["sub_cat_name"], "product_type_name": validated_data["product_type_name"], "currency": self.currency_label.text(), "is_gs_dependent": self.is_gs_dependent_checkbox.isChecked()}
            self.gsNewProductFillRequested.emit(prepared_data); self.set_gs_new_product_state(NewGsProductState.FILLING_IN_PROGRESS)
        except (ValueError, RuntimeError) as e:
            QMessageBox.critical(self, "Hiba", f"Nem sikerült elindítani a kitöltést: {e}")

    def _initiate_gs_validation(self):
        """
        Előkészíti az adatokat és elindítja a manuális GS validálási folyamatot.
        A felhasználó megerősítése után azonnal frissíti a UI-t, majd kibocsátja
        a jelzést a háttérművelet elindításához.
        """
        try:
            # 1. Adatok validálása és összegyűjtése az űrlapról
            validated_data = self._get_validated_data_from_form()
            if not self._image_gallery_widget or self._image_gallery_widget.get_temporary_image_count() == 0:
                raise ValueError("Legalább egy 'mixed_' képet fel kell tölteni a termékhez.")

            # 2. Felhasználói megerősítés kérése
            if QMessageBox.question(self, "Feltöltés megerősítése", "Biztos benne, hogy manuálisan feltöltötte a terméket a Galéria Savaria oldalra?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.No:
                return  # Művelet megszakítása, ha a felhasználó a 'Nem'-et választja

            # 3. Ideiglenes Product objektum létrehozása a validáláshoz
            product_to_validate = Product(
                id="NEW_GS_VALIDATING",
                title=validated_data["title"],
                description=validated_data["description"],
                price_numeric=validated_data["price_numeric"],
                price_raw="",
                main_category=validated_data["main_cat_enum"],
                main_category_slug=validated_data["main_cat_enum"].to_slug(),
                sub_category_slug=validated_data["sub_cat_slug"],
                product_type=validated_data["product_type_name"],
                product_type_slug=validated_data["product_type_slug"],
                is_gs_dependent=self.is_gs_dependent_checkbox.isChecked(),
                is_sold=False,
                needs_manual_category_review=validated_data["needs_review"],
                needs_upload=True,
                created_at=datetime.now()
            )

            # 4. A UI állapotának frissítése a folyamat indítása ELŐTT
            # Ez a kulcs a hiba javításához: a gomb azonnal letiltódik és frissül.
            self.set_gs_new_product_state(NewGsProductState.VALIDATING_IN_PROGRESS)
            
            # 5. A jelzés kibocsátása a háttérfolyamat elindítására
            self.gsNewProductValidateRequested.emit(product_to_validate)

        except (ValueError, RuntimeError) as e:
            # Hibakezelés, ha az adatok nem megfelelőek
            QMessageBox.critical(self, "Hiba", f"Nem sikerült előkészíteni a terméket az érvényesítéshez: {e}")

    def get_product_data_for_validation(self) -> Optional[Product]:
        """
        Összegyűjti az űrlap adatait, és létrehoz egy ideiglenes Product objektumot,
        amelyet a MainController felhasználhat az automatikus validálás elindításához.
        Hiba esetén None-t ad vissza.
        """
        try:
            validated_data = self._get_validated_data_from_form()
            
            # Ez a rész megegyezik az _initiate_gs_validation metódusban lévővel
            product_to_validate = Product(
                id="NEW_GS_VALIDATING",
                title=validated_data["title"],
                description=validated_data["description"],
                price_numeric=validated_data["price_numeric"],
                price_raw="",
                main_category=validated_data["main_cat_enum"],
                main_category_slug=validated_data["main_cat_enum"].to_slug(),
                sub_category_slug=validated_data["sub_cat_slug"],
                product_type=validated_data["product_type_name"],
                product_type_slug=validated_data["product_type_slug"],
                is_gs_dependent=self.is_gs_dependent_checkbox.isChecked(),
                is_sold=False,
                needs_manual_category_review=validated_data["needs_review"],
                needs_upload=True,
                created_at=datetime.now()
            )
            return product_to_validate
        except (ValueError, RuntimeError) as e:
            self._log(logging.ERROR, f"Hiba a validálási adatok összegyűjtésekor: {e}")
            return None

    @Slot(NewGsProductState, str)
    def set_gs_new_product_state(self, state: NewGsProductState, message: Optional[str] = None):
        self._gs_new_product_state = state; self._update_action_buttons_visibility()
        if message: self._log(logging.INFO, f"GS állapotüzenet: {message}")

    @Slot()
    def _on_title_edit_return_pressed(self):
        product_title = self.title_edit.text().strip()
        if not product_title: self.category_selector.highlight_fields(True); return
        best_match = self.category_manager.find_best_category_by_item_name(product_title)
        if best_match:
            found_main_cat_str, found_sub_cat_str, found_item_type_str = best_match
            try:
                main_cat_enum = MainCategory(found_main_cat_str)
                self.category_selector.set_category(main_cat_enum, _sanitize_for_slug(found_sub_cat_str), _sanitize_for_slug(found_item_type_str))
                self.category_selector.highlight_fields(False)
            except Exception as e:
                self._log(logging.ERROR, f"Hiba a javasolt kategória beállítása során: {e}", exc_info=True); self.category_selector.highlight_fields(True)
        else:
            self.category_selector.highlight_fields(True)

    @Slot(str)
    def _format_price_input(self, text: str):
        """
        Slot, amely meghívja a központi formázó segédfüggvényt az ár mezőre.
        """
        # A belső QLineEdit objektumot adjuk át a formázónak.
        format_numeric_input(self.price_numeric_edit.lineEdit())

    @Slot(int)
    def _on_gs_dependent_checkbox_state_changed(self, state: int):
        if self._is_new_product_mode: self._gs_new_product_state = NewGsProductState.IDLE; self._update_action_buttons_visibility()
        if QApplication.instance(): QApplication.instance().style().polish(self.is_gs_dependent_checkbox)

    @Slot()
    def update_toolbar_state(self):
        """
        Slot, amely külső eseményre (pl. FTP kapcsolat változása)
        frissíti a detail toolbar gombjainak állapotát.
        """
        is_editing_or_new = self._is_new_product_mode or self._is_editing_existing
        is_product_selected = self._current_product is not None
        
        self._update_detail_toolbar_buttons(is_editing_or_new, is_product_selected)
        logger.debug("Detail toolbar state updated due to external signal (e.g., FTP connection change).")

    @Slot()
    def _handle_reactivate_click(self):
        if self._current_product:
            reply = QMessageBox.question(self, "Újraaktiválás megerősítése",
                                         f"Biztosan újra szeretné aktiválni a(z) '{self._current_product.title}' terméket?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.productReactivated.emit(self._current_product.id)

    @Slot()
    def _handle_delete_permanently_click(self):
        if self._current_product:
            reply = QMessageBox.question(self, "Végleges törlés megerősítése",
                                         f"Biztosan végleg törli a(z) '{self._current_product.title}' terméket? Ez a művelet nem vonható vissza!",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.productPermanentlyDeleted.emit(self._current_product.id)

    # gui/product_detail_widget/product_detail_widget.py

    @Slot()
    def _handle_jf_fill_click(self):
        """
        Előkészíti az adatokat, megerősítést kér, és elindítja a Jófogás
        űrlapkitöltési folyamatát.
        """
        prepared_data = {}
        dialog_title = ""
        dialog_text = ""

        try:
            if self._is_new_product_mode:
                # ESET 1: Új termék
                dialog_title = "Jófogás hirdetés feladása"
                dialog_text = "Biztosan elindítja az új hirdetés feladását a Jófogáson?"
                validated_data = self._get_validated_data_from_form()
                
                # A Jófogás feltöltő az 'original_' képeket használja, nem a 'mixed_'-et.
                # Itt most csak azt ellenőrizzük, hogy van-e kép az ideiglenes mappában.
                if not self._image_gallery_widget or not any(f.name.startswith("original_") for f in self._image_gallery_widget._tmp_image_dir.iterdir()):
                    raise ValueError("Legalább egy 'original_' képet fel kell tölteni az új termékhez a Jófogás-feltöltés előtt.")

                # ### JAVÍTÁS: Adatgyűjtés a validált UI adatokból, NEM a self._current_product-ból ###
                prepared_data = {
                    # ID és slug-ok szándékosan nincsenek itt, mert új terméknél még nincsenek.
                    # A feltöltő ebből tudja, hogy a tmp_images mappát kell használnia.
                    "title": validated_data["title"],
                    "description": validated_data["description"],
                    "price_numeric": validated_data["price_numeric"],
                    "main_category_name": validated_data["main_cat_enum"].display_name,
                    "sub_category_name": validated_data["sub_cat_name"],
                    "product_type_name": validated_data["product_type_name"]
                }
            
            elif self._current_product:
                # ESET 2: Meglévő termék ("frissítés")
                dialog_title = "Jófogás hirdetés újrafeladása"
                dialog_text = f"A Jófogáson a frissítés egy 'törlés és újra feladás' folyamat.\n\nBiztosan elindítja a(z) '{self._current_product.title}' hirdetés újrafeladását?"
                
                # ### JAVÍTÁS: Ellenőrzés 'original_' képekre a termék objektumon ###
                if self._current_product.num_original_images == 0:
                     raise ValueError("A termék újrafeladásához szükséges legalább egy 'original_' kép.")
                
                sub_category_name = next((name for name, slug in self.category_manager.get_sub_categories_with_slugs_for_main(self._current_product.main_category) if slug == self._current_product.sub_category_slug), "")
                
                product_type_name = ""
                if sub_category_name:
                    all_product_types = self.category_manager.get_product_types_for_sub(self._current_product.main_category, sub_category_name)
                    product_type_name = next((name for name in all_product_types if _sanitize_for_slug(name) == self._current_product.product_type_slug), "")

                # ### JAVÍTÁS: A hiányzó kulcsok hozzáadása a helyes működéshez ###
                prepared_data = {
                    "id": self._current_product.id,
                    "main_category_slug": self._current_product.main_category_slug,
                    "sub_category_slug": self._current_product.sub_category_slug,
                    "product_type_slug": self._current_product.product_type_slug, # <-- EZ AZ ÚJ, FONTOS SOR
                    "title": self._current_product.title, 
                    "description": self._current_product.description, 
                    "price_numeric": self._current_product.price_numeric, 
                    "main_category_name": self._current_product.main_category.display_name,
                    "sub_category_name": sub_category_name,
                    "product_type_name": product_type_name
                }
            else:
                # Nincs kiválasztott termék, és nem is új termék módban vagyunk.
                return

            # A megerősítő ablak megjelenítése a metódus végén
            reply = QMessageBox.question(self, dialog_title, dialog_text, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                return

            # Indítás (csak ha 'Igen'-t nyomtak)
            self.jfNewProductFillRequested.emit(prepared_data)
            
            # Vizuális visszajelzés
            jf_button_item = self.detailToolbar.get_item_by_id("refresh_jf_product_btn")
            if jf_button_item:
                jf_button_item.setEnabled(False)
                jf_button_item.setToolTip("Kitöltés folyamatban...")

        except (ValueError, RuntimeError) as e:
            QMessageBox.critical(self, "Hiba", f"Nem sikerült elindítani a Jófogás kitöltést: {e}")

    
    def format_description(self, options: dict):
        """
        A leírás mező tartalmát formázza a kapott opciók alapján.
        A szöveget bekezdésenként (blokkonként) dolgozza fel, hogy elkerülje az adatvesztést.
        """
        if self.description_edit.isReadOnly():
            self._log(logging.WARNING, "A formázás nem lehetséges, mert a mező csak olvasható.")
            return

        format_type = options.get("format_type")
        if not format_type:
            return

        self._undo_buffer = self.description_edit.toHtml()

        cursor = self.description_edit.textCursor()
        has_selection = cursor.hasSelection()
        
        lines = []
        if has_selection:
            selected_text = cursor.selectedText()
            lines = selected_text.split('\u2029')
        else:
            document = self.description_edit.document()
            block = document.begin()
            while block.isValid():
                lines.append(block.text())
                block = block.next()

        formatted_text = ""

        if format_type == "cleanup_whitespace":
            stripped_lines = [line.strip() for line in lines]
            non_empty_lines = [line for line in stripped_lines if line]
            formatted_text = '\n\n'.join(non_empty_lines)
            self._log(logging.INFO, "Formázás: Takarítás.")
        
        elif format_type == "unify_lines":
            non_empty_lines = [line.strip() for line in lines if line.strip()]
            formatted_text = ' '.join(non_empty_lines)
            self._log(logging.INFO, "Formázás: Bekezdés.")

        elif format_type == "bullet_points":
            bullet_char = options.get("bullet_char", "•")
            non_empty_lines = [line.strip() for line in lines if line.strip()]
            bulleted_lines = [f"{bullet_char} {line}" for line in non_empty_lines]
            formatted_text = '\n'.join(bulleted_lines)
            self._log(logging.INFO, f"Formázás: Felsorolás '{bullet_char}' karakterrel.")

        if has_selection:
            cursor.insertText(formatted_text)
        else:
            self.description_edit.setPlainText(formatted_text)

    def undo_last_format(self):
        """Visszaállítja a leírást a legutóbbi formázás előtti állapotára."""
        if self._undo_buffer is not None:
            self.description_edit.setHtml(self._undo_buffer)
            self._undo_buffer = None # Csak egyszer lehet visszavonni
            self._log(logging.INFO, "A leírás formázása visszavonva.")
        else:
            self._log(logging.WARNING, "Nincs mit visszavonni.")

    @Slot()
    def _toggle_fb_mode(self):
        """Átkapcsolja a nézetet a Fő és a Facebook adatlap között."""
        if self._is_editing_existing:
            return # Szerkesztés közben nem engedélyezzük a váltást

        self._is_fb_mode = not self._is_fb_mode
        self.view_stack.setCurrentIndex(1 if self._is_fb_mode else 0)
        self.fb_mode_toggle_button.set_on_state(self._is_fb_mode)
        self._update_action_buttons_visibility()
        if self._image_gallery_widget:
            self._image_gallery_widget.set_fb_selection_mode(self._is_fb_mode)
        self._log(logging.DEBUG, f"Nézet váltva: {'Facebook' if self._is_fb_mode else 'Fő adatlap'}.")

    @Slot()
    def _on_form_data_changed(self):
        """
        Azonnal engedélyezi a mentés gombot, ha bármelyik szerkeszthető mezőben
        változás történik szerkesztési módban.
        """
        # Ez a metódus csak akkor csinál bármit, ha szerkesztési módban vagyunk
        if self._is_editing_existing or self._is_new_product_mode:
            # A flaget csak egyszer kell beállítani
            if not self.save_button.isEnabled():
                self.save_button.setEnabled(True)
                self._log(logging.DEBUG, "Változás észlelve az űrlapon, Mentés gomb engedélyezve.")

    @Slot()
    def _handle_fb_post_click(self):
        """Kezeli a 'Posztolás' gomb kattintását szigorú ellenőrzésekkel."""
        if not self._current_product:
            return

        # 1. Adatok begyűjtése
        post_text = self.fb_post_text_edit.toPlainText().strip()
        hashtags = self.fb_hashtags_edit.text().strip()
        
        selected_images = []
        if self._current_product.facebook_data:
            selected_images = self._current_product.facebook_data.selected_images

        # 2. Hibalista összeállítása (Kötelező feltételek)
        errors = []
        if not post_text:
            errors.append("- Hiányzik a poszt szövege!")
        if not selected_images:
            errors.append("- Nincs kijelölt kép! Kérlek, pipálj ki legalább egyet a galériában.")

        if errors:
            error_message = "A posztolás nem indítható az alábbi hiányosságok miatt:\n\n" + "\n".join(errors)
            QMessageBox.warning(self, "Hiányzó adatok", error_message)
            return

        # 3. Figyelmeztetés (Opcionális feltételek - Hashtag)
        if not hashtags:
            reply = QMessageBox.question(
                self, 
                "Hiányzó Hashtagek", 
                "Nem adtál meg hashtageket (pl. #antik, #bútor).\nEzek nélkül a poszt sokkal kevesebb emberhez jut el.\n\nBiztosan folytatod?",
                QMessageBox.Yes | QMessageBox.No, 
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                self.fb_hashtags_edit.setFocus()
                return

        # 4. Végső megerősítés
        image_count = len(selected_images)
        confirm_text = (
            f"Termék: {self._current_product.title}\n"
            f"Képek száma: {image_count} db\n"
            f"Hashtagek: {'Van' if hashtags else 'Nincs'}\n\n"
            "Indulhat a VALÓDI posztolás a Facebookra?"
        )

        if QMessageBox.question(self, "Posztolás indítása", confirm_text, QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self._log(logging.INFO, f"Facebook posztolás kérés küldése: {self._current_product.title} ({image_count} képpel)")
            
            # --- EZ A LÉNYEG: A JEL KIBOCSÁTÁSA ---
            self.fbPostRequested.emit(self._current_product)

    @Slot()
    def _handle_fb_ad_create_click(self):
        """Kezeli a 'Hirdetés' gomb kattintását (Itt a hashtag TILOS/szükségtelen, így azt nem ellenőrizzük)."""
        if not self._current_product:
            return

        ad_text = self.fb_ad_text_edit.toPlainText().strip()
        
        selected_images = []
        if self._current_product.facebook_data:
            selected_images = self._current_product.facebook_data.selected_images

        # Validáció (Hirdetésnél csak a szöveg és a kép kell)
        errors = []
        if not ad_text:
            errors.append("- Hiányzik a hirdetés szövege!")
        if not selected_images:
            errors.append("- Nincs kijelölt kép a hirdetéshez!")

        if errors:
            QMessageBox.warning(self, "Hiányzó adatok", "A hirdetés nem hozható létre:\n\n" + "\n".join(errors))
            return

        # Megerősítés
        if QMessageBox.question(self, "Hirdetés létrehozása", f"Biztosan létrehozod a hirdetést {len(selected_images)} képpel?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self._log(logging.INFO, f"Facebook hirdetés létrehozása: {self._current_product.title}")
            # IDE JÖN MAJD AZ AUTOMATOR HÍVÁSA
            QMessageBox.information(self, "Infó", "Hirdetés létrehozása (szimuláció) elindult.")