# gui/product_list_view/product_list_view.py
import logging
from typing import List, Optional, Dict
from PySide6.QtWidgets import (
    QTableWidgetItem, QAbstractItemView,
    QWidget, QHeaderView, QApplication, QMenu
)
from PySide6.QtGui import QResizeEvent, QFont, QFontMetrics, QPalette, QColor
from PySide6.QtCore import Qt, Signal, Slot, QTimer, QPoint

from models.product_model import Product
from managers.settings_manager import SettingsManager
from .list_view_ui import ListViewUi
from .product_table_adapter import ProductTableAdapter

logger = logging.getLogger(__name__)

class ProductListView(QWidget):
    productSelected = Signal(object)
    initialPopulationComplete = Signal()
    sortOrderChanged = Signal(int, Qt.SortOrder)

    COLUMN_CONFIG: List[Dict] = [
        {"header": "ID", "attr": "id", "optimal_width": 80, "resize_mode": QHeaderView.Interactive},
        {"header": "Név", "attr": "title", "optimal_width": 250, "resize_mode": QHeaderView.Interactive},
        {"header": "Ár", "attr": "price_numeric", "optimal_width": 100, "resize_mode": QHeaderView.Interactive},
        {"header": "Termék típus", "attr": "product_type", "optimal_width": 120, "min_visible_width": 10, "resize_mode": QHeaderView.Interactive},
        {"header": "MT", "attr": "gs_views", "optimal_width": 40, "min_visible_width": 10, "resize_mode": QHeaderView.Interactive},
        {"header": "MF", "attr": "gs_watchers", "optimal_width": 40, "min_visible_width": 10, "resize_mode": QHeaderView.Interactive},
        {"header": "Létrehozva", "attr": "created_at", "optimal_width": 160, "min_visible_width": 10, "resize_mode": QHeaderView.Interactive},
    ]

    DEFAULT_FONT_SIZE = 10; MIN_FONT_SIZE = 8; MAX_FONT_SIZE = 14; FONT_STEP = 1
    DEFAULT_ROW_PADDING = 8; MIN_ROW_PADDING = 4; MAX_ROW_PADDING = 20; ROW_PADDING_STEP = 2

    def __init__(self, settings_manager: SettingsManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.products: Dict[str, Product] = {}
        self._current_selected_product_id: Optional[str] = None
        self._last_selected_row = -1
        self._current_marking = "none"

        self._is_loading_images = False
        self._pending_selection_id: Optional[str] = None
        self._debounce_timer = QTimer(self); self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(250); self._debounce_timer.timeout.connect(self._process_debounced_selection)

        self._current_font_size = self.settings_manager.get_setting(
            "client_settings.list_view_font_size", self.DEFAULT_FONT_SIZE
        )
        self._current_row_padding = self.settings_manager.get_setting(
            "client_settings.list_view_row_padding", self.DEFAULT_ROW_PADDING
        )
        self._font = QFont("Segoe UI", self._current_font_size)

        self.ui = ListViewUi()
        self.ui.setup_ui(self)

        self.table_widget.setContextMenuPolicy(Qt.CustomContextMenu)        
        self.adapter = ProductTableAdapter(self.table_widget, self.COLUMN_CONFIG)
        
        self._connect_signals()
        
        # --- ITT VOLT A HIBA, MOST JAVÍTVA ---
        self.adapter.populate_table([], self._font, self._get_effective_row_height(), self._current_marking)

    def _log(self, level: int, message: str, *args, **kwargs):
        logger.log(level, f"[ProductListView] {message}", *args, **kwargs)

    def _connect_signals(self):
        self.table_widget.horizontalHeader().sectionClicked.connect(self._handle_header_clicked)
        self.table_widget.itemDoubleClicked.connect(self._handle_item_double_clicked)
        self.table_widget.itemSelectionChanged.connect(self._handle_item_selection_changed)
        self.table_widget.customContextMenuRequested.connect(self._show_context_menu)

    def _get_effective_row_height(self) -> int:
        return QFontMetrics(self._font).height() + self._current_row_padding

    def _find_row_by_product_id(self, product_id: str) -> int:
        """Megkeresi egy termék sor indexét az ID-ja alapján."""
        for row in range(self.table_widget.rowCount()):
            item = self.table_widget.item(row, 0)
            if item and item.data(Qt.UserRole) == product_id:
                return row
        return -1

    def _apply_scaling_to_table(self):
        self._font.setPointSize(self._current_font_size)
        effective_row_height = self._get_effective_row_height()
        for row_idx in range(self.table_widget.rowCount()):
            self.table_widget.setRowHeight(row_idx, effective_row_height)
            for col_idx in range(self.table_widget.columnCount()):
                item = self.table_widget.item(row_idx, col_idx)
                if item: item.setFont(self._font)

    @Slot()
    def scale_up(self):
        font_changed = False
        if self._current_font_size < self.MAX_FONT_SIZE:
            self._current_font_size += self.FONT_STEP
            self.settings_manager.set_setting("client_settings.list_view_font_size", self._current_font_size)
            font_changed = True

        padding_changed = False
        if self._current_row_padding < self.MAX_ROW_PADDING:
            self._current_row_padding += self.ROW_PADDING_STEP
            self.settings_manager.set_setting("client_settings.list_view_row_padding", self._current_row_padding)
            padding_changed = True
        
        if font_changed or padding_changed:
            self._apply_scaling_to_table()

    @Slot()
    def scale_down(self):
        font_changed = False
        if self._current_font_size > self.MIN_FONT_SIZE:
            self._current_font_size -= self.FONT_STEP
            self.settings_manager.set_setting("client_settings.list_view_font_size", self._current_font_size)
            font_changed = True

        padding_changed = False
        if self._current_row_padding > self.MIN_ROW_PADDING:
            self._current_row_padding -= self.ROW_PADDING_STEP
            self.settings_manager.set_setting("client_settings.list_view_row_padding", self._current_row_padding)
            padding_changed = True

        if font_changed or padding_changed:
            self._apply_scaling_to_table()

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event); self._update_column_visibility()

    def _update_column_visibility(self):
        pass

    def select_product_by_id(self, product_id: Optional[str], force_scroll_to_top: bool = False):
        if product_id is None:
            if self._last_selected_row != -1:
                old_product_id = self.get_product_id_at_row(self._last_selected_row)
                if old_product_id and old_product_id in self.products:
                    self.adapter.apply_selection_style_to_row(self._last_selected_row, self.products[old_product_id], False, self._current_marking)
            self.table_widget.clearSelection()
            self._last_selected_row = -1
            self.productSelected.emit(None)
            return

        row_idx = self._find_row_by_product_id(product_id)
        product = self.products.get(product_id)

        if row_idx != -1 and product:
            self.table_widget.blockSignals(True)
            self.table_widget.selectRow(row_idx)
            
            if self._last_selected_row != -1:
                old_product_id = self.get_product_id_at_row(self._last_selected_row)
                if old_product_id and old_product_id in self.products:
                    self.adapter.apply_selection_style_to_row(self._last_selected_row, self.products[old_product_id], False, self._current_marking)
            
            self.adapter.apply_selection_style_to_row(row_idx, product, True, self._current_marking)
            self._last_selected_row = row_idx
            
            scroll_hint = QAbstractItemView.PositionAtTop if force_scroll_to_top else QAbstractItemView.EnsureVisible
            self.table_widget.scrollToItem(self.table_widget.item(row_idx, 0), scroll_hint)
            self.table_widget.blockSignals(False)

            if self._current_selected_product_id != product_id:
                self._current_selected_product_id = product_id
                self.productSelected.emit(product_id)
        else:
            self.table_widget.clearSelection()
            self.productSelected.emit(None)

    def get_selected_product_id(self) -> Optional[str]:
        selected_rows = self.table_widget.selectionModel().selectedRows()
        if selected_rows:
            item = self.table_widget.item(selected_rows[0].row(), 0)
            if item: return item.data(Qt.UserRole)
        return None
    
    def get_product_id_at_row(self, row_index: int) -> Optional[str]:
        if 0 <= row_index < self.table_widget.rowCount():
            item = self.table_widget.item(row_index, 0)
            if item:
                return item.data(Qt.UserRole)
        return None

    def _handle_item_double_clicked(self, item: QTableWidgetItem):
        product_id = item.data(Qt.UserRole)
        if product_id: self.productSelected.emit(product_id)

    @Slot(list, str, int, Qt.SortOrder)
    def set_products(self, products: List[Product], product_id_to_select: Optional[str] = None,
                     initial_sort_column: int = -1, initial_sort_order: Qt.SortOrder = Qt.AscendingOrder):
        self.table_widget.setSortingEnabled(False)
        self.table_widget.blockSignals(True)
        
        self.products = {p.id: p for p in products}
        self.adapter.populate_table(products, self._font, self._get_effective_row_height(), self._current_marking)
        
        self._last_selected_row = -1
        self._current_selected_product_id = None
        
        if initial_sort_column != -1: 
            self.table_widget.sortItems(initial_sort_column, initial_sort_order)
        
        self._update_column_visibility()

        self.table_widget.blockSignals(False)
        self.table_widget.setSortingEnabled(True)

        if self.table_widget.rowCount() > 0:
            if not product_id_to_select or product_id_to_select not in self.products:
                product_id_to_select = self.table_widget.item(0, 0).data(Qt.UserRole)
        else:
            product_id_to_select = None

        if product_id_to_select: 
            QTimer.singleShot(100, lambda: self.select_product_by_id(product_id_to_select, force_scroll_to_top=True))
        else: 
            self.productSelected.emit(None)
            
        self.initialPopulationComplete.emit()

    @Slot(Product, bool, str)
    def add_product(self, product: Product, success: bool, message: str):
        if not success: self._log(logging.ERROR, f"Hiba a termék listához adásakor: {message}"); return
        self.products[product.id] = product
        self.adapter.add_row(product, self._font, self._get_effective_row_height(), self._current_marking)
        self.table_widget.sortItems(self.table_widget.horizontalHeader().sortIndicatorSection(), self.table_widget.horizontalHeader().sortIndicatorOrder())

    @Slot(Product, bool, str)
    def update_product(self, product: Product, success: bool, message: str):
        if not success or product.id not in self.products: self._log(logging.ERROR, f"Hiba a termék frissítésekor: {message}"); return
        self.products[product.id] = product
        if not self.adapter.update_row(product, self._font, self._get_effective_row_height(), self._current_marking):
            self.set_products(list(self.products.values()), self._current_selected_product_id)

    @Slot(str, bool, str)
    def remove_product(self, product_id: str, success: bool, message: str):
        if not success or product_id not in self.products: self._log(logging.ERROR, f"Hiba a termék törlésekor: {message}"); return
        del self.products[product_id]
        self.adapter.remove_row(product_id)
        if self._current_selected_product_id == product_id:
            if self.table_widget.rowCount() > 0:
                self.select_product_by_id(self.table_widget.item(0, 0).data(Qt.UserRole), force_scroll_to_top=True)
            else:
                self.productSelected.emit(None)

    @Slot()
    def _handle_item_selection_changed(self):
        selected_rows = self.table_widget.selectionModel().selectedRows()
        
        new_selected_id = None
        new_selected_row = -1

        if selected_rows:
            new_selected_row = selected_rows[0].row()
            item = self.table_widget.item(new_selected_row, 0)
            if item:
                new_selected_id = item.data(Qt.UserRole)
        
        if new_selected_id == self._current_selected_product_id:
            return

        if self._last_selected_row != -1 and self._last_selected_row != new_selected_row:
            old_product_id = self.get_product_id_at_row(self._last_selected_row)
            if old_product_id and old_product_id in self.products:
                self.adapter.apply_selection_style_to_row(self._last_selected_row, self.products[old_product_id], False, self._current_marking)
        
        if new_selected_row != -1 and new_selected_id in self.products:
            self.adapter.apply_selection_style_to_row(new_selected_row, self.products[new_selected_id], True, self._current_marking)
            self._last_selected_row = new_selected_row
        else:
            self._last_selected_row = -1

        self._pending_selection_id = new_selected_id
        if not self._is_loading_images: 
            self._debounce_timer.start()

    @Slot()
    def _process_debounced_selection(self):
        if self._pending_selection_id:
            self.select_product_by_id(self._pending_selection_id, force_scroll_to_top=False)
            self._pending_selection_id = None

    @Slot(bool)
    def _set_image_loading_status(self, is_loading: bool):
        self._is_loading_images = is_loading
        if not is_loading and self._pending_selection_id:
            self._debounce_timer.start()

    @Slot(int)
    def _handle_header_clicked(self, logical_index: int):
        self.sortOrderChanged.emit(logical_index, self.table_widget.horizontalHeader().sortIndicatorOrder())

    @Slot(QPoint)
    def _show_context_menu(self, pos: QPoint):
        item = self.table_widget.itemAt(pos)
        if not item:
            return

        context_menu = QMenu(self)
        copy_action = context_menu.addAction("Másolás")
        
        copy_action.triggered.connect(lambda: self._copy_cell_to_clipboard(item))
        
        context_menu.exec(self.table_widget.mapToGlobal(pos))

    def _copy_cell_to_clipboard(self, item: QTableWidgetItem):
        clipboard = QApplication.clipboard()
        cell_text = item.text()
        clipboard.setText(cell_text)
        self._log(logging.INFO, f"A '{cell_text}' érték a vágólapra másolva.")

    @Slot(str)
    def reapply_styles(self, marking: str):
        """Újraalkalmazza a sorok stílusát a megváltozott jelölés alapján."""
        self._current_marking = marking
        self.adapter.reapply_styles_for_all_rows(
            self.products, 
            self._current_marking, 
            self._current_selected_product_id
        )