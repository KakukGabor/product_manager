# Helye: gui/product_detail_widget/pdw_ui.py

import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QLineEdit, QTextEdit, QPushButton, QSizePolicy, QScrollArea,
    QCheckBox, QGroupBox, QAbstractSpinBox, QStackedWidget, QTabWidget
)
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt, QSize

from gui.formatted_double_spinbox import FormattedDoubleSpinBox
from gui.toolbar_widget.toolbar_widget import ToolbarWidget
from gui.toolbar_widget.two_state_button import TwoStateButton
from gui.product_detail_widget.pdw_styles import PRODUCT_DETAIL_STYLESHEET
from gui.product_detail_widget.category_selector_widget import CategorySelectorWidget

class ProductDetailUi:
    """
    Ez az osztály felelős a ProductDetailWidget felhasználói felületének
    létrehozásáért és elrendezéséért.
    """
    def setup_ui(self, parent_widget: QWidget):
        main_layout = QVBoxLayout(parent_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # --- EGYETLEN KÖZÖS GÖRGETHETŐ KONTÉNER ---
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setObjectName("productDetailScrollArea")
        parent_widget.scroll_area = scroll_area

        scroll_content_widget = QWidget()
        scroll_area.setWidget(scroll_content_widget)
        scroll_content_widget.setObjectName("scrollContentWidget")
        parent_widget.scroll_content_widget = scroll_content_widget

        # A görgethető területen belüli fő elrendezés
        content_v_layout = QVBoxLayout(scroll_content_widget)
        content_v_layout.setSpacing(10)

        # --- FELSŐ SÁV A GOMBBAL (a görgethető területen BELÜL) ---
        top_bar_layout = QHBoxLayout()
        top_bar_layout.addStretch() # Jobbra tolja a gombot

        icons_dir = os.path.join(parent_widget.product_manager.app_root_dir, "res", "icons")
        main_mode_icon = os.path.join(icons_dir, "detail_mode_main.png")
        fb_mode_icon = os.path.join(icons_dir, "detail_mode_fb.png")

        parent_widget.fb_mode_toggle_button = TwoStateButton(
            item_id="fb_mode_toggle",
            icon_off_path=main_mode_icon,
            icon_on_path=fb_mode_icon,
            tooltip="Váltás a fő termékadatlap és a Facebook adatok között",
            parent=parent_widget
        )
        parent_widget.fb_mode_toggle_button.set_item_size(QSize(28, 28))
        top_bar_layout.addWidget(parent_widget.fb_mode_toggle_button)
        
        content_v_layout.addLayout(top_bar_layout)

        # --- QStackedWidget a nézetek váltásához (a gomb ALATT) ---
        parent_widget.view_stack = QStackedWidget()
        content_v_layout.addWidget(parent_widget.view_stack)
        
        # A fő elrendezéshez a központi görgethető területet adjuk hozzá
        main_layout.addWidget(scroll_area)

        # --- A. Fő Adatlap Widget LÉTREHOZÁSA (már nem scroll area) ---
        main_details_widget = self._create_main_details_widget(parent_widget)
        parent_widget.view_stack.addWidget(main_details_widget)

        # --- B. Facebook Adatlap Widget LÉTREHOZÁSA (már nem scroll area) ---
        facebook_details_widget = self._create_facebook_details_widget(parent_widget)
        parent_widget.view_stack.addWidget(facebook_details_widget)

        # --- Alsó gombsor ---
        button_layout = QHBoxLayout()
        parent_widget.edit_button = QPushButton("Szerkesztés")
        parent_widget.edit_button.setObjectName("editButton")
        button_layout.addWidget(parent_widget.edit_button)

        parent_widget.save_button = QPushButton("Mentés")
        parent_widget.save_button.setObjectName("saveButton")
        button_layout.addWidget(parent_widget.save_button)
        
        parent_widget.cancel_button = QPushButton("Mégse")
        parent_widget.cancel_button.setObjectName("cancelButton")
        button_layout.addWidget(parent_widget.cancel_button)

        main_layout.addLayout(button_layout)
        
        # --- Detail Toolbar ---
        icons_dir = os.path.join(parent_widget.product_manager.app_root_dir, "res", "icons")
        mail_icon_path = os.path.join(icons_dir, "email.png")
        dollar_icon_path = os.path.join(icons_dir, "dollar.png")
        product_upload_icon_path = os.path.join(icons_dir, "upload_product.png")
        export_icon_path = os.path.join(icons_dir, "export.png")

        detail_toolbar_button_configs = [
            {"id": "email_btn", "type": "simple_push", "icon_path": mail_icon_path, "tooltip": "Termék adatok küldése emailben"},
            {"id": "export_product_btn", "type": "simple_push", "icon_path": export_icon_path, "tooltip": "Exportálás"},
            {"id": "sold_btn", "type": "simple_push", "icon_path": dollar_icon_path, "tooltip": "Termék eladottként jelölése"},
            {"id": "product_upload_btn", "type": "simple_push", "icon_path": product_upload_icon_path, "tooltip": "Termék feltöltése a szerverre"},
            {"id": "remove_from_markets_btn", "type": "simple_push", "icon_path": os.path.join(icons_dir, "remove_from_markets.png"), "tooltip": "Termék eltávolítása a piacterekről"},
            {"id": "refresh_jf_product_btn", "type": "simple_push", "icon_path": os.path.join(icons_dir, "refresh_jf_product.png"), "tooltip": "Jófogás hirdetés frissítése/kiemelése"},
            {"id": "description_format_btn", "type": "simple_push", "icon_path": os.path.join(icons_dir, "description_format.png"), "tooltip": "Leírás formázása"},
        ]
        
        parent_widget.detailToolbar = ToolbarWidget(
            settings_manager=parent_widget.product_manager.settings_manager,
            item_configs=detail_toolbar_button_configs,
            orientation=Qt.Horizontal,
            settings_key="detail_toolbar_order",
            item_size=QSize(30, 30),
            parent=parent_widget
        )
        
        parent_widget.detailToolbar.set_toolbar_background_color(QColor("#d9d9f3"))
        parent_widget.detailToolbar.set_toolbar_bottom_border_color(QColor("#B0C7C9"))
        parent_widget.detailToolbar.set_button_background_color(QColor("#9CC4E1"))
        parent_widget.detailToolbar.set_grid_visibility(True)
        main_layout.addWidget(parent_widget.detailToolbar)

        parent_widget.setStyleSheet(PRODUCT_DETAIL_STYLESHEET)

    def _create_main_details_widget(self, parent_widget: QWidget) -> QWidget:
        """Létrehozza a fő termékadatlapot tartalmazó widgetet."""
        main_details_container = QWidget()

        form_layout = QFormLayout(main_details_container)
        form_layout.setContentsMargins(0, 0, 0, 0) # A margót a szülő kezeli
        form_layout.setSpacing(10)
        form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        id_line_layout = QHBoxLayout()
        
        id_label_text = QLabel("Termék ID:")
        id_line_layout.addWidget(id_label_text)
        
        parent_widget.product_id_label = QLabel("Nincs")
        parent_widget.product_id_label.setStyleSheet("font-weight: bold; color: #555;")
        id_line_layout.addWidget(parent_widget.product_id_label)
        
        id_line_layout.addStretch()

        parent_widget.is_gs_dependent_checkbox = QCheckBox("GS Függőség")
        parent_widget.is_gs_dependent_checkbox.setChecked(True)
        parent_widget.is_gs_dependent_checkbox.setVisible(False)
        id_line_layout.addWidget(parent_widget.is_gs_dependent_checkbox)
        
        form_layout.addRow(id_line_layout)

        parent_widget.created_at_label = QLabel("N/A")
        form_layout.addRow("Létrehozva:", parent_widget.created_at_label)

        parent_widget.title_edit = QLineEdit()
        parent_widget.title_edit.setPlaceholderText("Termék címe")
        parent_widget.title_edit.setStyleSheet("font-weight: bold;")
        form_layout.addRow("Cím:", parent_widget.title_edit)

        parent_widget.description_edit = QTextEdit()
        parent_widget.description_edit.setPlaceholderText("Termék részletes leírása")
        parent_widget.description_edit.setMinimumHeight(150)
        form_layout.addRow("Leírás:", parent_widget.description_edit)

        price_layout = QHBoxLayout()
        parent_widget.price_numeric_edit = FormattedDoubleSpinBox()
        parent_widget.price_numeric_edit.setRange(0.0, 999999999.0)
        parent_widget.price_numeric_edit.setButtonSymbols(QAbstractSpinBox.NoButtons)
        parent_widget.price_numeric_edit.setDecimals(0)
        parent_widget.price_numeric_edit.setStyleSheet("font-size: 11pt; font-weight: bold;")
        price_layout.addWidget(parent_widget.price_numeric_edit, 1)

        parent_widget.currency_label = QLabel("HUF")
        parent_widget.currency_label.setStyleSheet("font-weight: bold;")
        price_layout.addWidget(parent_widget.currency_label)
        form_layout.addRow("Ár:", price_layout)

        parent_widget.category_selector = CategorySelectorWidget(parent_widget.category_manager, parent_widget)
        form_layout.addRow(parent_widget.category_selector)

        parent_widget.gs_fill_validate_button = QPushButton("Kitöltés / Érvényesítés")
        parent_widget.gs_fill_validate_button.setObjectName("gsFillValidateButton")
        form_layout.addRow(parent_widget.gs_fill_validate_button)

        sold_buttons_layout = QHBoxLayout()
        parent_widget.reactivate_button = QPushButton("Újra aktiválás")
        parent_widget.reactivate_button.setObjectName("reactivateButton")
        parent_widget.reactivate_button.setStyleSheet("background-color: #28a745; color: white;")
        sold_buttons_layout.addWidget(parent_widget.reactivate_button)

        parent_widget.delete_permanently_button = QPushButton("Végleges törlés")
        parent_widget.delete_permanently_button.setObjectName("deletePermanentlyButton")
        parent_widget.delete_permanently_button.setStyleSheet("background-color: #dc3545; color: white;")
        sold_buttons_layout.addWidget(parent_widget.delete_permanently_button)
        form_layout.addRow(sold_buttons_layout)

        return main_details_container

    def _create_facebook_details_widget(self, parent_widget: QWidget) -> QWidget:
        """Létrehozza a Facebook-specifikus adatokat tartalmazó widgetet."""
        fb_details_container = QWidget()

        form_layout = QFormLayout(fb_details_container)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(10)
        form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        # 1. Konténer a szövegdobozoknak és a gomboknak
        description_area_container = QWidget()
        description_area_layout = QHBoxLayout(description_area_container)
        description_area_layout.setContentsMargins(0, 0, 0, 0)
        description_area_layout.setSpacing(10)

        # 2. A bal oldali TabWidget (Leírások)
        parent_widget.fb_description_tabs = QTabWidget()
        
        parent_widget.fb_post_text_edit = QTextEdit()
        parent_widget.fb_description_tabs.addTab(parent_widget.fb_post_text_edit, "Poszt Szöveg")
        
        parent_widget.fb_ad_text_edit = QTextEdit()
        parent_widget.fb_description_tabs.addTab(parent_widget.fb_ad_text_edit, "Hirdetés Szöveg")
        
        parent_widget.fb_description_tabs.setMinimumHeight(150)
        
        # Hozzáadjuk a layoutoz, stretch=1, hogy kitöltse a teret
        description_area_layout.addWidget(parent_widget.fb_description_tabs, 1)

        # 3. A jobb oldali gomb panel
        buttons_panel_layout = QVBoxLayout()
        # Kis felső margó (25px), hogy a gombok teteje kb. a tab fülek aljával legyen egyvonalban
        buttons_panel_layout.setContentsMargins(0, 25, 0, 0) 
        buttons_panel_layout.setSpacing(10)

        parent_widget.fb_post_button = QPushButton("Posztolás")
        parent_widget.fb_post_button.setToolTip("Tartalom közzététele a Facebook oldalon")
        parent_widget.fb_post_button.setStyleSheet("""
            QPushButton {
                background-color: #4267B2;
                color: white;
                font-weight: bold;
                border-radius: 3px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #365899; /* Kicsit sötétebb kék, ha fölé viszed az egeret */
            }
            QPushButton:disabled {
                background-color: #cccccc; /* Szürke háttér */
                color: #666666;            /* Sötétszürke szöveg */
            }
        """)
        
        # --- MÓDOSÍTÁS: Rövidebb gombfelirat ---
        parent_widget.fb_ad_create_button = QPushButton("Hirdetés")
        parent_widget.fb_ad_create_button.setToolTip("Fizetett hirdetés létrehozása a Business Managerben")
        
        buttons_panel_layout.addWidget(parent_widget.fb_post_button)
        buttons_panel_layout.addWidget(parent_widget.fb_ad_create_button)
        buttons_panel_layout.addStretch() # A gombok maradjanak felül tömörülve

        description_area_layout.addLayout(buttons_panel_layout, 0)

        # --- MÓDOSÍTÁS: Címke nélkül adjuk hozzá, így balra igazodik és kitölti a sort ---
        form_layout.addRow(description_area_container)

        # További mezők...
        parent_widget.fb_hashtags_edit = QLineEdit()
        parent_widget.fb_hashtags_edit.setPlaceholderText("#antik, #bútor, #neoreneszánsz")
        form_layout.addRow("Hashtagek:", parent_widget.fb_hashtags_edit)
        
        status_groupbox = QGroupBox("Státusz")
        status_layout = QHBoxLayout(status_groupbox)
        
        parent_widget.fb_is_posted_checkbox = QCheckBox("Posztolva")
        status_layout.addWidget(parent_widget.fb_is_posted_checkbox)

        parent_widget.fb_is_ad_created_checkbox = QCheckBox("Hirdetés létrehozva")
        status_layout.addWidget(parent_widget.fb_is_ad_created_checkbox)
        status_layout.addStretch()
        
        form_layout.addRow(status_groupbox)

        parent_widget.fb_post_url_edit = QLineEdit()
        parent_widget.fb_post_url_edit.setPlaceholderText("A poszt URL-je itt fog megjelenni")
        parent_widget.fb_post_url_edit.setReadOnly(True)
        parent_widget.fb_post_url_edit.setStyleSheet("background-color: #f0f0f0; color: #3b5998; font-style: italic;")
        form_layout.addRow("Poszt URL:", parent_widget.fb_post_url_edit)

        return fb_details_container