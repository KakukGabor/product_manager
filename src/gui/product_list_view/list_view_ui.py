# src/gui/product_list_view/list_view_ui.py
from PySide6.QtWidgets import (
    QTableWidget, QAbstractItemView, QVBoxLayout, QHeaderView
)
from PySide6.QtGui import QColor

DEFAULT_ROW_COLOR = QColor(220, 240, 255)

class ListViewUi:

    def setup_ui(self, parent_widget):
        
        main_layout = QVBoxLayout(parent_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        parent_widget.table_widget = QTableWidget(parent_widget)
        parent_widget.table_widget.setShowGrid(True)

        parent_widget.table_widget.setColumnCount(len(parent_widget.COLUMN_CONFIG))
        parent_widget.table_widget.setHorizontalHeaderLabels([col["header"] for col in parent_widget.COLUMN_CONFIG])

        for i, col_info in enumerate(parent_widget.COLUMN_CONFIG):
            parent_widget.table_widget.horizontalHeader().setSectionResizeMode(i, col_info["resize_mode"])
            parent_widget.table_widget.setColumnWidth(i, col_info["optimal_width"])

        parent_widget.table_widget.setSelectionBehavior(QAbstractItemView.SelectRows)
        parent_widget.table_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        parent_widget.table_widget.setEditTriggers(QAbstractItemView.NoEditTriggers)

        parent_widget.table_widget.setSortingEnabled(True)
        parent_widget.table_widget.horizontalHeader().setSortIndicatorShown(True)

        parent_widget.table_widget.setStyleSheet(f"""
            QTableWidget {{
                background-color: {DEFAULT_ROW_COLOR.name()};
                gridline-color: #c5d9e8; /* Finom kékes-szürke rácsvonal szín */
            }}

            QScrollBar:vertical {{
                background: #a4c7e0;
                width: 8px;          
            }}

            QScrollBar::handle:vertical:hover {{
                background: #7496ad;
            }}
        """)

        main_layout.addWidget(parent_widget.table_widget)