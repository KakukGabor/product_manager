# gui/toolbar_widget/toolbar_widget.py
import logging
import math
from typing import Optional, Any

from PySide6.QtWidgets import (
    QWidget, QSizePolicy
)
from PySide6.QtGui import (
    QPainter, QColor,
    QDropEvent, QDragEnterEvent, QDragMoveEvent, QPen,
    QPaintEvent, QDragLeaveEvent, QResizeEvent
)
from PySide6.QtCore import (
    Qt, QPoint, Signal, Slot, QSize, QRect, QTimer
)

from managers.settings_manager import SettingsManager
from .toolbar_item import ToolbarItem
from .simple_push_button import SimplePushButton
from .two_state_button import TwoStateButton

logger = logging.getLogger(__name__)

class ToolbarWidget(QWidget):
    buttonOrderChanged = Signal(list)
    buttonClicked = Signal(str)

    def __init__(self, settings_manager: SettingsManager, item_configs: list[dict[str, Any]],
                 orientation: Qt.Orientation = Qt.Horizontal, settings_key: str = "toolbar_button_order",
                 state_settings_key: Optional[str] = None, parent: Optional[QWidget] = None, item_size: QSize = QSize(40, 40)):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self._item_configs_pool = item_configs
        self._orientation = orientation
        self._settings_key = settings_key
        self._state_settings_key = state_settings_key

        self._item_size = item_size
        self._item_spacing = 5
        self._margins = {"left": 5, "top": 5, "right": 5, "bottom": 5}

        self._toolbar_items: dict[str, ToolbarItem] = {}
        self._item_ids_order: list[str | None] = []

        self.setAcceptDrops(True)
        self.setMouseTracking(True)

        if self._orientation == Qt.Horizontal:
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        else:
            self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        self._target_slot_index = -1

        self._toolbar_bg_color = QColor(230, 240, 250)
        self._toolbar_border_bottom_color = QColor(190, 210, 230)
        self._highlight_slot_color = QColor(100, 150, 200, 120)
        self._slot_border_color = QColor(170, 190, 210, 180)
        self._button_bg_color = QColor(Qt.transparent)
        self._button_hover_color = QColor(255, 255, 255, 40) 
        self._button_pressed_color = QColor(0, 0, 0, 40)

        self._show_grid_setting = True
        self._force_show_grid = False

        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._reposition_items)

        self._create_toolbar_items_from_config()
        self._load_item_order()
        self._reposition_items() # Hozzáadva, hogy induláskor is elrendezze

    def sizeHint(self) -> QSize:
        if self._orientation == Qt.Horizontal:
            height = self._item_size.height() + self._margins["top"] + self._margins["bottom"]
            return QSize(super().sizeHint().width(), height)
        else:
            width = self._item_size.width() + self._margins["left"] + self._margins["right"]
            return QSize(width, super().sizeHint().height())

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    @Slot(str, bool)
    def set_button_on_state(self, item_id: str, is_on: bool):
        item = self._toolbar_items.get(item_id)
        if isinstance(item, TwoStateButton):
            item.set_on_state(is_on)

    @Slot(str, bool, bool)
    def set_item_state(self, item_id: str, is_active_feature: bool, is_action_enabled: bool):
        item = self._toolbar_items.get(item_id)
        if item:
            if isinstance(item, TwoStateButton):
                item.set_on_state_and_enabled(is_on_for_icon=is_active_feature, is_enabled_for_click=is_action_enabled)
            else:
                item.setEnabled(is_action_enabled)

    @Slot(QColor)
    def set_toolbar_background_color(self, color: QColor):
        if self._toolbar_bg_color != color: self._toolbar_bg_color = color; self.update()

    @Slot(QColor)
    def set_toolbar_bottom_border_color(self, color: QColor):
        if self._toolbar_border_bottom_color != color: self._toolbar_border_bottom_color = color; self.update()

    @Slot(QColor)
    def set_highlighted_slot_color(self, color: QColor):
        if self._highlight_slot_color != color: self._highlight_slot_color = color; self.update()

    @Slot(QColor)
    def set_slot_border_color(self, color: QColor):
        if self._slot_border_color != color: self._slot_border_color = color; self.update()

    @Slot(bool)
    def set_grid_visibility(self, show: bool):
        if self._show_grid_setting != show: self._show_grid_setting = show; self.update()
    
    # --- JAVÍTÁS: A HIÁNYZÓ METÓDUS HOZZÁADÁSA ---
    def get_item_by_id(self, item_id: str) -> Optional[ToolbarItem]:
        """
        Visszaadja a ToolbarItem példányt a megadott azonosító alapján.
        """
        return self._toolbar_items.get(item_id)
    # --- JAVÍTÁS VÉGE ---

    def _create_toolbar_items_from_config(self):
        for config in self._item_configs_pool:
            item_id = config.get("id")
            item_type = config.get("type", "simple_push")
            tooltip = config.get("tooltip", item_id)
            if not item_id: continue
            item: Optional[ToolbarItem] = None
            if item_type == "simple_push":
                item = SimplePushButton(item_id, icon_path=config.get("icon_path"), tooltip=tooltip, parent=self)
            elif item_type == "two_state":
                item = TwoStateButton(item_id, icon_off_path=config.get("icon_off_path"), icon_on_path=config.get("icon_on_path"), tooltip=tooltip, parent=self)
                if self._state_settings_key:
                    item.stateChanged.connect(self._handle_item_state_changed)
                    all_states = self.settings_manager.get_setting(self._state_settings_key, {})
                    initial_state = all_states.get(item_id, False)
                    item.set_on_state(initial_state)

            if item:
                item.set_item_size(self._item_size)
                item.itemClicked.connect(self.buttonClicked.emit)
                item.itemDragStarted.connect(self._handle_item_drag_started)
                item.apply_stylesheet(self._button_bg_color, self._button_hover_color, self._button_pressed_color)
                self._toolbar_items[item_id] = item
                item.hide()

    @Slot(str, bool)
    def _handle_item_state_changed(self, item_id: str, is_on: bool):
        if not self._state_settings_key:
            return
        all_states = self.settings_manager.get_setting(self._state_settings_key, {})
        all_states[item_id] = is_on
        self.settings_manager.set_setting(self._state_settings_key, all_states)
        logger.debug(f"Gomb állapot mentve: '{item_id}': {is_on} a '{self._state_settings_key}' kulcs alá.")

    @Slot(QColor, QColor, QColor)
    def set_button_background_color(self, color: QColor, hover_color: Optional[QColor] = None, pressed_color: Optional[QColor] = None):
        """
        Beállítja az eszköztár gombjainak háttérszínét.
        Ha a hover és pressed színek nincsenek megadva, automatikusan generálja őket.
        """
        self._button_bg_color = color
        
        # Ha nincs megadva hover szín, generálunk egy világosabbat
        self._button_hover_color = hover_color if hover_color else color.lighter(115)
        
        # Ha nincs megadva pressed szín, generálunk egy sötétebbet
        self._button_pressed_color = pressed_color if pressed_color else color.darker(115)

        # Alkalmazzuk a stílust az összes létező gombra
        for item in self._toolbar_items.values():
            item.apply_stylesheet(self._button_bg_color, self._button_hover_color, self._button_pressed_color)

    def _handle_item_drag_started(self, item_id: str):
        self._force_show_grid = True; self.update()

    def _load_item_order(self):
        default_ids = [c["id"] for c in self._item_configs_pool if "id" in c]
        loaded_order = self.settings_manager.get_setting(self._settings_key, default_ids)
        cleaned_order = [i for i in loaded_order if i is None or i in self._toolbar_items]
        if not any(i is not None for i in cleaned_order): cleaned_order = default_ids
        self._item_ids_order = cleaned_order

    def _save_item_order(self):
        trimmed_order = list(self._item_ids_order)
        while trimmed_order and trimmed_order[-1] is None:
            trimmed_order.pop()
        self.settings_manager.set_setting(self._settings_key, trimmed_order)

    def _get_max_visible_slot_count(self) -> int:
        if self._orientation == Qt.Horizontal:
            available = self.width() - self._margins["left"] - self._margins["right"]
            item_len = self._item_size.width()
        else:
            available = self.height() - self._margins["top"] - self._margins["bottom"]
            item_len = self._item_size.height()
        if available < item_len: return 0
        effective_size = item_len + self._item_spacing
        if effective_size <= 0: return 999
        return math.floor((available + self._item_spacing) / effective_size)

    def _reposition_items(self):
        for item in self._toolbar_items.values(): item.hide()
        max_slots = self._get_max_visible_slot_count()
        
        while len(self._item_ids_order) < max_slots:
            self._item_ids_order.append(None)
        
        for i in range(min(len(self._item_ids_order), max_slots)):
            item_id = self._item_ids_order[i]
            if item_id and item_id in self._toolbar_items:
                self._toolbar_items[item_id].setGeometry(self._get_slot_rect(i))
                self._toolbar_items[item_id].show()
        self.update()

    def _get_slot_rect(self, slot_index: int) -> QRect:
        w, h = self._item_size.width(), self._item_size.height()
        if self._orientation == Qt.Horizontal:
            x = self._margins["left"] + slot_index * (w + self._item_spacing)
            # A gombot a felső margónál kezdjük, így a sizeHint miatt automatikusan középre kerül
            y = self._margins["top"]
        else:
            x = self._margins["left"]
            y = self._margins["top"] + slot_index * (h + self._item_spacing)
        return QRect(x, y, w, h)

    def _update_target_slot(self, mouse_pos: QPoint):
        max_slots = self._get_max_visible_slot_count()
        new_target = -1

        for i in range(max_slots):
            if self._get_slot_rect(i).contains(mouse_pos):
                new_target = i
                break
        
        if new_target != self._target_slot_index:
            self._target_slot_index = new_target
            self.update()

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        self._resize_timer.start(10)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasText() and event.mimeData().text() in self._toolbar_items:
            self._force_show_grid = True; self.update(); event.acceptProposedAction()
        else: event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent):
        if event.mimeData().hasText() and event.mimeData().text() in self._toolbar_items:
            self._update_target_slot(event.pos()); event.acceptProposedAction()
        else: event.ignore()

    def dropEvent(self, event: QDropEvent):
        try:
            dragged_id = event.mimeData().text()
            try:
                original_index = self._item_ids_order.index(dragged_id)
            except ValueError: return 

            target_index = self._target_slot_index

            if target_index == -1: return
            if target_index == original_index: return

            max_slots = self._get_max_visible_slot_count()
            while len(self._item_ids_order) < max_slots:
                self._item_ids_order.append(None)
            
            self._item_ids_order.pop(original_index)
            self._item_ids_order.insert(target_index, dragged_id)

            self._reposition_items()
            self._save_item_order()
            self.buttonOrderChanged.emit(self._item_ids_order)
            event.acceptProposedAction()

        finally:
            self._target_slot_index = -1
            self._force_show_grid = False
            self.update()

    def dragLeaveEvent(self, event: QDragLeaveEvent):
        self._target_slot_index = -1
        self._force_show_grid = False
        self.update()
        super().dragLeaveEvent(event)

    def paintEvent(self, event: QPaintEvent):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), self._toolbar_bg_color)
        painter.setPen(QPen(self._toolbar_border_bottom_color, 1, Qt.SolidLine))
        if self._orientation == Qt.Horizontal:
            painter.drawLine(0, self.height() - 1, self.width(), self.height() - 1)
        else:
            painter.drawLine(self.width() - 1, 0, self.width() - 1, self.height())
        if self._show_grid_setting or self._force_show_grid:
            max_slots = self._get_max_visible_slot_count()
            for i in range(max_slots):
                rect = self._get_slot_rect(i)
                if i == self._target_slot_index: painter.fillRect(rect, self._highlight_slot_color)
                painter.setPen(QPen(self._slot_border_color, 1, Qt.DotLine)); painter.drawRect(rect)
        painter.end()