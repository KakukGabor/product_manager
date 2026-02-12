# two_state_button.py
import logging
from typing import Optional

from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QIcon, QColor, QPixmap, QPainter
from PySide6.QtCore import QSize, Slot, Signal

from gui.toolbar_widget.toolbar_item import ToolbarItem

logger = logging.getLogger(__name__)

class TwoStateButton(ToolbarItem):
    """
    Egy kétállapotú nyomógomb típusú ToolbarItem, amely on/off ikonokkal rendelkezik.
    Kattintásra az ikon váltakozik.
    """
    stateChanged = Signal(str, bool)

    def __init__(self, item_id: str, icon_off_path: str, icon_on_path: str, tooltip: str = "", parent: Optional[QWidget] = None):
        super().__init__(item_id, slot_occupancy=1, tooltip=tooltip, parent=parent)
        self._icon_off_path = icon_off_path
        self._icon_on_path = icon_on_path
        self._is_on: bool = False

        self._update_visuals()

    @Slot()
    def _handle_internal_button_clicked(self):
        """
        Kezeli a belső gomb kattintását.
        Váltja a gomb 'on/off' állapotát és továbbítja a jelet.
        """
        # Csak akkor váltunk állapotot, ha nem drag műveletről van szó (ami a mouseReleaseEvent előtt elindulna)
        if not self._dragging:
            self._is_on = not self._is_on
            self._update_visuals()
            logger.debug(f"TwoStateButton '{self.item_id}' állapota váltva: {'BE' if self._is_on else 'KI'}")
            self.itemClicked.emit(self.item_id)
            self.stateChanged.emit(self.item_id, self._is_on)

    def set_on_state(self, is_on: bool):
        """
        Kívülről beállítja a gomb 'on' állapotát anélkül, hogy kattintási eseményt váltana ki.
        """
        if self._is_on != is_on:
            self._is_on = is_on
            self._update_visuals()

    def set_on_state_and_enabled(self, is_on_for_icon: bool, is_enabled_for_click: bool):
        """
        Beállítja a gomb "be/ki" vizuális állapotát (ikon) és engedélyezettségét (kattinthatóság).
        `is_on_for_icon`: Meghatározza a gomb ikonjának állapotát (pl. zöld/szürke a böngészőhöz).
                          Ez az `_is_on` belső attribútumot állítja be.
        `is_enabled_for_click`: Ha True, a gomb kattintható. Ha False, le van tiltva.
        """
        self._is_on = is_on_for_icon # A külső logika felülírhatja a belső on/off állapotot
        self.setEnabled(is_enabled_for_click) # Ezt a ToolbarItem.setEnabled() metódusa kezeli, ami hívja az _update_visuals()-t
        # A self.setEnabled() hívás már frissíti a vizuális állapotot, de ha csak _is_on változott és enable állapot maradt,
        # akkor direktben is hívni kell.
        self._update_visuals()

    def _update_visuals(self):
        """
        Frissíti a gomb ikonját az aktuális _is_on állapot és engedélyezettség alapján.
        """
        target_icon_path = self._icon_on_path if self._is_on else self._icon_off_path
        icon = self._get_icon_from_ref(self, target_icon_path, self._item_size * 0.8)

        # Letiltott állapot vizuális effekte (szürkézés).
        if not self.isEnabled() and not icon.isNull():
            pixmap = icon.pixmap(self._internal_button.iconSize())
            painter = QPainter(pixmap)
            painter.setCompositionMode(QPainter.CompositionMode_SourceAtop)
            painter.fillRect(pixmap.rect(), QColor(128, 128, 128, 128))
            painter.end()
            icon = QIcon(pixmap)

        self._internal_button.setIcon(icon)
