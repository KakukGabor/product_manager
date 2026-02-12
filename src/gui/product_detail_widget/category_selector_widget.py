# src/gui/product_detail_widget/category_selector_widget.py
import logging
from typing import List, Optional, Tuple
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QComboBox, QSizePolicy
from PySide6.QtGui import QPalette
from PySide6.QtCore import Qt, Signal

from models.product_model import MainCategory, _sanitize_for_slug
from managers.product_category_manager import ProductCategoryManager

logger = logging.getLogger(__name__)

class CategorySelectorWidget(QWidget):
    """
    Egy önálló widget a termékkategóriák (fő, al, típus) kiválasztására.
    Kezeli a legördülő listák egymástól függő feltöltését.
    """
    # Jelez, ha a felhasználó megváltoztatta a kategóriát.
    # A kibocsátott adatok: (MainCategory enum, sub_category_slug, product_type_slug)
    categoryChanged = Signal(object, str, str)

    def __init__(self, category_manager: ProductCategoryManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.category_manager = category_manager
        self._setup_ui()
        self._connect_signals()
        self.populate_main_categories()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.category_group_box = QGroupBox("Kategorizálás")
        self.category_group_box.setObjectName("categoryGroupBox")
        category_group_layout = QVBoxLayout(self.category_group_box)

        category_selectors_layout = QHBoxLayout()

        self.main_category_combo = QComboBox()
        self.main_category_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        category_selectors_layout.addWidget(self.main_category_combo)

        self.sub_category_combo = QComboBox()
        self.sub_category_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        category_selectors_layout.addWidget(self.sub_category_combo)

        self.product_type_combo = QComboBox()
        self.product_type_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        category_selectors_layout.addWidget(self.product_type_combo)

        category_group_layout.addLayout(category_selectors_layout)
        main_layout.addWidget(self.category_group_box)

    def _connect_signals(self):
        self.main_category_combo.currentIndexChanged.connect(self._on_main_category_changed)
        self.sub_category_combo.currentIndexChanged.connect(self._on_sub_category_changed)
        self.product_type_combo.currentIndexChanged.connect(self._emit_category_changed)

    def populate_main_categories(self):
        self.main_category_combo.blockSignals(True)
        self.main_category_combo.clear()
        main_categories_enums = self.category_manager.get_main_categories()
        self.main_category_combo.addItem("Nincs fő kategória", MainCategory.UNCATEGORIZED)
        for cat_enum in main_categories_enums:
            self.main_category_combo.addItem(cat_enum.display_name, cat_enum)
        self.main_category_combo.blockSignals(False)

    def _on_main_category_changed(self):
        self.sub_category_combo.blockSignals(True)
        self.sub_category_combo.clear()
        selected_main_cat_enum: MainCategory = self.main_category_combo.currentData()

        if selected_main_cat_enum is None or selected_main_cat_enum == MainCategory.UNCATEGORIZED:
            self.sub_category_combo.addItem("Nincs alkategória", _sanitize_for_slug("Nincs alkategória"))
        else:
            sub_categories_names = self.category_manager.get_sub_categories_for_main(selected_main_cat_enum)
            self.sub_category_combo.addItem("Nincs alkategória", _sanitize_for_slug("Nincs alkategória"))
            for sub_cat_name in sub_categories_names:
                self.sub_category_combo.addItem(sub_cat_name, _sanitize_for_slug(sub_cat_name))

        self.sub_category_combo.blockSignals(False)
        self._on_sub_category_changed() # Láncolt hívás a terméktípusok frissítéséhez

    def _on_sub_category_changed(self):
        self.product_type_combo.blockSignals(True)
        self.product_type_combo.clear()
        selected_main_cat_enum: MainCategory = self.main_category_combo.currentData()
        selected_sub_cat_slug: str = self.sub_category_combo.currentData()

        if selected_main_cat_enum is None or selected_main_cat_enum == MainCategory.UNCATEGORIZED or \
           selected_sub_cat_slug is None or selected_sub_cat_slug == _sanitize_for_slug("Nincs alkategória"):
            self.product_type_combo.addItem("Nincs terméktípus", _sanitize_for_slug("Nincs terméktípus"))
        else:
            sub_cat_name = self.sub_category_combo.currentText()
            product_types_names = self.category_manager.get_product_types_for_sub(selected_main_cat_enum, sub_cat_name)
            self.product_type_combo.addItem("Nincs terméktípus", _sanitize_for_slug("Nincs terméktípus"))
            for prod_type_name in product_types_names:
                self.product_type_combo.addItem(prod_type_name, _sanitize_for_slug(prod_type_name))

        self.product_type_combo.blockSignals(False)
        self._emit_category_changed()

    def _emit_category_changed(self):
        """Kibocsátja a categoryChanged jelet az aktuális értékekkel."""
        if not self.signalsBlocked():
            main, sub, p_type = self.get_category()
            self.categoryChanged.emit(main, sub, p_type)
            
    # --- Publikus API a szülő widget számára ---

    def set_enabled(self, enabled: bool):
        """Engedélyezi vagy letiltja az összes legördülő listát."""
        self.main_category_combo.setEnabled(enabled)
        self.sub_category_combo.setEnabled(enabled)
        self.product_type_combo.setEnabled(enabled)
        
    def set_category(self, main_cat: MainCategory, sub_cat_slug: str, prod_type_slug: str):
        """Programozottan beállítja a kategóriákat."""
        self.blockSignals(True)
        
        # Fő kategória beállítása
        main_cat_index = self.main_category_combo.findData(main_cat)
        if main_cat_index >= 0:
            self.main_category_combo.setCurrentIndex(main_cat_index)
            # A _on_main_category_changed manuális hívása frissíti a következő listát
            self._on_main_category_changed()

        # Alkategória beállítása
        sub_cat_index = self.sub_category_combo.findData(sub_cat_slug)
        if sub_cat_index >= 0:
            self.sub_category_combo.setCurrentIndex(sub_cat_index)
            self._on_sub_category_changed()

        # Terméktípus beállítása
        prod_type_index = self.product_type_combo.findData(prod_type_slug)
        if prod_type_index >= 0:
            self.product_type_combo.setCurrentIndex(prod_type_index)
            
        self.blockSignals(False)

    def get_category(self) -> Tuple[MainCategory, str, str]:
        """Visszaadja a jelenleg kiválasztott kategóriákat."""
        main_cat = self.main_category_combo.currentData()
        sub_cat_slug = self.sub_category_combo.currentData()
        prod_type_slug = self.product_type_combo.currentData()
        return main_cat, sub_cat_slug, prod_type_slug

    def highlight_fields(self, highlight: bool):
        """Beállítja vagy törli a sárga kiemelést és a tooltipeket."""
        color = Qt.yellow if highlight else Qt.white
        tooltip = "Manuális kategória felülvizsgálat szükséges!" if highlight else ""
        
        palette = self.palette()
        palette.setColor(QPalette.Window, color)
        
        for combo in [self.main_category_combo, self.sub_category_combo, self.product_type_combo]:
            combo.setPalette(palette)
            combo.setToolTip(tooltip)