# gui/main_window.py
import logging
import collections
import os
from datetime import datetime
from typing import Callable
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QMessageBox, QApplication,
                               QSplitter, QTextBrowser, QStackedWidget)

from PySide6.QtGui import QCloseEvent, QColor, QPixmap, QPainter, QPen
from PySide6.QtCore import Qt, Signal, Slot, QPoint, QSize, QRectF, QRect

from gui.toolbar_widget.toolbar_widget import ToolbarWidget
from gui.toolbar_widget.two_state_button import TwoStateButton
from gui.status_bar.status_bar_widget import StatusBarWidget
from managers.settings_manager import SettingsManager
from managers.resource_manager import ResourceManager
from controllers.main_controller import MainController
from gui.product_list_view.product_list_view import ProductListView
from gui.product_detail_widget.product_detail_widget import ProductDetailWidget
from gui.image_gallery_widget.image_gallery_widget import ImageGalleryWidget

logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    appShuttingDown = Signal()

    def __init__(self, settings_manager: SettingsManager, resource_manager: ResourceManager, main_controller: MainController,
                 product_list_view: ProductListView,
                 product_detail_widget: ProductDetailWidget,
                 image_gallery_widget: ImageGalleryWidget,
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle("Hirdetéskezelő")
        self.settings_manager = settings_manager
        self.main_controller = main_controller
        self._is_shutting_down = False

        self.product_list_view = product_list_view
        self.product_detail_widget = product_detail_widget
        self.image_gallery_widget = image_gallery_widget
        self._log_panel: QTextBrowser | None = None
        self._log_stacked_widget: QStackedWidget | None = None
        self._log_history = collections.deque(maxlen=500)

        # Ikonok létrehozása, mielőtt bármelyik toolbar használná őket
        self._ensure_toolbar_icons_exist(resource_manager.icon_base_path)

        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.setCentralWidget(central_widget)

        toolbar_configs = resource_manager.get_toolbar_config("main_horizontal")
        self.toolbar = ToolbarWidget(settings_manager, toolbar_configs, orientation=Qt.Horizontal, settings_key="main_toolbar_order", parent=self)
        self.toolbar.set_toolbar_background_color(QColor(105, 145, 225))
        self.toolbar.set_button_background_color(QColor("#9CC4E1"))
        self.toolbar.set_highlighted_slot_color(QColor(65, 105, 225, 120))

        left_panel_widget = QWidget()
        left_panel_layout = QVBoxLayout(left_panel_widget)
        left_panel_layout.setContentsMargins(0, 0, 0, 0)
        left_panel_layout.setSpacing(0)

        left_panel_layout.addWidget(self.product_list_view)
        
        list_toolbar_configs = resource_manager.get_toolbar_config("list_view_toolbar")
        self.list_toolbar = ToolbarWidget(
            settings_manager,
            list_toolbar_configs,
            orientation=Qt.Horizontal,
            settings_key="list_view_toolbar_order",
            item_size=QSize(25, 25),
            parent=self
        )
        self.list_toolbar.set_toolbar_background_color(QColor("#c2d2fe"))
        self.list_toolbar.set_button_background_color(QColor("#D6EAF8"))
        
        left_panel_layout.addWidget(self.list_toolbar)

        self._horizontal_content_splitter = QSplitter(Qt.Horizontal)
        self._horizontal_content_splitter.setHandleWidth(1)
        self._horizontal_content_splitter.addWidget(left_panel_widget)
        self._horizontal_content_splitter.addWidget(self.product_detail_widget)
        self._horizontal_content_splitter.addWidget(self.image_gallery_widget)
        
        saved_sizes = self.settings_manager.get_setting("client_settings.main_splitter_sizes", [300, 450, 250])
        self._horizontal_content_splitter.setSizes(saved_sizes)
        self._horizontal_content_splitter.splitterMoved.connect(self._save_splitter_state)

        self._setup_log_panel()

        self._vertical_main_splitter = QSplitter(Qt.Vertical)
        self._vertical_main_splitter.addWidget(self._horizontal_content_splitter)
        self._vertical_main_splitter.addWidget(self._log_stacked_widget)
        self._vertical_main_splitter.setSizes([1000, 0])
        self._vertical_main_splitter.setHandleWidth(1)
        self._vertical_main_splitter.setStyleSheet("QSplitter::handle { background-color: #3566c4; }")
        
        log_handle = self._vertical_main_splitter.handle(1)
        if log_handle:
            log_handle.setEnabled(False)

        self.status_bar = StatusBarWidget(resource_manager, self)

        main_layout.addWidget(self.toolbar)
        main_layout.addWidget(self._vertical_main_splitter)
        main_layout.addWidget(self.status_bar)

        self.toolbar.buttonClicked.connect(self._handle_toolbar_button_click)
        self.list_toolbar.buttonClicked.connect(self._handle_list_toolbar_click)
        self.main_controller.updateToolbarButtonState.connect(self.toolbar.set_item_state)
        self.main_controller.updateToolbarButtonState.connect(self.list_toolbar.set_item_state)
        self.main_controller.updateStatusBar.connect(self.status_bar.update_status)
        self.status_bar.logMessageFormatted.connect(self._add_message_to_log_history)
        self.status_bar.toggleClicked.connect(self._handle_log_toggle_click)
       
        splitter_stylesheet = """
            QSplitter {
            background-color: #8db9f7;
            }
            QSplitter::handle {
                background-color: #89b3c4;
            }
            QSplitter::handle:hover {
                background-color: #778899;
            }
            QSplitter::handle:pressed {
                background-color: #2F4F4F;
            }
            QSplitter::handle:horizontal {
                background-color: transparent; /* A háttér átlátszó */
                border-left: 1px dashed #ffffff;  /* Szaggatott bal szegély */
                border-right: 1px dashed #ffffff; /* Szaggatott jobb szegély */
                width: 5px; /* Adjunk neki egy kis szélességet, hogy a szaggatás látszódjon */
                margin: 1px 0;
            }
        """
        self._horizontal_content_splitter.setStyleSheet(splitter_stylesheet)
        self._vertical_main_splitter.setStyleSheet(splitter_stylesheet)
        
        self.showMaximized()

    def _ensure_toolbar_icons_exist(self, icons_dir: str):
        """Ellenőrzi a toolbar ikonjait, és létrehozza őket, ha hiányoznak."""
        
        # Szűrő ikon (tölcsér)
        filter_icon_path = os.path.join(icons_dir, "filter.png")
        if not os.path.exists(filter_icon_path):
            pixmap = QPixmap(32, 32); pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap); painter.setRenderHint(QPainter.Antialiasing); painter.setPen(QPen(Qt.black, 2))
            # --- JAVÍTÁS: A 'Qt.' prefixek eltávolítva ---
            points = [QPoint(4, 8), QPoint(28, 8), QPoint(18, 18), QPoint(18, 26), QPoint(14, 26), QPoint(14, 18)]
            # --- JAVÍTÁS VÉGE ---
            painter.drawPolygon(points)
            painter.end(); pixmap.save(filter_icon_path, "PNG")
            logger.info(f"Dummy 'filter.png' létrehozva: {filter_icon_path}")

        # Nagyítás ikon (+)
        zoom_in_icon_path = os.path.join(icons_dir, "zoom_in.png")
        if not os.path.exists(zoom_in_icon_path):
            pixmap = QPixmap(32, 32); pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap); painter.setRenderHint(QPainter.Antialiasing); painter.setPen(QPen(Qt.black, 3))
            painter.drawLine(16, 8, 16, 24); painter.drawLine(8, 16, 24, 16)
            painter.end(); pixmap.save(zoom_in_icon_path, "PNG")
            logger.info(f"Dummy 'zoom_in.png' létrehozva: {zoom_in_icon_path}")

        # Kicsinyítés ikon (-)
        zoom_out_icon_path = os.path.join(icons_dir, "zoom_out.png")
        if not os.path.exists(zoom_out_icon_path):
            pixmap = QPixmap(32, 32); pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap); painter.setRenderHint(QPainter.Antialiasing); painter.setPen(QPen(Qt.black, 3))
            painter.drawLine(8, 16, 24, 16)
            painter.end(); pixmap.save(zoom_out_icon_path, "PNG")
            logger.info(f"Dummy 'zoom_out.png' létrehozva: {zoom_out_icon_path}")

        check_db_icon_path = os.path.join(icons_dir, "check_database.png")
        if not os.path.exists(check_db_icon_path):
            pixmap = QPixmap(32, 32)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            
            # Adatbázis henger rajzolása
            pen = QPen(Qt.black, 2)
            painter.setPen(pen)
            painter.drawEllipse(QRectF(8, 6, 16, 6)) # Felső ellipszis
            painter.drawLine(8, 9, 8, 23)           # Bal oldali vonal
            painter.drawLine(24, 9, 24, 23)          # Jobb oldali vonal
            painter.drawArc(QRectF(8, 20, 16, 6), 180 * 16, 180 * 16) # Alsó ív

            # Pipa rajzolása
            pen.setColor(QColor("#008000")) # Zöld szín a pipának
            pen.setWidth(3)
            painter.setPen(pen)
            painter.drawLine(13, 16, 16, 19)
            painter.drawLine(16, 19, 21, 14)

            painter.end()
            pixmap.save(check_db_icon_path, "PNG")
            logger.info(f"Dummy 'check_database.png' létrehozva: {check_db_icon_path}")

        # --- ÚJ formázás IKON LÉTREHOZÁSA ---
        desc_format_icon_path = os.path.join(icons_dir, "description_format.png")
        if not os.path.exists(desc_format_icon_path):
            pixmap = QPixmap(32, 32)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            
            # Egy "T" betűt és néhány sort rajzolunk, ami a formázást szimbolizálja
            painter.setPen(QPen(Qt.black, 3))
            font = painter.font()
            font.setPixelSize(20)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(QRect(4, 2, 15, 28), Qt.AlignCenter, "T")

            painter.setPen(QPen(Qt.black, 2))
            painter.drawLine(18, 8, 28, 8)
            painter.drawLine(18, 14, 28, 14)
            painter.drawLine(18, 20, 28, 20)
            painter.drawLine(18, 26, 28, 26)

            painter.end()
            pixmap.save(desc_format_icon_path, "PNG")
            logger.info(f"Dummy 'description_format.png' létrehozva: {desc_format_icon_path}")

    def _setup_log_panel(self):
        self._log_panel = QTextBrowser(self)
        self._log_panel.setReadOnly(True)
        self._log_panel.setStyleSheet("QTextBrowser { background-color: #d5e0f5; border: 2px solid #E0E0E0; font-family: 'Consolas', 'Monospace'; }")
        self._log_stacked_widget = QStackedWidget(self)
        self._log_stacked_widget.addWidget(QWidget())
        self._log_stacked_widget.addWidget(self._log_panel)
        self._log_stacked_widget.setCurrentIndex(0)

    
    @Slot(bool)
    def _handle_log_toggle_click(self, show_panel: bool):
        sizes = self._vertical_main_splitter.sizes()
        total_height = sum(sizes)
        handle = self._vertical_main_splitter.handle(1)

        if show_panel:
            if not self._log_panel.toPlainText():
                self._log_panel.clear()
                for msg in self._log_history:
                    self._log_panel.append(msg)
            
            scrollbar = self._log_panel.verticalScrollBar()
            if scrollbar: scrollbar.setValue(scrollbar.maximum())
            
            if sizes[1] < 10: self._vertical_main_splitter.setSizes([total_height - 200, 200])
            self._log_stacked_widget.setCurrentIndex(1)
            if handle: handle.setEnabled(True)
        else:
            self._vertical_main_splitter.setSizes([total_height, 0])
            self._log_stacked_widget.setCurrentIndex(0)
            if handle: handle.setEnabled(False)

    @Slot(str)
    def _add_message_to_log_history(self, formatted_message: str):
        current_time = datetime.now().strftime("[%H:%M:%S]")
        final_log_entry = f"{current_time} {formatted_message}"
        self._log_history.append(final_log_entry)

        if self._log_stacked_widget and self._log_stacked_widget.currentIndex() == 1:
            self._log_panel.append(final_log_entry)
            scrollbar = self._log_panel.verticalScrollBar()
            if scrollbar: scrollbar.setValue(scrollbar.maximum())

    def closeEvent(self, event: QCloseEvent):
        if self._is_shutting_down:
            event.accept()
            return
        reply = QMessageBox.question(self, "Kilépés megerősítése", "Biztosan ki szeretnél lépni?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self._is_shutting_down = True
            self.setEnabled(False)
            self.status_bar.update_status("Leállítás folyamatban...", logging.INFO, None)
            event.ignore()
            self.appShuttingDown.emit()
        else:
            event.ignore()

    def _show_confirmation_dialog(self, title: str, message: str, callback_on_yes: Callable[[], None]):
        reply = QMessageBox.question(self, title, message, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            callback_on_yes()

    @Slot(int, int)
    def _save_splitter_state(self, pos, index):
        current_sizes = self._horizontal_content_splitter.sizes()
        self.settings_manager.set_setting("client_settings.main_splitter_sizes", current_sizes)

    @Slot(str)
    def _handle_toolbar_button_click(self, button_id: str):
        item = self.toolbar.get_item_by_id(button_id)
        if not item: return

        if button_id in ("browser_toggle", "ftp_toggle", "settings_toggle", "text_editor_toggle"):
            if isinstance(item, TwoStateButton):
                if button_id == "browser_toggle": self.main_controller.handle_browser_button_click(item._is_on)
                elif button_id == "ftp_toggle": self.main_controller.handle_ftp_toggle_click(item._is_on)
                elif button_id == "settings_toggle": self.main_controller.handle_settings_request()
                elif button_id == "text_editor_toggle": self.main_controller.handle_text_editor_request()
        elif button_id == "gs_auto_btn":
            self._show_confirmation_dialog("Adatgyűjtés megerősítése", "Biztosan indulhat a Galéria Savaria adatgyűjtés?",
                                         lambda: self.main_controller.start_gs_data_extraction())
        elif button_id == "jf_auto_btn":
            self._show_confirmation_dialog("Adatgyűjtés megerősítése", "Biztosan indulhat a Jófogás adatgyűjtés?",
                                         lambda: self.main_controller.start_jf_data_extraction())
        elif button_id == "ai_generate_desc":
            self.main_controller.handle_generate_description_click()
        elif button_id == "add_product_btn":
            self.main_controller.handle_add_product_request()
        elif button_id == "check_database_btn":
            self.main_controller.handle_database_check_request()

    @Slot(str)
    def _handle_list_toolbar_click(self, button_id: str):
        if button_id == "filter_btn":
            self.main_controller.handle_filter_request()
        elif button_id == "list_plus_btn":
            if self.product_list_view:
                self.product_list_view.scale_up()
        elif button_id == "list_minus_btn":
            if self.product_list_view:
                self.product_list_view.scale_down()
        elif button_id == "search_btn":
            self.main_controller.handle_search_request()
        elif button_id == "mark_btn":
            # A hívást a 'self'-ről a 'self.main_controller'-re kell irányítani
            self.main_controller.handle_marking_request()

    