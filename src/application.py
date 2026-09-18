# src/application.py
import sys
import logging
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTranslator, QLibraryInfo, QLocale, QSharedMemory, Qt, Slot
from pathlib import Path

from managers.settings_manager import SettingsManager
from managers.resource_manager import ResourceManager
from gui.main_window import MainWindow
from automation.playwright_automator import PlaywrightAutomator
from managers.product_category_manager import ProductCategoryManager
from managers.product_manager import ProductManager
from automation.sites.gs_automator import GaleriaSavariaAutomator
from automation.sites.jofogas_automator import JofogasAutomator
from controllers.main_controller import MainController
from gui.settings_dialog import SettingsDialog
from managers.ftp_manager import FtpManager
from controllers.text_editor_controller import TextEditorController
from gui.product_list_view.product_list_view import ProductListView
from gui.product_detail_widget.product_detail_widget import ProductDetailWidget
from gui.image_gallery_widget.image_gallery_widget import ImageGalleryWidget
from gui.product_list_view.filter_dialog import FilterDialog
from managers.email_manager import EmailManager
from automation.sites.fb_automator import FacebookAutomator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)



class Application:
    SHARED_MEMORY_KEY = "ProductManager_SingleInstance"

    def __init__(self, argv):
        self._app = QApplication(argv)
        self._translator = QTranslator()

        if getattr(sys, 'frozen', False):
            self.app_root_path = Path(sys.executable).parent.absolute()
        else:
            self.app_root_path = Path(__file__).parent.parent.absolute()

        # A fordítások betöltése, mielőtt bármilyen UI elem létrejönne
        self._load_translations()

        self._shared_memory = QSharedMemory(self.SHARED_MEMORY_KEY)
        if self._shared_memory.attach():
            # Ha az előző leállás nem volt tiszta, először lecsatoljuk
            self._shared_memory.detach()
            
        if not self._shared_memory.create(1):
            sys.exit(1)
        self._app.aboutToQuit.connect(self._release_shared_memory)
        
        # --- KOMPONENSEK LÉTREHOZÁSA A HELYES SORRENDBEN ---

        # 1. Managerek és háttérszolgáltatások létrehozása
        self._settings_manager = SettingsManager(filename="settings.json", app_root_path=self.app_root_path)
        self._resource_manager = ResourceManager(app_root_path=self.app_root_path)
        self._category_manager = ProductCategoryManager()
        self._product_manager = ProductManager(
            app_root_dir=str(self.app_root_path),
            settings_manager=self._settings_manager,
            category_manager=self._category_manager
        )

        self._playwright_automator = PlaywrightAutomator(str(self.app_root_path), self._settings_manager)
        self._gs_automator = GaleriaSavariaAutomator(
            core_automator=self._playwright_automator,
            settings_manager=self._settings_manager
        )
        # <-- ÚJ JOFOGAS AUTOMATOR PÉLDÁNYOSÍTÁS
        self._jofogas_automator = JofogasAutomator(
            core_automator=self._playwright_automator,
            settings_manager=self._settings_manager,
            app_root_dir=str(self.app_root_path)
        )
        # -->

        self._fb_automator = FacebookAutomator(
            core_automator=self._playwright_automator,
            settings_manager=self._settings_manager
        )

        self._playwright_automator.start_event_loop()

        self._ftp_manager = FtpManager(
            core_automator=self._playwright_automator,
            settings_manager=self._settings_manager,
            product_manager=self._product_manager
        )

        self._email_manager = EmailManager(
            settings_manager=self._settings_manager,
            loop_worker=self._playwright_automator.loop_worker
        )

        self._text_editor_controller = TextEditorController(
            settings_manager=self._settings_manager,
            resource_manager=self._resource_manager
        )

        # 2. A Controller létrehozása
        self._main_controller = MainController(
            playwright_automator=self._playwright_automator,
            product_manager=self._product_manager,
            gs_automator=self._gs_automator,
            jf_automator=self._jofogas_automator,
            fb_automator=self._fb_automator,  # <-- EZT A SORT KELL BETENNED!
            ftp_manager=self._ftp_manager,
            email_manager=self._email_manager,
            text_editor_controller=self._text_editor_controller
        )

        self._product_list_view = ProductListView(self._settings_manager)
        self._image_gallery_widget = ImageGalleryWidget(self._product_manager, str(self.app_root_path), self._settings_manager, resource_manager=self._resource_manager)
        self._product_detail_widget = ProductDetailWidget(self._product_manager, self._category_manager, self._ftp_manager, self._image_gallery_widget)
        self._filter_dialog = FilterDialog(self._category_manager)

        # 3. A Főablak (szülő) létrehozása
        self._main_window = MainWindow(
            settings_manager=self._settings_manager,
            resource_manager=self._resource_manager,
            main_controller=self._main_controller,
            # Új paraméterek az __init__-ben:
            product_list_view=self._product_list_view,
            product_detail_widget=self._product_detail_widget,
            image_gallery_widget=self._image_gallery_widget
        )

        # 4. A Beállítások dialógus (gyermek) létrehozása, a már létező főablakkal mint szülővel
        self._settings_dialog = SettingsDialog(
            settings_manager=self._settings_manager,
            resource_manager=self._resource_manager,
            parent=self._main_window  # Most már a self._main_window létezik!
        )

        # 5. A dialógusablak átadása a Controllernek
        self._main_controller.set_settings_dialog(self._settings_dialog)
        self._main_controller.set_filter_dialog(self._filter_dialog)
        self._main_controller.set_main_widgets(
            self._product_list_view,
            self._product_detail_widget,
            self._image_gallery_widget
        )

        # --- SZIGNÁL-SLOT KAPCSOLATOK ---
        self._main_window.appShuttingDown.connect(self._main_controller.handle_app_shutting_down)
        self._playwright_automator.workerShutdownCompleted.connect(self.quit_application, Qt.QueuedConnection)
        self._gs_automator.gsDataExtractionFinished.connect(self._product_manager.process_gs_extracted_products_slot)
        self._jofogas_automator.jfDataExtractionFinished.connect(self._product_manager.process_jf_extracted_products_slot)
        self._text_editor_controller.statusUpdated.connect(self._main_controller.updateStatusBar)
        self._gs_automator.gsSemiAutoLocateFinished.connect(self._main_controller._handle_gs_product_semi_auto_locate_finished)
        self._jofogas_automator.jfSemiAutoLocateFinished.connect(self._main_controller._handle_jf_product_semi_auto_locate_finished)
        
        self._product_manager.load_all_products_sync()

    def _load_translations(self):
        """
        Betölti a Qt magyar fordításait.
        """
        QLocale.setDefault(QLocale(QLocale.Language.Hungarian, QLocale.Country.Hungary))

        loaded_qt_translation = False

        translations_path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
        qt_hu_qm_qlib = Path(translations_path) / "qt_hu.qm"

        if translations_path and qt_hu_qm_qlib.exists() and self._translator.load("qt_hu", translations_path):
            self._app.installTranslator(self._translator)
            loaded_qt_translation = True
        else:
            logger.warning(f"A Qt magyar fordítás betöltése a QLibraryInfo útvonalról ({qt_hu_qm_qlib.absolute()}) sikertelen. Másodlagos útvonal keresése...")
            
            try:
                import PySide6
                pyside_path = Path(PySide6.__file__).parent
                pyside_translations_path = pyside_path / "translations"

                if pyside_translations_path.exists() and self._translator.load("qt_hu", str(pyside_translations_path)):
                    self._app.installTranslator(self._translator)
                    loaded_qt_translation = True
                else:
                    logger.error(f"HIBA: A Qt magyar fordítások betöltése a másodlagos útvonalról is sikertelen.")
            except ImportError:
                 logger.error("HIBA: A PySide6 csomag nem található a másodlagos fordítási útvonal kereséséhez.")


        if not loaded_qt_translation:
            logger.warning("A program a szabványos Qt vezérlők (pl. Fájl megnyitás ablak) magyar fordítása nélkül folytatódik.")


    @Slot()
    def quit_application(self):
        logger.info("A worker leállt, az alkalmazás most kilép.")
        self._app.quit()
        
    def _release_shared_memory(self):
        if self._shared_memory.isAttached():
            self._shared_memory.detach()

    def run(self):
        self._main_window.show()
        sys.exit(self._app.exec())