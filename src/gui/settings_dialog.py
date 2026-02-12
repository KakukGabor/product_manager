import os
import json
from datetime import datetime
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QWidget, QMessageBox, QApplication, QLineEdit,
    QCheckBox, QSpinBox, QFileDialog
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage # Ezt importáljuk a képkezeléshez
# from resources import GLOBAL_FOLDER_ICON_PATH
from gui.folder_selector.folder_selector import PySideFolderSelector
from managers.resource_manager import ResourceManager
from managers.settings_manager import SettingsManager


class SettingsDialog(QDialog):
    def __init__(self, settings_manager: SettingsManager, resource_manager: ResourceManager, parent=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.resource_manager = resource_manager # <-- EZ AZ ÚJ, FONTOS SOR
        
        self.setWindowTitle("Beállítások")
        self.setWindowFlags(self.windowFlags() | Qt.Dialog)
        self._set_dynamic_size()
        self.setMinimumSize(self.size()) 

        self._dark_entry_style = "QLineEdit { background-color: #606060; color: white; border: 1px solid #606060; font-weight: bold; }"

        self._setup_ui()
        self._load_settings_to_ui()
        self._center_on_parent()

    def _set_dynamic_size(self):
        screen = QApplication.primaryScreen()
        if screen:
            available_geometry = screen.availableGeometry()
            dlg_width = int(available_geometry.width() * 0.7)
            dlg_height = int(available_geometry.height() * 0.7)
            self.resize(dlg_width, dlg_height)
        else:
            self.resize(800, 600)

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)

        self.tab_widget = QTabWidget(self)
        main_layout.addWidget(self.tab_widget)

        self._create_client_tab()
        self._create_server_tab()
        self._create_browser_tab()
        self._create_images_tab()
        self._create_email_tab()

        self.tab_widget.setCurrentIndex(0)

        self._create_buttons(main_layout)


    def _create_client_tab(self):
        client_page = QWidget()
        client_layout = QVBoxLayout(client_page)

        initial_download_folder_path = self.settings_manager.get_setting("client_settings.download_folder", os.path.expanduser("~"))
        self.client_download_folder_selector = PySideFolderSelector(
            label_text="Letöltés mappa:",
            initial_path=initial_download_folder_path,
            parent=client_page
        )
        client_layout.addWidget(self.client_download_folder_selector)

        client_layout.addStretch()
        self.tab_widget.addTab(client_page, "Kliensoldal")

    def _create_server_tab(self):
        server_page = QWidget()
        server_layout = QVBoxLayout(server_page)

        # Weboldal URL
        server_layout.addWidget(QLabel("Weboldal URL:"))
        self.server_url_entry = QLineEdit()
        self.server_url_entry.setPlaceholderText("Kérlek állítsd be!")
        self.server_url_entry.setStyleSheet(self._dark_entry_style)
        server_layout.addWidget(self.server_url_entry)
        
        # FTP Kiszolgáló
        server_layout.addWidget(QLabel("FTP Kiszolgáló:"))
        self.ftp_host_entry = QLineEdit()
        self.ftp_host_entry.setPlaceholderText("Kérlek állítsd be!")
        self.ftp_host_entry.setStyleSheet(self._dark_entry_style)
        server_layout.addWidget(self.ftp_host_entry)

        # FTP Név
        server_layout.addWidget(QLabel("FTP Név:"))
        self.ftp_user_entry = QLineEdit()
        self.ftp_user_entry.setPlaceholderText("Kérlek állítsd be!")
        self.ftp_user_entry.setStyleSheet(self._dark_entry_style)
        server_layout.addWidget(self.ftp_user_entry)

        # FTP Jelszó
        server_layout.addWidget(QLabel("FTP Jelszó:"))
        self.ftp_pass_entry = QLineEdit()
        self.ftp_pass_entry.setPlaceholderText("Kérlek állítsd be!")
        self.ftp_pass_entry.setEchoMode(QLineEdit.Password)
        self.ftp_pass_entry.setStyleSheet(self._dark_entry_style)
        server_layout.addWidget(self.ftp_pass_entry)

        server_layout.addStretch()
        self.tab_widget.addTab(server_page, "Szerveroldal")

    def _create_browser_tab(self):
        browser_main_page = QWidget()
        browser_main_layout = QVBoxLayout(browser_main_page)

        self.browser_sub_tab_widget = QTabWidget(browser_main_page)
        browser_main_layout.addWidget(self.browser_sub_tab_widget)

        self._create_browser_general_sub_tab()
        self._create_browser_gs_sub_tab()
        self._create_browser_jf_sub_tab()
        self._create_browser_fb_sub_tab()

        self.browser_sub_tab_widget.setCurrentIndex(0)
        self.tab_widget.addTab(browser_main_page, "Böngésző")

    def _create_browser_general_sub_tab(self):
        general_browser_settings_page = QWidget()
        general_layout = QVBoxLayout(general_browser_settings_page)

        # Headless mód
        self.browser_headless_checkbox = QCheckBox("Böngésző futtatása 'headless' módban (háttérben)")
        general_layout.addWidget(self.browser_headless_checkbox)

        # Alapértelmezett navigációs időkorlát
        general_layout.addWidget(QLabel("Alapértelmezett navigációs időkorlát (ms):"))
        self.browser_default_navigation_timeout_spinbox = QSpinBox()
        self.browser_default_navigation_timeout_spinbox.setRange(1000, 120000) # 1mp-től 2 percig
        self.browser_default_navigation_timeout_spinbox.setSingleStep(1000)
        self.browser_default_navigation_timeout_spinbox.setSuffix(" ms")
        general_layout.addWidget(self.browser_default_navigation_timeout_spinbox)

        # Elem láthatósági időkorlát
        general_layout.addWidget(QLabel("Elem láthatósági/interakciós időkorlát (ms):"))
        self.browser_element_visibility_timeout_spinbox = QSpinBox()
        self.browser_element_visibility_timeout_spinbox.setRange(100, 30000) # 100ms-től 30mp-ig
        self.browser_element_visibility_timeout_spinbox.setSingleStep(100)
        self.browser_element_visibility_timeout_spinbox.setSuffix(" ms")
        general_layout.addWidget(self.browser_element_visibility_timeout_spinbox)
        
        # Böngésző bezárási időkorlát
        general_layout.addWidget(QLabel("Böngésző bezárási időkorlát (s):"))
        self.browser_close_timeout_spinbox = QSpinBox()
        self.browser_close_timeout_spinbox.setRange(1, 60) # 1mp-től 60mp-ig
        self.browser_close_timeout_spinbox.setSingleStep(1)
        self.browser_close_timeout_spinbox.setSuffix(" s")
        general_layout.addWidget(self.browser_close_timeout_spinbox)

        # ÚJ: Akciók közötti minimális várakozási idő
        general_layout.addWidget(QLabel("Akciók közötti minimális várakozás (ms):"))
        self.browser_post_action_delay_spinbox = QSpinBox()
        self.browser_post_action_delay_spinbox.setRange(0, 10000) # 0ms-től 10mp-ig
        self.browser_post_action_delay_spinbox.setSingleStep(100)
        self.browser_post_action_delay_spinbox.setSuffix(" ms")
        general_layout.addWidget(self.browser_post_action_delay_spinbox)


        general_layout.addStretch()
        self.browser_sub_tab_widget.addTab(general_browser_settings_page, "Általános")

    def _create_browser_gs_sub_tab(self):
        gs_page = QWidget()
        gs_layout = QVBoxLayout(gs_page)

        gs_layout.addWidget(QLabel("Galéria Savaria specifikus URL-ek:"))
        
        gs_layout.addWidget(QLabel("Gomb cél URL (alap oldal):"))
        self.gs_button_target_url_entry = QLineEdit()
        self.gs_button_target_url_entry.setPlaceholderText("pl. https://galeriasavaria.hu/")
        self.gs_button_target_url_entry.setStyleSheet(self._dark_entry_style)
        gs_layout.addWidget(self.gs_button_target_url_entry)

        gs_layout.addWidget(QLabel("Termékek oldal URL:"))
        self.gs_products_url_entry = QLineEdit()
        self.gs_products_url_entry.setPlaceholderText("pl. https://galeriasavaria.hu/termekek")
        self.gs_products_url_entry.setStyleSheet(self._dark_entry_style)
        gs_layout.addWidget(self.gs_products_url_entry)

        gs_layout.addWidget(QLabel("Új termék feltöltési URL:"))
        self.gs_new_product_url_entry = QLineEdit()
        self.gs_new_product_url_entry.setPlaceholderText("pl. https://galeriasavaria.hu/feltoltes")
        self.gs_new_product_url_entry.setStyleSheet(self._dark_entry_style)
        gs_layout.addWidget(self.gs_new_product_url_entry)

        gs_layout.addStretch()
        self.browser_sub_tab_widget.addTab(gs_page, "Galéria Savaria")

    def _create_browser_jf_sub_tab(self):
        jf_page = QWidget()
        jf_layout = QVBoxLayout(jf_page)

        jf_layout.addWidget(QLabel("Jófogás specifikus URL-ek:"))

        jf_layout.addWidget(QLabel("Gomb cél URL (alap oldal):):"))
        self.jf_button_target_url_entry = QLineEdit()
        self.jf_button_target_url_entry.setPlaceholderText("pl. https://www.jofogas.hu/")
        self.jf_button_target_url_entry.setStyleSheet(self._dark_entry_style)
        jf_layout.addWidget(self.jf_button_target_url_entry)

        jf_layout.addWidget(QLabel("Hirdetések oldal URL:"))
        self.jf_products_url_entry = QLineEdit()
        self.jf_products_url_entry.setPlaceholderText("pl. https://www.jofogas.hu/hirdetesek")
        self.jf_products_url_entry.setStyleSheet(self._dark_entry_style)
        jf_layout.addWidget(self.jf_products_url_entry)

        jf_layout.addWidget(QLabel("Hirdetés feladási URL:"))
        self.jf_new_product_url_entry = QLineEdit()
        self.jf_new_product_url_entry.setPlaceholderText("pl. https://www.jofogas.hu/hirdetes-feladasa")
        self.jf_new_product_url_entry.setStyleSheet(self._dark_entry_style)
        jf_layout.addWidget(self.jf_new_product_url_entry)

        jf_layout.addWidget(QLabel("Sikeres termékfeladás URL:"))
        self.jf_upload_success_url_entry = QLineEdit()
        self.jf_upload_success_url_entry.setPlaceholderText("pl. https://www2.jofogas.hu/ai/confirm/0")
        self.jf_upload_success_url_entry.setStyleSheet(self._dark_entry_style)
        jf_layout.addWidget(self.jf_upload_success_url_entry)

        jf_layout.addStretch()
        self.browser_sub_tab_widget.addTab(jf_page, "Jófogás")

    def _create_browser_fb_sub_tab(self):
        fb_page = QWidget()
        fb_layout = QVBoxLayout(fb_page)
        
        fb_layout.addWidget(QLabel("Facebook API Beállítások (Graph API):"))

        # Page ID
        fb_layout.addWidget(QLabel("Page ID (Oldal azonosító):"))
        self.fb_page_id_entry = QLineEdit()
        self.fb_page_id_entry.setPlaceholderText("pl. 103978284320096")
        self.fb_page_id_entry.setStyleSheet(self._dark_entry_style)
        fb_layout.addWidget(self.fb_page_id_entry)

        # Access Token
        fb_layout.addWidget(QLabel("Page Access Token (Hozzáférési kulcs):"))
        self.fb_access_token_entry = QLineEdit()
        self.fb_access_token_entry.setPlaceholderText("EAA...")
        self.fb_access_token_entry.setEchoMode(QLineEdit.Password) # Jelszóként rejtjük
        self.fb_access_token_entry.setStyleSheet(self._dark_entry_style)
        fb_layout.addWidget(self.fb_access_token_entry)

        # Gomb URL (Marad, a 'Megnyitás' gombhoz)
        fb_layout.addWidget(QLabel("Böngésző gomb cél URL (Opcionális):"))
        self.fb_button_target_url_entry = QLineEdit()
        self.fb_button_target_url_entry.setPlaceholderText("pl. https://www.facebook.com/")
        self.fb_button_target_url_entry.setStyleSheet(self._dark_entry_style)
        fb_layout.addWidget(self.fb_button_target_url_entry)

        fb_layout.addStretch()
        self.browser_sub_tab_widget.addTab(fb_page, "Facebook API")

    def _create_images_tab(self):
        images_page = QWidget()
        images_layout = QVBoxLayout(images_page)

        # Aktuális háttérkép opció
        background_image_layout = QHBoxLayout()
        background_image_layout.addWidget(QLabel("Aktuális háttérkép:"))
        
        self.images_background_image_path_entry = QLineEdit()
        self.images_background_image_path_entry.setPlaceholderText("Válassz ki egy képfájlt...")
        self.images_background_image_path_entry.setReadOnly(True) # Csak olvasási mód
        self.images_background_image_path_entry.setStyleSheet(self._dark_entry_style)
        background_image_layout.addWidget(self.images_background_image_path_entry)

        self.images_browse_background_image_button = QPushButton("...")
        self.images_browse_background_image_button.clicked.connect(self._browse_background_image_file)
        background_image_layout.addWidget(self.images_browse_background_image_button)

        images_layout.addLayout(background_image_layout)
        images_layout.addStretch()
        self.tab_widget.addTab(images_page, "Képek")

    def _browse_background_image_file(self):
        """Megnyit egy fájlválasztó ablakot a háttérkép kiválasztásához és ellenőrzi a felbontást."""
        # Meghatározzuk az alapértelmezett könyvtárat
        # Feltételezzük, hogy a hirdetes_kezelo a projekt gyökere
        # és a SettingsDialog egy 'gui' alkönyvtárban van
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        default_dir = os.path.join(project_root, "app_data_storage", "image_backgrounds")

        # Létrehozzuk a könyvtárat, ha nem létezik
        if not os.path.exists(default_dir):
            try:
                os.makedirs(default_dir)
            except OSError as e:
                QMessageBox.critical(self, "Könyvtár létrehozási hiba", f"Nem sikerült létrehozni a háttérkép mappát: {default_dir}. Hiba: {e}")
                default_dir = os.path.expanduser("~") # Fallback home directory

        current_path = self.images_background_image_path_entry.text()
        if not current_path or not os.path.exists(current_path):
            current_path = default_dir
            
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Háttérkép kiválasztása",
            current_path,
            "Képek (*.png *.jpg *.jpeg *.gif *.bmp);;Minden fájl (*.*)"
        )
        if file_path:
            image = QImage(file_path)
            if image.isNull():
                QMessageBox.critical(self, "Kép betöltési hiba", "Nem sikerült betölteni a kiválasztott képfájlt. Lehet, hogy sérült vagy nem támogatott formátum.")
                return

            width = image.width()
            height = image.height()

            if width == 2048 and height == 2048:
                self.images_background_image_path_entry.setText(file_path)
            else:
                QMessageBox.warning(
                    self,
                    "Érvénytelen felbontás",
                    f"A kiválasztott kép felbontása ({width}x{height}) nem 2048x2048 pixel. Kérlek válassz egy megfelelő felbontású képet."
                )

    def _create_email_tab(self):
        email_page = QWidget()
        email_layout = QVBoxLayout(email_page)

        email_layout.addWidget(QLabel("Küldő Gmail címe:"))
        self.email_sender_entry = QLineEdit()
        self.email_sender_entry.setPlaceholderText("pl. te.neved@gmail.com")
        self.email_sender_entry.setStyleSheet(self._dark_entry_style)
        email_layout.addWidget(self.email_sender_entry)

        email_layout.addWidget(QLabel("Gmail Alkalmazásjelszó (16 karakter):"))
        self.email_app_password_entry = QLineEdit()
        self.email_app_password_entry.setPlaceholderText("Másold be a generált 16 jegyű kódot")
        self.email_app_password_entry.setEchoMode(QLineEdit.Password)
        self.email_app_password_entry.setStyleSheet(self._dark_entry_style)
        email_layout.addWidget(self.email_app_password_entry)
        
        email_layout.addWidget(QLabel("Alapértelmezett címzett email címe:"))
        self.email_recipient_entry = QLineEdit()
        self.email_recipient_entry.setPlaceholderText("pl. partner.neve@email.hu")
        self.email_recipient_entry.setStyleSheet(self._dark_entry_style)
        email_layout.addWidget(self.email_recipient_entry)
        
        email_layout.addStretch()
        self.tab_widget.addTab(email_page, "Email")

    def _create_buttons(self, parent_layout):
        button_frame = QWidget()
        button_layout = QHBoxLayout(button_frame)
        button_layout.setContentsMargins(0, 0, 0, 0)

        save_button = QPushButton("Mentés")
        save_button.clicked.connect(self.accept)
        
        cancel_button = QPushButton("Mégse")
        cancel_button.clicked.connect(self.reject)

        button_layout.addStretch()
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(save_button)
        
        parent_layout.addWidget(button_frame)

    def _load_settings_to_ui(self):
        """Betölti a beállításokat a SettingsManager-ből a UI elemekbe."""
        
        # Kliensoldal
        self.client_download_folder_selector.set_path(self.settings_manager.get_setting("client_settings.download_folder", os.path.expanduser("~")))

        # Szerveroldal
        self.server_url_entry.setText(self.settings_manager.get_setting("server_settings.website_url", ""))
        self.ftp_host_entry.setText(self.settings_manager.get_setting("server_settings.ftp_host", ""))
        self.ftp_user_entry.setText(self.settings_manager.get_setting("server_settings.ftp_user", ""))
        self.ftp_pass_entry.setText(self.settings_manager.get_setting("server_settings.ftp_pass", ""))

        # Böngésző - Általános
        self.browser_headless_checkbox.setChecked(self.settings_manager.get_setting("browser_settings.headless", False))
        self.browser_default_navigation_timeout_spinbox.setValue(self.settings_manager.get_setting("browser_settings.default_navigation_timeout_ms", 30000))
        self.browser_element_visibility_timeout_spinbox.setValue(self.settings_manager.get_setting("browser_settings.element_visibility_timeout_ms", 5000))
        self.browser_close_timeout_spinbox.setValue(self.settings_manager.get_setting("browser_settings.browser_close_timeout_s", 5))
        self.browser_post_action_delay_spinbox.setValue(self.settings_manager.get_setting("browser_settings.post_action_delay_ms", 500))

        # Böngésző - Galéria Savaria
        self.gs_button_target_url_entry.setText(self.settings_manager.get_setting("site_configs.galeria_savaria.button_target_url", "https://galeriasavaria.hu/"))
        self.gs_products_url_entry.setText(self.settings_manager.get_setting("site_configs.galeria_savaria.products_url", "https://galeriasavaria.hu/termekek"))
        self.gs_new_product_url_entry.setText(self.settings_manager.get_setting("site_configs.galeria_savaria.new_product_url", "https://galeriasavaria.hu/feltoltes"))

        # Böngésző - Jófogás
        self.jf_button_target_url_entry.setText(self.settings_manager.get_setting("site_configs.jofogas.button_target_url", "https://www.jofogas.hu/"))
        self.jf_products_url_entry.setText(self.settings_manager.get_setting("site_configs.jofogas.products_url", "https://www.jofogas.hu/hirdetesek"))
        self.jf_new_product_url_entry.setText(self.settings_manager.get_setting("site_configs.jofogas.new_product_url", "https://www.jofogas.hu/hirdetes-feladasa"))
        self.jf_upload_success_url_entry.setText(self.settings_manager.get_setting("site_configs.jofogas.upload_success_url", "https://www2.jofogas.hu/ai/confirm/0"))
        # Böngésző - Facebook
        self.fb_button_target_url_entry.setText(self.settings_manager.get_setting("site_configs.facebook.button_target_url", "https://www.facebook.com/"))
        self.fb_page_id_entry.setText(self.settings_manager.get_setting("site_configs.facebook.page_id", ""))
        self.fb_access_token_entry.setText(self.settings_manager.get_setting("site_configs.facebook.access_token", ""))
        self.fb_button_target_url_entry.setText(self.settings_manager.get_setting("site_configs.facebook.button_target_url", "https://www.facebook.com/"))

        # Képek
        self.images_background_image_path_entry.setText(self.settings_manager.get_setting("image_settings.background_image_path", ""))

        # Email beállítások betöltése
        self.email_sender_entry.setText(self.settings_manager.get_setting("email_settings.sender_email", ""))
        self.email_app_password_entry.setText(self.settings_manager.get_setting("email_settings.app_password", ""))
        self.email_recipient_entry.setText(self.settings_manager.get_setting("email_settings.recipient_email", ""))


    def _save_settings_from_ui(self):
        """Elmenti a UI elemekből az értékeket a SettingsManager-be."""

        # Kliensoldal
        self.settings_manager.set_setting("client_settings.download_folder", self.client_download_folder_selector.get_path())

        # Szerveroldal
        self.settings_manager.set_setting("server_settings.website_url", self.server_url_entry.text())
        self.settings_manager.set_setting("server_settings.ftp_host", self.ftp_host_entry.text())
        self.settings_manager.set_setting("server_settings.ftp_user", self.ftp_user_entry.text())
        self.settings_manager.set_setting("server_settings.ftp_pass", self.ftp_pass_entry.text())

        # Böngésző - Általános
        self.settings_manager.set_setting("browser_settings.headless", self.browser_headless_checkbox.isChecked())
        self.settings_manager.set_setting("browser_settings.default_navigation_timeout_ms", self.browser_default_navigation_timeout_spinbox.value())
        self.settings_manager.set_setting("browser_settings.element_visibility_timeout_ms", self.browser_element_visibility_timeout_spinbox.value())
        self.settings_manager.set_setting("browser_settings.browser_close_timeout_s", self.browser_close_timeout_spinbox.value())
        self.settings_manager.set_setting("browser_settings.post_action_delay_ms", self.browser_post_action_delay_spinbox.value())

        # Böngésző - Galéria Savaria
        self.settings_manager.set_setting("site_configs.galeria_savaria.button_target_url", self.gs_button_target_url_entry.text())
        self.settings_manager.set_setting("site_configs.galeria_savaria.products_url", self.gs_products_url_entry.text())
        self.settings_manager.set_setting("site_configs.galeria_savaria.new_product_url", self.gs_new_product_url_entry.text())

        # Böngésző - Jófogás
        self.settings_manager.set_setting("site_configs.jofogas.button_target_url", self.jf_button_target_url_entry.text())
        self.settings_manager.set_setting("site_configs.jofogas.products_url", self.jf_products_url_entry.text())
        self.settings_manager.set_setting("site_configs.jofogas.new_product_url", self.jf_new_product_url_entry.text())
        self.settings_manager.set_setting("site_configs.jofogas.upload_success_url", self.jf_upload_success_url_entry.text())

        # Böngésző - Facebook
        self.settings_manager.set_setting("site_configs.facebook.button_target_url", self.fb_button_target_url_entry.text())
        self.settings_manager.set_setting("site_configs.facebook.page_id", self.fb_page_id_entry.text().strip())
        self.settings_manager.set_setting("site_configs.facebook.access_token", self.fb_access_token_entry.text().strip())
        self.settings_manager.set_setting("site_configs.facebook.button_target_url", self.fb_button_target_url_entry.text())

        # Képek
        self.settings_manager.set_setting("image_settings.background_image_path", self.images_background_image_path_entry.text())

        # Email beállítások mentése
        self.settings_manager.set_setting("email_settings.sender_email", self.email_sender_entry.text())
        self.settings_manager.set_setting("email_settings.app_password", self.email_app_password_entry.text())
        self.settings_manager.set_setting("email_settings.recipient_email", self.email_recipient_entry.text())

        self.settings_manager.save_settings() # Mentsük el a beállításokat a fájlba


    def accept(self):
        """Felülírjuk az alapértelmezett accept() metódust, hogy mentse a beállításokat."""
        try:
            self._save_settings_from_ui()
            QMessageBox.information(self, "Beállítások mentve", "A beállítások sikeresen mentésre kerültek.")
            super().accept() # Hívjuk meg a QDialog alapértelmezett accept() metódusát
        except Exception as e:
            QMessageBox.critical(self, "Hiba a mentés során", f"Hiba történt a beállítások mentésekor: {e}")


    def _center_on_parent(self):
        if self.parent():
            parent_geometry = self.parent().geometry()
            dialog_geometry = self.geometry()

            x = parent_geometry.x() + (parent_geometry.width() - dialog_geometry.width()) // 2
            y = parent_geometry.y() + (parent_geometry.height() - dialog_geometry.height()) // 2

            self.move(x, y)
        else:
            screen = QApplication.primaryScreen()
            if screen:
                screen_geometry = screen.availableGeometry()
                dialog_geometry = self.geometry()
                x = (screen_geometry.width() - dialog_geometry.width()) // 2
                y = (screen_geometry.height() - dialog_geometry.height()) // 2
                self.move(x, y)
            else:
                print("Hiba: Nincs szülő, és nem sikerült lekérdezni a képernyő adatait sem a középre igazításhoz.")
