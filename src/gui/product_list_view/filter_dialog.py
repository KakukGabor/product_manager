import logging
from typing import Dict, Any, Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QMessageBox, QWidget, QAbstractSpinBox, QCheckBox
)
from PySide6.QtCore import Qt, Signal, Slot

from models.product_model import MainCategory, _sanitize_for_slug
from managers.product_category_manager import ProductCategoryManager
from gui.formatted_double_spinbox import FormattedDoubleSpinBox
from utils.formatters import format_numeric_input

logger = logging.getLogger(__name__)

DIALOG_STYLESHEET = """
    #filterDialog {
        background-color: #F0F8FF;
        border: 1px solid #4682B4;
    }
    #headerLabel {
        background-color: #4682B4;
        color: white;
        font-size: 11pt;
        font-weight: bold;
        padding: 8px;
    }
    #formContainer QLabel {
        font-size: 10pt;
        font-weight: bold;
        color: #333;
    }
    QLineEdit, QComboBox, FormattedDoubleSpinBox {
        font-size: 10pt;
        padding: 5px;
        border: 1px solid #B0C4DE;
        border-radius: 4px;
        min-width: 150px;
    }
    #buttonContainer {
        background-color: #A0C4FF;
        border-top: 1px solid #8FAADC;
    }
    QPushButton {
        padding: 8px 20px;
        border: 1px solid #777;
        border-radius: 4px;
        font-size: 10pt;
        background-color: #F0F0F0;
    }
    QPushButton:hover {
        background-color: #E0E0E0;
    }
    #applyButton {
        font-weight: bold;
        background-color: #007bff;
        color: white;
        border-color: #1e7e34;
    }
    #applyButton:hover {
        background-color: #218838;
    }
"""

class FilterDialog(QDialog):
    applyFilters = Signal(dict)
    clearFilters = Signal()

    def __init__(self, category_manager: ProductCategoryManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.category_manager = category_manager
        self.setWindowTitle("Szűrő feltételek")
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setFixedSize(750, 320)
        self.setObjectName("filterDialog")
        self.setStyleSheet(DIALOG_STYLESHEET)
        
        self._setup_ui()
        self._connect_signals()
        self._populate_main_categories()

    def _log(self, level: int, message: str, *args, **kwargs):
        logger.log(level, f"[FilterDialog] {message}", *args, **kwargs)

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        header_label = QLabel("Szűrő feltételek")
        header_label.setObjectName("headerLabel")
        main_layout.addWidget(header_label)

        form_container = QWidget()
        form_container.setObjectName("formContainer")
        
        grid_layout = QGridLayout(form_container)
        grid_layout.setContentsMargins(15, 15, 15, 15)
        grid_layout.setHorizontalSpacing(10)
        grid_layout.setVerticalSpacing(12)

        id_label = QLabel("Azonosító (ID):")
        price_label = QLabel("Ár tartomány:")
        cat_label = QLabel("Kategória:")
        gs_label = QLabel("GS Függőség:")

        self.id_filter_edit = QLineEdit()
        self.id_filter_edit.setPlaceholderText("Részleges vagy teljes ID egyezés")
        
        price_sub_layout = QHBoxLayout()
        self.price_min_filter_spinbox = FormattedDoubleSpinBox()
        self.price_min_filter_spinbox.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.price_min_filter_spinbox.setDecimals(0)
        self.price_min_filter_spinbox.setRange(0.0, 999999999.0)
        
        self.price_max_filter_spinbox = FormattedDoubleSpinBox()
        self.price_max_filter_spinbox.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.price_max_filter_spinbox.setDecimals(0)
        self.price_max_filter_spinbox.setRange(0.0, 999999999.0)

        price_sub_layout.addWidget(self.price_min_filter_spinbox, 1)
        price_sub_layout.addWidget(QLabel("-"), 0)
        price_sub_layout.addWidget(self.price_max_filter_spinbox, 1)

        category_sub_layout = QHBoxLayout()
        self.main_category_filter_combo = QComboBox()
        self.sub_category_filter_combo = QComboBox()
        self.product_type_filter_combo = QComboBox()
        category_sub_layout.addWidget(self.main_category_filter_combo)
        category_sub_layout.addWidget(self.sub_category_filter_combo)
        category_sub_layout.addWidget(self.product_type_filter_combo)

        self.gs_dependency_filter_combo = QComboBox()
        self.gs_dependency_filter_combo.addItem("Minden termék", None)
        self.gs_dependency_filter_combo.addItem("Csak GS függő", True)
        self.gs_dependency_filter_combo.addItem("Csak GS független", False)

        grid_layout.addWidget(id_label, 0, 0)
        grid_layout.addWidget(self.id_filter_edit, 0, 1)
        grid_layout.addWidget(price_label, 1, 0)
        grid_layout.addLayout(price_sub_layout, 1, 1)
        grid_layout.addWidget(cat_label, 2, 0)
        grid_layout.addLayout(category_sub_layout, 2, 1)
        grid_layout.addWidget(gs_label, 3, 0)
        grid_layout.addWidget(self.gs_dependency_filter_combo, 3, 1)
        
        self.sold_products_checkbox = QCheckBox("Eladott termékek listázása")
        self.sold_products_checkbox.setStyleSheet("font-weight: bold; color: #A52A2A;")
        grid_layout.addWidget(self.sold_products_checkbox, 4, 0, 1, 2)

        grid_layout.setColumnStretch(0, 0)
        grid_layout.setColumnStretch(1, 1)
       
        main_layout.addWidget(form_container)
        main_layout.addStretch(1)

        button_container = QWidget()
        button_container.setObjectName("buttonContainer")
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(15, 8, 15, 8)
        self.apply_button = QPushButton("Szűrés alkalmazása")
        self.apply_button.setObjectName("applyButton")
        self.clear_button = QPushButton("Szűrők törlése")
        self.cancel_button = QPushButton("Mégse")
        button_layout.addWidget(self.apply_button)
        button_layout.addStretch(1)
        button_layout.addWidget(self.clear_button)
        button_layout.addWidget(self.cancel_button)
        main_layout.addWidget(button_container)

    def _connect_signals(self):
        self.price_min_filter_spinbox.lineEdit().textChanged.connect(lambda: format_numeric_input(self.price_min_filter_spinbox.lineEdit()))
        self.price_max_filter_spinbox.lineEdit().textChanged.connect(lambda: format_numeric_input(self.price_max_filter_spinbox.lineEdit()))
        self.main_category_filter_combo.currentIndexChanged.connect(self._on_main_category_changed)
        self.sub_category_filter_combo.currentIndexChanged.connect(self._on_sub_category_changed)
        self.apply_button.clicked.connect(self._emit_apply_filters)
        self.apply_button.setAutoDefault(False)
        self.cancel_button.clicked.connect(self.reject)
        self.cancel_button.setAutoDefault(False)
        self.clear_button.clicked.connect(self._handle_clear_and_close)
        self.clear_button.setAutoDefault(False)
        self.sold_products_checkbox.toggled.connect(self._on_sold_checkbox_toggled)

    def _populate_main_categories(self):
        self.main_category_filter_combo.blockSignals(True)
        self.main_category_filter_combo.clear()
        self.main_category_filter_combo.addItem("Minden főkategória", "")
        for cat_enum in self.category_manager.get_main_categories():
            self.main_category_filter_combo.addItem(cat_enum.display_name, cat_enum.to_slug())
        self.main_category_filter_combo.blockSignals(False)
        self._on_main_category_changed()

    def _on_main_category_changed(self):
        self.sub_category_filter_combo.blockSignals(True)
        self.sub_category_filter_combo.clear()
        self.sub_category_filter_combo.addItem("Minden alkategória", "")
        selected_main_cat_slug = self.main_category_filter_combo.currentData()
        if selected_main_cat_slug:
            try:
                main_cat_enum = MainCategory(self.main_category_filter_combo.currentText())
                sub_categories = self.category_manager.get_sub_categories_for_main(main_cat_enum)
                for sub_cat_name in sorted(sub_categories):
                    self.sub_category_filter_combo.addItem(sub_cat_name, _sanitize_for_slug(sub_cat_name))
            except ValueError:
                self._log(logging.WARNING, "Érvénytelen főkategória a szűrőben.")
        self.sub_category_filter_combo.blockSignals(False)
        self._on_sub_category_changed()

    def _on_sub_category_changed(self):
        self.product_type_filter_combo.blockSignals(True)
        self.product_type_filter_combo.clear()
        self.product_type_filter_combo.addItem("Minden terméktípus", "")
        main_cat_slug = self.main_category_filter_combo.currentData()
        sub_cat_slug = self.sub_category_filter_combo.currentData()
        if main_cat_slug and sub_cat_slug:
            try:
                main_cat_enum = MainCategory(self.main_category_filter_combo.currentText())
                sub_cat_name = self.sub_category_filter_combo.currentText()
                product_types = self.category_manager.get_product_types_for_sub(main_cat_enum, sub_cat_name)
                for prod_type_name in sorted(product_types):
                    self.product_type_filter_combo.addItem(prod_type_name, _sanitize_for_slug(prod_type_name))
            except ValueError:
                 self._log(logging.WARNING, "Érvénytelen kategória a terméktípusok lekérdezésekor.")
        self.product_type_filter_combo.blockSignals(False)

    def set_current_filters(self, filters: Dict[str, Any]):
        self.id_filter_edit.setText(filters.get("id", ""))
        self.price_min_filter_spinbox.setValue(filters.get("price_min", 0.0))
        self.price_max_filter_spinbox.setValue(filters.get("price_max", 0.0))
        self.blockSignals(True)
        main_slug = filters.get("main_category_slug", "")
        index = self.main_category_filter_combo.findData(main_slug)
        self.main_category_filter_combo.setCurrentIndex(index if index >= 0 else 0)
        self._on_main_category_changed()
        sub_slug = filters.get("sub_category_slug", "")
        index = self.sub_category_filter_combo.findData(sub_slug)
        self.sub_category_filter_combo.setCurrentIndex(index if index >= 0 else 0)
        self._on_sub_category_changed()
        prod_type_slug = filters.get("product_type_slug", "")
        index = self.product_type_filter_combo.findData(prod_type_slug)
        self.product_type_filter_combo.setCurrentIndex(index if index >= 0 else 0)
        self.blockSignals(False)
        gs_dependency_value = filters.get("is_gs_dependent", None)
        index_gs = self.gs_dependency_filter_combo.findData(gs_dependency_value)
        self.gs_dependency_filter_combo.setCurrentIndex(index_gs if index_gs >= 0 else 0)
        show_sold = filters.get("is_sold", False)
        self.sold_products_checkbox.setChecked(show_sold)
        self._on_sold_checkbox_toggled(show_sold)

    @Slot()
    def _emit_apply_filters(self):
        filters = {}

        if self.sold_products_checkbox.isChecked():
            filters["is_sold"] = True
        else:            
            id_text = self.id_filter_edit.text().strip()
            if id_text:
                filters["id"] = id_text
            
            price_min = self.price_min_filter_spinbox.value()
            if price_min > 0.0:
                filters["price_min"] = price_min
            
            price_max = self.price_max_filter_spinbox.value()
            if price_max > 0.0:
                if price_max < price_min and price_min > 0.0:
                    QMessageBox.warning(self, "Hiba", "A maximális árnak nagyobbnak kell lennie, mint a minimális ár.")
                    return
                filters["price_max"] = price_max

            main_cat_slug = self.main_category_filter_combo.currentData()
            if main_cat_slug:
                filters["main_category_slug"] = main_cat_slug
            
            sub_cat_slug = self.sub_category_filter_combo.currentData()
            if sub_cat_slug:
                filters["sub_category_slug"] = sub_cat_slug
            
            prod_type_slug = self.product_type_filter_combo.currentData()
            if prod_type_slug:
                filters["product_type_slug"] = prod_type_slug
            
            gs_dependency_value = self.gs_dependency_filter_combo.currentData()
            if gs_dependency_value is not None:
                filters["is_gs_dependent"] = gs_dependency_value

        if not filters:
            self.clearFilters.emit()
        else:
            self.applyFilters.emit(filters)
        
        self.accept()

    @Slot()
    def _handle_clear_and_close(self):   
        self.clearFilters.emit()
        self.accept()

    @Slot()
    def _reset_ui_fields(self, clear_sold_checkbox: bool = True):
        self.id_filter_edit.clear()
        self.price_min_filter_spinbox.setValue(0.0)
        self.price_max_filter_spinbox.setValue(0.0)
        self.main_category_filter_combo.setCurrentIndex(0)
        self.gs_dependency_filter_combo.setCurrentIndex(0)
        if clear_sold_checkbox:
            self.sold_products_checkbox.setChecked(False)

    @Slot(bool)
    def _on_sold_checkbox_toggled(self, checked: bool):
        widgets_to_toggle = [
            self.id_filter_edit, self.price_min_filter_spinbox, self.price_max_filter_spinbox,
            self.main_category_filter_combo, self.sub_category_filter_combo,
            self.product_type_filter_combo, self.gs_dependency_filter_combo
        ]
        for widget in widgets_to_toggle:
            widget.setEnabled(not checked)

        if checked:
            self._reset_ui_fields(clear_sold_checkbox=False)