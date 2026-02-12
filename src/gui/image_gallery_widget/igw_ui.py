# src/gui/image_gallery_widget/igw_ui.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QScrollArea, QLabel
)
from PySide6.QtCore import Qt

from .igw_style import IMAGE_GALLERY_STYLESHEET

class ImageGalleryUi:
    """
    Ez az osztály felelős az ImageGalleryWidget felhasználói felületének
    létrehozásáért és elrendezéséért.
    """
    def setup_ui(self, parent_widget: QWidget):
        # A fő widget stílusának beállítása a külön fájlból
        parent_widget.setStyleSheet(IMAGE_GALLERY_STYLESHEET)
        parent_widget.setObjectName("imageGalleryWidget")

        main_layout = QVBoxLayout(parent_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        main_layout.setAlignment(Qt.AlignTop)

        parent_widget.toggle_expand_button = QPushButton()
        parent_widget.toggle_expand_button.setObjectName("toggleExpandButton")
        parent_widget.toggle_expand_button.setFlat(False)
        parent_widget.toggle_expand_button.setFixedHeight(18)
        main_layout.addWidget(parent_widget.toggle_expand_button)

        parent_widget.scroll_area = QScrollArea(parent_widget)
        parent_widget.scroll_area.setWidgetResizable(True)
        parent_widget.scroll_area.setObjectName("imageGalleryScrollArea")

        scroll_content_widget = QWidget()
        scroll_content_widget.setObjectName("galleryScrollContent")
        scroll_content_widget.setAutoFillBackground(True)

        parent_widget.scroll_area.setWidget(scroll_content_widget)

        parent_widget.gallery_layout = QVBoxLayout(scroll_content_widget)
        parent_widget.gallery_layout.setContentsMargins(0, 0, 0, 0)
        parent_widget.gallery_layout.setSpacing(15)
        parent_widget.gallery_layout.setAlignment(Qt.AlignTop)

        # Címkék és layoutok létrehozása minden kategóriához
        for tag, header_text in parent_widget.IMAGE_TAGS.items():
            header_label = QLabel(header_text)
            header_label.setObjectName("imageCategoryHeader")
            header_label.setAlignment(Qt.AlignCenter)
            header_label.setVisible(False)
            parent_widget._header_labels[tag] = header_label
            parent_widget.gallery_layout.addWidget(header_label)

            category_v_layout = QVBoxLayout()
            category_v_layout.setSpacing(5)
            category_v_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

            parent_widget._image_layout_widgets[tag] = category_v_layout
            parent_widget.gallery_layout.addLayout(category_v_layout)

            parent_widget.gallery_layout.addSpacing(20)

        parent_widget.gallery_layout.addStretch(1)
        main_layout.addWidget(parent_widget.scroll_area)