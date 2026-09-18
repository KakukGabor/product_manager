# gui/product_list_view/product_table_adapter.py
import logging
from typing import List, Dict, Optional
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem
from PySide6.QtGui import QColor, QFont
from PySide6.QtCore import Qt

from models.product_model import Product, MainCategory
from .numeric_table_widget_item import NumericTableWidgetItem

logger = logging.getLogger(__name__)

DEFAULT_ROW_COLOR = QColor(220, 240, 255)
DELISTED_GS_COLOR = QColor(0,0,40)
NO_IMAGES_COLOR = QColor(100, 200, 237)
NO_CATEGORY_COLOR = QColor(255, 100, 100)
REVIEW_NEEDED_COLOR = QColor(255, 255, 102)
UPLOAD_NEEDED_COLOR = QColor(255, 165, 0)
# --- ÚJ SZÍNEK ---
FB_POSTED_COLOR = QColor(204, 255, 204) # Világoszöld
FB_AD_CREATED_COLOR = QColor(204, 229, 255) # Világoskék
JF_INACTIVE_COLOR = QColor(255, 228, 225)
JF_ARCHIVED_COLOR = QColor(255, 180, 180) # Pirosas a Jófogás archívumhoz

TEXT_COLOR_DARK_BACKGROUND = QColor(Qt.white)
TEXT_COLOR_LIGHT_BACKGROUND = QColor(Qt.black)


class ProductTableAdapter:
   
    def __init__(self, table_widget: QTableWidget, column_config: List[Dict]):
        self.table = table_widget
        self.column_config = column_config

    def populate_table(self, products: List[Product], font: QFont, row_height: int, marking: str):
        self.table.setRowCount(0)
        for product in products:
            self.add_row(product, font, row_height, marking)

    def add_row(self, product: Product, font: QFont, row_height: int, marking: str, row_idx: int = -1):
        if row_idx == -1:
            row_idx = self.table.rowCount()
            self.table.insertRow(row_idx)

        self._update_row_data(row_idx, product, font, marking)
        self.table.setRowHeight(row_idx, row_height)

    def update_row(self, product: Product, font: QFont, row_height: int, marking: str) -> bool:
        for row_idx in range(self.table.rowCount()):
            item_id = self.table.item(row_idx, 0)
            if item_id and item_id.data(Qt.UserRole) == product.id:
                self._update_row_data(row_idx, product, font, marking)
                self.table.setRowHeight(row_idx, row_height)
                return True
        return False

    def remove_row(self, product_id: str):
        for row_idx in range(self.table.rowCount()):
            item_id = self.table.item(row_idx, 0)
            if item_id and item_id.data(Qt.UserRole) == product_id:
                self.table.removeRow(row_idx)
                break

    def _update_row_data(self, row_idx: int, product: Product, font: QFont, marking: str):
        background_color, foreground_color, tooltip_text = self._get_row_style(product, marking)

        for col_index, col_info in enumerate(self.column_config):
            attr_name = col_info["attr"]
            item = self._create_item_for_attribute(product, attr_name)

            item.setBackground(background_color)
            item.setForeground(foreground_color)
            item.setToolTip(tooltip_text)
            item.setFont(font)
            self.table.setItem(row_idx, col_index, item)

    def _get_row_style(self, product: Product, marking: str) -> tuple[QColor, QColor, str]:
        
        background_color = DEFAULT_ROW_COLOR
        tooltip_text = "Rendben."
        is_marked = False

        # 0. A legmagasabb prioritású állapotok (eladva, törölve)
        if product.is_sold:
            background_color = QColor(Qt.darkGray)
            tooltip_text = "A termék eladva."
        elif product.is_delisted_on_gs:
            background_color = DELISTED_GS_COLOR
            tooltip_text = "FIGYELEM: Ez a GS-függő termék már nem található a Galéria Savaria weboldalon!"
        else:
            # 1. Jelölések ellenőrzése
            if marking == "posted_fb" and product.facebook_data.is_posted:
                background_color = FB_POSTED_COLOR
                tooltip_text = "Megjelölve: Facebook posztolva."
                is_marked = True
            elif marking == "ad_created_fb" and product.facebook_data.is_ad_created:
                background_color = FB_AD_CREATED_COLOR
                tooltip_text = "Megjelölve: Facebook hirdetés létrehozva."
                is_marked = True
            elif marking == "inactive_jf":
                # Ellenőrizzük, hogy a pozíció None vagy 0
                if product.jf_position is None or product.jf_position == 0:
                    if product.additional_attributes.get("jofogas", {}).get("is_archived", False):
                        background_color = JF_ARCHIVED_COLOR
                        tooltip_text = "Megjelölve: Jófogás ARCHÍVUMBAN (törlés alatt) lévő termék (újraposztolás nem lehetséges!)."
                    else:
                        background_color = JF_INACTIVE_COLOR
                        tooltip_text = "Megjelölve: Inaktív a Jófogáson (pozíció: 0 vagy nincs)."
                    is_marked = True

            # 2. Ha nincs jelölés, a normál állapotellenőrzés következik
            if not is_marked:
                if product.main_category == MainCategory.UNCATEGORIZED:
                    background_color = NO_CATEGORY_COLOR
                    tooltip_text = "HIBA: Nincs fő kategória beállítva!"
                elif product.num_mixed_images == 0:
                    background_color = NO_IMAGES_COLOR
                    tooltip_text = "Nincs kép feltöltve a termékhez!"
                elif product.needs_manual_category_review:
                    background_color = REVIEW_NEEDED_COLOR
                    tooltip_text = "Manuális kategória felülvizsgálat szükséges!"
                elif product.needs_upload:
                    background_color = UPLOAD_NEEDED_COLOR
                    tooltip_text = "Feltöltés szükséges a távoli szerverre!"
                elif product.is_in_sync_and_ready:
                    background_color = DEFAULT_ROW_COLOR
                    tooltip_text = "Rendben."

        # 3. Szövegszín dinamikus meghatározása
        if background_color.lightness() > 128:
            foreground_color = TEXT_COLOR_LIGHT_BACKGROUND
        else:
            foreground_color = TEXT_COLOR_DARK_BACKGROUND

        return background_color, foreground_color, tooltip_text

    def _create_item_for_attribute(self, product: Product, attr_name: str) -> QTableWidgetItem:
        if attr_name == "id":
            item = QTableWidgetItem(product.id)
            item.setData(Qt.UserRole, product.id)
            return item
        elif attr_name == "title":
            return QTableWidgetItem(product.title)
        elif attr_name == "price_numeric":
            if product.price_numeric is not None:
                text = f"{int(product.price_numeric):,} {product.currency}".replace(',', ' ')
                return NumericTableWidgetItem(text, product.price_numeric)
            else:
                return NumericTableWidgetItem(f"N/A {product.currency}", None)
        elif attr_name == "product_type":
            item = QTableWidgetItem(product.product_type or "Nincs")
            item.setTextAlignment(Qt.AlignCenter)
            return item
        elif attr_name == "gs_views":
            item = NumericTableWidgetItem(str(product.gs_views), product.gs_views)
            item.setTextAlignment(Qt.AlignCenter)
            return item
        elif attr_name == "gs_watchers":
            item = NumericTableWidgetItem(str(product.gs_watchers), product.gs_watchers)
            item.setTextAlignment(Qt.AlignCenter)
            return item
        elif attr_name == "created_at":
            if product.created_at:
                text = product.created_at.strftime("%Y.%m.%d %H:%M:%S")
                return NumericTableWidgetItem(text, product.created_at.timestamp())
            else:
                return NumericTableWidgetItem("N/A", None)
        else:
            return QTableWidgetItem("")
        
    def apply_selection_style_to_row(self, row_index: int, product: Product, is_selected: bool, marking: str):
        if not (0 <= row_index < self.table.rowCount()) or not product:
            return

        base_bg_color, base_fg_color, _ = self._get_row_style(product, marking)

        for col_index in range(self.table.columnCount()):
            item = self.table.item(row_index, col_index)
            if item:
                font = item.font()
                font.setBold(is_selected)
                item.setFont(font)

                if is_selected:
                    if base_bg_color.lightness() > 128:
                        item.setBackground(base_bg_color.darker(140))
                    else:
                        item.setBackground(base_bg_color.lighter(140))
                else:
                    item.setBackground(base_bg_color)
                    item.setForeground(base_fg_color)

    def reapply_styles_for_all_rows(self, products: Dict[str, Product], marking: str, selected_product_id: Optional[str]):
        """Újraalkalmazza az összes sor stílusát, figyelembe véve a jelölést és a kijelölést."""
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if not item: continue
            
            product_id = item.data(Qt.UserRole)
            product = products.get(product_id)
            if not product: continue
            
            is_selected = (product_id == selected_product_id)
            self.apply_selection_style_to_row(row, product, is_selected, marking)