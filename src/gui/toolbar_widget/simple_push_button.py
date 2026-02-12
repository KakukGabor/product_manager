# simple_push_button.py
import logging
from typing import Optional

from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QIcon, QColor, QPixmap, QPainter
from PySide6.QtCore import QSize

from gui.toolbar_widget.toolbar_item import ToolbarItem

logger = logging.getLogger(__name__)

class SimplePushButton(ToolbarItem):
    """
    Egy egyszerű nyomógomb típusú ToolbarItem, amely egyetlen ikont jelenít meg.
    """
    def __init__(self, item_id: str, icon_path: str, tooltip: str = "", parent: Optional[QWidget] = None):
        super().__init__(item_id, slot_occupancy=1, tooltip=tooltip, parent=parent)
        self.icon_path = icon_path
        self._update_visuals()

    def _update_visuals(self):
        """
        Frissíti a gomb ikonját az aktuális beállítások alapján.
        A letiltott állapot vizuális effekttel (szürkézés) jár.
        """
        icon = self._get_icon_from_ref(self, self.icon_path, self._item_size * 0.8) # Használjuk a ToolbarItem statikus metódusát

        # Letiltott állapot vizuális effekte (szürkézés).
        if not self.isEnabled() and not icon.isNull():
            pixmap = icon.pixmap(self._internal_button.iconSize())
            painter = QPainter(pixmap)
            painter.setCompositionMode(QPainter.CompositionMode_SourceAtop)
            painter.fillRect(pixmap.rect(), QColor(128, 128, 128, 128))
            painter.end()
            icon = QIcon(pixmap)

        self._internal_button.setIcon(icon)