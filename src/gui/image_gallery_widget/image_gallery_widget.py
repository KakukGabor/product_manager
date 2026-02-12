import os
import logging
from typing import Optional, List, Dict, Any, Tuple
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea, QSizePolicy, 
    QMessageBox, QPushButton, QLabel
)
from PySide6.QtGui import QPixmap, QDragEnterEvent, QDropEvent, QImage, QIcon, QDragMoveEvent, QPainter
from PySide6.QtCore import Qt, Signal, Slot, QSize, QUrl
from pathlib import Path
import shutil
import re

from models.product_model import Product, _sanitize_for_slug, MainCategory
from managers.product_manager import ProductManager
from managers.settings_manager import SettingsManager
from gui.image_gallery_widget.image_thumbnail_widget import ImageThumbnailWidget
from managers.resource_manager import ResourceManager
from .igw_ui import ImageGalleryUi

logger = logging.getLogger(__name__)

class ImageGalleryWidget(QWidget):

    SUPPORTED_IMAGE_FORMATS = ['.jpg', '.jpeg', '.png', '.gif', '.webp']

    IMAGE_TAGS = {
        "mixed_": "Szerkesztett képek",
        "original_": "Eredeti képek",
        "transparent_": "Transzparens képek"
    }
    IMAGE_TAG_ORDER = ["mixed_", "original_", "transparent_"]
   
    imagesUpdated = Signal(str, Dict[str, Any])
    initialImagesLoadedComplete = Signal()
    imageLoadingStarted = Signal()
    imageLoadingFinished = Signal()

    TEMP_PRODUCT_ID = "__TMP_NEW_PRODUCT__"

    def __init__(self, product_manager: ProductManager, project_root: str, settings_manager: SettingsManager, 
                 resource_manager: ResourceManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.product_manager = product_manager
        self._project_root = Path(project_root).resolve()
        self.settings_manager = settings_manager
        self.resource_manager = resource_manager

        self._current_product_id: Optional[str] = None
        self._is_temp_mode_active: bool = False

        self._tmp_image_dir: Path = self._project_root / "app_data_storage" / "tmp_images"
        self._tmp_image_dir.mkdir(parents=True, exist_ok=True)
       
        icons_dir = self._project_root / "res" / "icons"
        self.ICON_DOWN_PATH = icons_dir / "drop_down.png"
        self.ICON_UP_PATH = icons_dir / "drop_up.png"

        self._all_product_image_data: Dict[str, List[Tuple[str, str, str]]] = {tag: [] for tag in self.IMAGE_TAG_ORDER}
        self._image_widgets: Dict[str, List[ImageThumbnailWidget]] = {tag: [] for tag in self.IMAGE_TAG_ORDER}
        self._image_layout_widgets: Dict[str, QVBoxLayout] = {}
        self._header_labels: Dict[str, QLabel] = {}

        self._is_expanded: bool = False
        
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setAcceptDrops(True)
        self.setAutoFillBackground(True)
        
        self.ui = ImageGalleryUi()
        self.ui.setup_ui(self)
        
        self.toggle_expand_button.clicked.connect(self._toggle_gallery_expansion)
        self._update_expand_button_icon()
    

    def _log(self, level: int, message: str, *args, **kwargs):
        logger.log(level, f"[ImageGalleryWidget] {message}", *args, **kwargs)

    def _update_expand_button_icon(self):
        if self._is_expanded:
            if self.ICON_UP_PATH.exists():
                self.toggle_expand_button.setIcon(QIcon(str(self.ICON_UP_PATH)))
            else:
                self.toggle_expand_button.setIcon(QIcon.fromTheme("go-up"))
            self.toggle_expand_button.setText("")
        else:
            if self.ICON_DOWN_PATH.exists():
                self.toggle_expand_button.setIcon(QIcon(str(self.ICON_DOWN_PATH)))
            else:
                self.toggle_expand_button.setIcon(QIcon.fromTheme("go-down"))
            self.toggle_expand_button.setText("")

    @Slot()
    def _toggle_gallery_expansion(self):
        self._is_expanded = not self._is_expanded
        self._update_expand_button_icon()
        self._display_current_images()

    @Slot(str)
    def set_product_id(self, product_id: Optional[str]):
        if product_id is None:
            if self._current_product_id == ImageGalleryWidget.TEMP_PRODUCT_ID:
                self.initialImagesLoadedComplete.emit()
                self.imageLoadingFinished.emit()
                return

            self._current_product_id = ImageGalleryWidget.TEMP_PRODUCT_ID
            self._is_temp_mode_active = True
        else:
            if self._current_product_id == product_id and not self._is_temp_mode_active:
                if self._current_product_id:
                    self.initialImagesLoadedComplete.emit()
                    self.imageLoadingFinished.emit()
                return

            self._current_product_id = product_id
            self._is_temp_mode_active = False

        self._is_expanded = False
        self._update_expand_button_icon()

        self.imageLoadingStarted.emit()

        self._clear_gallery_data()
        self._load_all_image_paths_for_current_product()
        self._display_current_images()

        self._scroll_to_position(0)
        self.initialImagesLoadedComplete.emit()
        self.imageLoadingFinished.emit()

    @Slot()
    def clear_temporary_images(self):
        self.imageLoadingStarted.emit()
        try:
            for f in self._tmp_image_dir.iterdir():
                if f.is_file():
                    os.remove(f)
        except OSError as e:
            QMessageBox.critical(self, "Hiba", f"Nem sikerült kiüríteni az ideiglenes képmappát: {e}")
        finally:
            self._clear_gallery_data()
            self._load_all_image_paths_for_current_product()
            self._display_current_images()
            self._scroll_to_position(0)
            self.imageLoadingFinished.emit()


    def _clear_gallery_data(self):
        for tag in self.IMAGE_TAG_ORDER:
            self._all_product_image_data[tag].clear()
            for widget in self._image_widgets[tag]:
                widget.setParent(None)
                widget.deleteLater()
            self._image_widgets[tag].clear()


    def _load_all_image_paths_for_current_product(self):
        if not self._current_product_id:
            return

        image_source_dir: Path
        product_id_for_thumbnail = self._current_product_id

        if self._is_temp_mode_active:
            image_source_dir = self._tmp_image_dir
        else:
            product = self.product_manager.get_product_by_id(self._current_product_id)
            if not product:
                return
            image_source_dir = self.product_manager._get_product_path_from_product_object(product) / "images"

        if not image_source_dir.exists():
            return

        for tag in self.IMAGE_TAG_ORDER:
            self._all_product_image_data[tag].clear()

        all_image_files: Dict[str, List[Path]] = {tag: [] for tag in self.IMAGE_TAG_ORDER}
        for f in image_source_dir.iterdir():
            if f.is_file() and f.suffix.lower() in self.SUPPORTED_IMAGE_FORMATS:
                for tag in self.IMAGE_TAG_ORDER:
                    if f.name.lower().startswith(tag):
                        all_image_files[tag].append(f)
                        break

        for tag in self.IMAGE_TAG_ORDER:
            all_image_files[tag].sort(key=lambda p: int(re.search(r'_(\d+)\.', p.name).group(1)) if re.search(r'_(\d+)\.', p.name) else 0)

            for image_path in all_image_files[tag]:
                self._all_product_image_data[tag].append((image_path.name, str(image_path), product_id_for_thumbnail))


    def _display_current_images(self):
        self._clear_displayed_widgets()

        if not self._current_product_id:
            return

        for tag in self.IMAGE_TAG_ORDER:
            if tag in self._header_labels:
                self._header_labels[tag].setVisible(self._is_expanded)

        if self._is_expanded:
            for tag in self.IMAGE_TAG_ORDER:
                for filename, image_path, product_id in self._all_product_image_data[tag]:
                    self._add_image_thumbnail_to_layout(tag, filename, image_path, product_id, show_controls=True, show_filename=True)
        else:
            if self._all_product_image_data["mixed_"]:
                filename, image_path, product_id = self._all_product_image_data["mixed_"][0]
                self._add_image_thumbnail_to_layout(
                    "mixed_", 
                    filename, 
                    image_path, 
                    product_id, 
                    show_controls=False, 
                    show_filename=False
                )
            else:
                pass



    def _clear_displayed_widgets(self):
        for tag in self.IMAGE_TAG_ORDER:
            for widget in self._image_widgets[tag]:
                widget.setParent(None)
                widget.deleteLater()
            self._image_widgets[tag].clear()

    def _add_image_thumbnail_to_layout(self, tag: str, filename: str, image_path: str, product_id: str, 
                                       show_controls: bool = True, show_filename: bool = True):
        # Megnézzük, hogy a termék modell szerint ez a kép ki van-e választva
        is_selected = False
        product = self.product_manager.get_product_by_id(product_id)
        if product and product.facebook_data and filename in product.facebook_data.selected_images:
            is_selected = True

        thumbnail = ImageThumbnailWidget(
            image_path, tag, filename, product_id, 
            show_controls, show_filename, 
            is_selected=is_selected, # <-- Átadjuk az állapotot
            resource_manager=self.resource_manager,
            parent=self
        )
        
        # Bekötjük az új signalt
        thumbnail.selectionToggled.connect(self._handle_image_selection_toggled)
        thumbnail.imageDeleted.connect(self._handle_image_deleted)
        thumbnail.moveUpRequested.connect(self._handle_move_up_requested)
        thumbnail.moveDownRequested.connect(self._handle_move_down_requested)

        target_layout = self._image_layout_widgets.get(tag)
        if target_layout:
            target_layout.addWidget(thumbnail)
            self._image_widgets[tag].append(thumbnail)
        else:
            pass


    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            all_files_valid = True
            for url in event.mimeData().urls():
                file_extension = "." + url.fileName().lower().split('.')[-1]
                if not url.isLocalFile() or file_extension not in self.SUPPORTED_IMAGE_FORMATS:
                    all_files_valid = False
                    break
            if all_files_valid:
                event.acceptProposedAction()
            else:
                event.ignore()
                self._log(logging.DEBUG, "Drag Enter: Elutasítva (nem fájl URL vagy nem kép).")
        else:
            event.ignore()
            self._log(logging.DEBUG, "Drag Enter: Elutasítva (nincsenek URL-ek).")

    def dragMoveEvent(self, event: QDragMoveEvent):
        """ Elfogadja a mozgatási eseményt, hogy a kurzor jelezze a dobás lehetőségét. """
        event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        if not self._current_product_id:
            QMessageBox.warning(self, "Hiba", "Nincs kiválasztva termék, amihez képet adhatna hozzá!")
            event.ignore()
            return

        if not event.mimeData().hasUrls():
            event.ignore()
            return

        target_dir, product = self._get_target_dir_and_product()
        if not target_dir:
            event.ignore()
            return

        processed_count = 0
        for url in event.mimeData().urls():
            if url.isLocalFile():
                if self._process_dropped_file(Path(url.toLocalFile()), target_dir, product):
                    processed_count += 1

        if processed_count > 0:
            self._finalize_processing(product)
            self._refresh_gallery()

        event.acceptProposedAction()

    # ==============================================================================
    # == Segédfüggvények a Drop Event-hez
    # ==============================================================================

    def _get_target_dir_and_product(self) -> Tuple[Optional[Path], Optional[Product]]:
        """ Meghatározza a célkönyvtárat és a termék objektumot a feldolgozáshoz. """
        if self._is_temp_mode_active:
            return self._tmp_image_dir, None
        else:
            product = self.product_manager.get_product_by_id(self._current_product_id)
            if not product:
                QMessageBox.warning(self, "Hiba", f"Nem található a(z) {self._current_product_id} ID-jű termék!")
                return None, None
            
            product_dir = self.product_manager._get_product_path_from_product_object(product)
            target_image_dir = product_dir / "images"
            target_image_dir.mkdir(parents=True, exist_ok=True)
            return target_image_dir, product

    def _process_dropped_file(self, source_path: Path, target_dir: Path, product: Optional[Product]) -> bool:
        """
        Egyetlen eldobott fájl teljes feldolgozási logikája:
        betöltés, átméretezés, transzparencia-detektálás, mentés, és 'mixed' kép generálása.
        MÓDOSÍTVA: A JPG fájlokat mindig 'original_'-ként kezeli.
        """
        resized_image, error = self._load_and_resize_image(source_path)
        if error:
            QMessageBox.warning(self, "Hiba", f"{error}\nFájl: {source_path.name}")
            return False

        # --- MÓDOSÍTÁS KEZDETE ---
        original_suffix = source_path.suffix.lower()
        tag: str
        
        if original_suffix in ['.jpg', '.jpeg']:
            # Ha az eredeti fájl JPG, akkor a címke mindig 'original_', és a transzparencia-
            # ellenőrzést kihagyjuk.
            tag = "original_"
            self._log(logging.DEBUG, f"A(z) '{source_path.name}' fájl JPG, ezért 'original_' címkét kap.")
        else:
            # Minden más fájltípus (pl. PNG) esetén lefuttatjuk az ellenőrzést.
            tag = self._detect_image_transparency(resized_image)

        # A mentési formátumot és az új kiterjesztést a címke alapján határozzuk meg.
        if tag == "transparent_":
            new_suffix = ".png"
            save_format = "PNG"
        else:  # tag == "original_"
            new_suffix = ".jpg"
            save_format = "JPG"
        # --- MÓDOSÍTÁS VÉGE ---

        new_filename = self._generate_new_filename(tag, new_suffix, target_dir)
        destination_path = target_dir / new_filename

        try:
            quality = -1 if save_format == "PNG" else 90
            if not resized_image.save(str(destination_path), save_format, quality):
                raise IOError(f"A QImage mentése ({save_format}) sikertelen.")

            self._log(logging.INFO, f"Kép feldolgozva és mentve: {destination_path.name}")
            self._update_product_model(product, tag)

            # A 'mixed' kép generálása továbbra is csak akkor történik meg, ha a kép
            # ténylegesen transzparens volt (és ezért 'transparent_' címkét kapott).
            if tag == "transparent_":
                self._create_mixed_image_from_transparent(resized_image, target_dir, product)
            
            return True
        except Exception as e:
            QMessageBox.critical(self, "Hiba", f"Nem sikerült menteni a képet: {source_path.name}\nHiba: {e}")
            return False

    def _load_and_resize_image(self, source_path: Path) -> Tuple[Optional[QImage], Optional[str]]:
        """
        Beolvassa a képet, és ha szükséges, átméretezi 2048x2048-as vászonra.
        Visszaadja a feldolgozott QImage objektumot.
        """
        source_image = QImage(str(source_path))
        if source_image.isNull():
            return None, "Nem érvényes képfájl."

        if source_image.width() == 2048 and source_image.height() == 2048:
            return source_image, None
        
        self._log(logging.INFO, f"Kép átméretezése: '{source_path.name}' ({source_image.width()}x{source_image.height()}) -> 2048x2048")
        try:
            canvas = QImage(2048, 2048, QImage.Format_ARGB32_Premultiplied)
            canvas.fill(Qt.transparent)
            scaled_image = source_image.scaled(2048, 2048, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            painter = QPainter(canvas)
            x = (canvas.width() - scaled_image.width()) // 2
            y = (canvas.height() - scaled_image.height()) // 2
            painter.drawImage(x, y, scaled_image)
            painter.end()
            return canvas, None
        except Exception as e:
            return None, f"Hiba történt az átméretezés során: {e}"

    def _detect_image_transparency(self, image: QImage) -> str:
        """ Eldönti, hogy a kép transzparens-e, és visszaadja a megfelelő taget. """
        if not image.hasAlphaChannel():
            return "original_"

        # Optimalizált ellenőrzés: megnézzük a kép négy sarkát és a közepét.
        # Ez a legtöbb esetben elég gyors és pontos.
        points_to_check = [
            (0, 0), (image.width() - 1, 0),
            (0, image.height() - 1), (image.width() - 1, image.height() - 1),
            (image.width() // 2, image.height() // 2)
        ]
        for x, y in points_to_check:
            if image.pixelColor(x, y).alpha() < 255:
                self._log(logging.DEBUG, "Transzparens pixel található (gyors ellenőrzés), 'transparent_' tag hozzárendelve.")
                return "transparent_"

        # Ha a gyors ellenőrzés nem talál semmit, lefuttatjuk a teljes vizsgálatot.
        for y in range(image.height()):
            for x in range(image.width()):
                if image.pixelColor(x, y).alpha() < 255:
                    self._log(logging.DEBUG, "Transzparens pixel található (teljes vizsgálat), 'transparent_' tag hozzárendelve.")
                    return "transparent_"
        
        self._log(logging.DEBUG, "Nincs transzparens pixel, 'original_' tag hozzárendelve.")
        return "original_"

    def _generate_new_filename(self, tag: str, suffix: str, target_dir: Path) -> str:
        """ Legenerálja a következő sorszámozott fájlnevet a tag alapján. """
        next_index = 1
        existing_files = [f for f in target_dir.iterdir() if f.is_file() and f.name.lower().startswith(tag)]
        if existing_files:
            max_index = max((int(m.group(1)) for f in existing_files if (m := re.search(r'_(\d+)\.', f.name))), default=0)
            next_index = max_index + 1
        return f"{tag}{next_index:03d}{suffix.lower()}"
    
    def _update_product_model(self, product: Optional[Product], tag: str):
        """ Frissíti a termék objektumot az új képek számával és a feltöltési állapottal. """
        if self._is_temp_mode_active or not product:
            return

        if tag == "original_": product.num_original_images += 1
        elif tag == "transparent_": product.num_transparent_images += 1
        elif tag == "mixed_": product.num_mixed_images += 1
        
        if not product.needs_upload:
            product.needs_upload = True

    def _create_mixed_image_from_transparent(self, transparent_img: QImage, target_dir: Path, product: Optional[Product]):
        """ Létrehoz egy 'mixed' képet egy transzparens képből a beállított háttérrel. """
        mixed_filename = self._generate_new_filename("mixed_", ".webp", target_dir)
        destination_mixed_path = target_dir / mixed_filename
        
        background_path_str = self.settings_manager.get_setting("image_settings.background_image_path", "")
        bg_path = Path(background_path_str)

        if not bg_path.is_absolute():
            bg_path = self._project_root / bg_path

        if not background_path_str or not bg_path.exists():
            QMessageBox.warning(self, "Hiányzó háttérkép", f"A háttérkép nincs beállítva vagy nem található. A 'mixed' verzió nem készült el.")
            return

        try:
            background_img = QImage(str(bg_path))
            if background_img.isNull():
                raise ValueError("A háttérképfájl nem tölthető be.")

            mixed_image = QImage(2048, 2048, QImage.Format_RGB32)
            painter = QPainter(mixed_image)
            
            painter.drawImage(0, 0, background_img.scaled(2048, 2048, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
            painter.drawImage(0, 0, transparent_img) # A transparent_img már 2048x2048
            painter.end()

            mixed_image.save(str(destination_mixed_path), "WEBP", 85)
            self._log(logging.INFO, f"Létrehozva: {destination_mixed_path.name}")
            self._update_product_model(product, "mixed_")

        except Exception as e:
            QMessageBox.critical(self, "Hiba", f"Nem sikerült létrehozni a 'mixed' képet: {e}")

    def _finalize_processing(self, product: Optional[Product]):
        """ Elvégzi a feldolgozás utáni mentési műveleteket. """
        if not self._is_temp_mode_active and product:
            self.product_manager.add_or_update_product_sync(product)

    def _refresh_gallery(self):
        """ Frissíti a kép galériát az új képek megjelenítéséhez. """
        if not self._is_expanded:
            self._is_expanded = True
            self._update_expand_button_icon()

        self._clear_gallery_data()
        self._load_all_image_paths_for_current_product()
        self._display_current_images()
        self._scroll_to_position(0)
    
    @Slot(str, str, str)
    def _handle_image_deleted(self, tag: str, filename: str, product_id: str):
        target_dir, product = self._get_target_dir_and_product()
        if not target_dir: return

        image_to_delete_path = target_dir / filename
        pair_to_delete_path = self._find_pair_path(tag, filename, target_dir)
        pair_tag = "transparent_" if tag == "mixed_" else "mixed_" if tag == "transparent_" else None

        try:
            # Elsődleges fájl törlése
            if image_to_delete_path.exists():
                os.remove(image_to_delete_path)
                self._update_product_model_on_delete(product, tag)
                self._log(logging.INFO, f"Kép törölve: {filename}")
            else:
                 QMessageBox.warning(self, "Hiba", f"A '{filename}' képfájl nem található a törléshez.")

            # Pár fájl törlése, ha létezik
            if pair_to_delete_path and pair_to_delete_path.exists():
                os.remove(pair_to_delete_path)
                self._update_product_model_on_delete(product, pair_tag)
                self._log(logging.INFO, f"Kép párja törölve: {pair_to_delete_path.name}")
            
            # Újrasorszámozás
            self._renumber_images_in_category(tag, target_dir)
            if pair_tag:
                self._renumber_images_in_category(pair_tag, target_dir)

            # Véglegesítés és UI frissítés
            self._finalize_processing(product)
            self._refresh_gallery()

        except Exception as e:
            QMessageBox.critical(self, "Hiba", f"Nem sikerült törölni a képet vagy a párját: {e}")

    def _renumber_images_in_category(self, tag: str, image_dir: Path):
        files_to_renumber = []
        for f in image_dir.iterdir():
            if f.is_file() and f.name.lower().startswith(tag) and f.suffix.lower() in self.SUPPORTED_IMAGE_FORMATS:
                files_to_renumber.append(f)

        files_to_renumber.sort(key=lambda p: int(re.search(r'_(\d+)\.', p.name).group(1)) if re.search(r'_(\d+)\.', p.name) else 0)

        temp_renamed_files: List[Path] = []
        for i, old_path in enumerate(files_to_renumber):
            temp_name = image_dir / f"temp_{old_path.name}"
            try:
                old_path.rename(temp_name)
                temp_renamed_files.append(temp_name)
            except Exception as e:
                QMessageBox.critical(self, "Hiba", f"Nem sikerült ideiglenesen átnevezni a képet: {old_path.name}\nHiba: {e}")
                return

        for i, temp_path_for_new_name in enumerate(temp_renamed_files):
            new_filename = f"{tag}{i+1:03d}{temp_path_for_new_name.suffix.lower()}"
            new_path = image_dir / new_filename
            try:
                temp_path_for_new_name.rename(new_path)
            except Exception as e:
                QMessageBox.critical(self, "Hiba", f"Nem sikerült véglegesen átnevezni a képet: {temp_path_for_new_name.name}\nHiba: {e}")
                return

    def get_temporary_image_count(self) -> int:
        count = 0
        if self._tmp_image_dir.exists():
            for f in self._tmp_image_dir.iterdir():
                if f.is_file() and f.name.lower().startswith("mixed_") and f.suffix.lower() in self.SUPPORTED_IMAGE_FORMATS:
                    count += 1
        return count

    @Slot(str, str, str)
    def _handle_move_up_requested(self, tag: str, filename: str, product_id: str):
        self._move_image_within_category(tag, filename, product_id, -1)

    @Slot(str, str, str)
    def _handle_move_down_requested(self, tag: str, filename: str, product_id: str):
        self._move_image_within_category(tag, filename, product_id, 1)

    def _move_image_within_category(self, tag: str, filename: str, product_id: str, direction: int):
        target_dir, product = self._get_target_dir_and_product()
        if not target_dir: return

        # Ha original_ kép, a régi logika fut le
        if tag == "original_":
            self._perform_single_category_move(tag, filename, target_dir, product, direction)
            return
        
        # Ha transparent_ vagy mixed_, a szinkronizált logika fut le
        pair_tag = "transparent_" if tag == "mixed_" else "mixed_"
        
        # Fő kategória fájljainak összegyűjtése és rendezése
        primary_files = sorted([f for f in target_dir.iterdir() if f.is_file() and f.name.lower().startswith(tag)],
                               key=lambda p: int(re.search(r'_(\d+)\.', p.name).group(1)) or 0)
        
        # Pár kategória fájljainak összegyűjtése és rendezése
        pair_files = sorted([f for f in target_dir.iterdir() if f.is_file() and f.name.lower().startswith(pair_tag)],
                            key=lambda p: int(re.search(r'_(\d+)\.', p.name).group(1)) or 0)

        # Indexek meghatározása
        try:
            current_index = [f.name for f in primary_files].index(filename)
        except ValueError:
            QMessageBox.warning(self, "Hiba", f"A kép '{filename}' nem található a mozgatáshoz.")
            return

        new_index = current_index + direction
        if not (0 <= new_index < len(primary_files)):
            return # Érvénytelen mozgatás (lista elejére/végére ért)

        # A fájlok cseréje mindkét listában
        primary_files[current_index], primary_files[new_index] = primary_files[new_index], primary_files[current_index]
        # Ha a párok listája szinkronban van, ott is cserélünk
        if len(primary_files) == len(pair_files):
            pair_files[current_index], pair_files[new_index] = pair_files[new_index], pair_files[current_index]
        else:
            self._log(logging.WARNING, f"A '{tag}' és '{pair_tag}' kategóriák képszáma nem egyezik! Csak az egyik kategória lesz átrendezve.")

        # Átnevezési folyamat mindkét listára
        try:
            # Ideiglenes átnevezés mindkét kategóriában
            all_files_to_rename = primary_files + pair_files
            temp_map = {f.name: target_dir / f"temp_{f.name}" for f in all_files_to_rename}
            for f in all_files_to_rename: f.rename(temp_map[f.name])

            # Végleges átnevezés az új sorrend alapján
            for i, temp_ordered_file in enumerate(primary_files):
                new_name = f"{tag}{i+1:03d}{temp_ordered_file.suffix.lower()}"
                temp_map[temp_ordered_file.name].rename(target_dir / new_name)

            if len(primary_files) == len(pair_files):
                for i, temp_ordered_file in enumerate(pair_files):
                    new_name = f"{pair_tag}{i+1:03d}{temp_ordered_file.suffix.lower()}"
                    temp_map[temp_ordered_file.name].rename(target_dir / new_name)
            
            self._finalize_processing(product)
            self._refresh_gallery()

        except Exception as e:
            QMessageBox.critical(self, "Hiba", f"Nem sikerült szinkronban mozgatni a képeket: {e}")
            # Visszaállítási kísérlet hiba esetén
            for original_name, temp_path in temp_map.items():
                if temp_path.exists(): temp_path.rename(target_dir / original_name)
            self._refresh_gallery()

    def _perform_single_category_move(self, tag: str, filename: str, image_dir: Path, product: Optional[Product], direction: int):
        """A régi, csak egy kategóriát érintő mozgatási logika, 'original_' képekhez."""
        files_to_renumber = sorted([f for f in image_dir.iterdir() if f.is_file() and f.name.lower().startswith(tag)],
                                   key=lambda p: int(re.search(r'_(\d+)\.', p.name).group(1)) or 0)
        try:
            current_index = [f.name for f in files_to_renumber].index(filename)
        except ValueError: return

        new_index = current_index + direction
        if not (0 <= new_index < len(files_to_renumber)): return

        files_to_renumber.insert(new_index, files_to_renumber.pop(current_index))
        
        try:
            temp_map = {f.name: image_dir / f"temp_{f.name}" for f in files_to_renumber}
            for f in files_to_renumber: f.rename(temp_map[f.name])

            for i, temp_ordered_file in enumerate(files_to_renumber):
                new_name = f"{tag}{i+1:03d}{temp_ordered_file.suffix.lower()}"
                temp_map[temp_ordered_file.name].rename(image_dir / new_name)
            
            self._finalize_processing(product)
            self._refresh_gallery()
        except Exception as e:
            QMessageBox.critical(self, "Hiba", f"Hiba a kép mozgatásakor: {e}")
            for original_name, temp_path in temp_map.items():
                if temp_path.exists(): temp_path.rename(image_dir / original_name)
            self._refresh_gallery()

    def _scroll_to_position(self, position: int):
        if self.scroll_area and self.scroll_area.verticalScrollBar():
            self.scroll_area.verticalScrollBar().setValue(position)
        else:
            self._log(logging.WARNING, "Nem sikerült görgetősávot elérni.")

    def _find_pair_path(self, tag: str, filename: str, image_dir: Path) -> Optional[Path]:
        """
        Megkeresi egy 'transparent_' vagy 'mixed_' kép párját a sorszáma alapján.
        'original_' képekre vagy ha nincs pár, None-t ad vissza.
        """
        if tag == "original_":
            return None

        match = re.search(r'_(\d+)\.', filename)
        if not match:
            return None
        
        index_str = match.group(1)
        pair_tag = "transparent_" if tag == "mixed_" else "mixed_"
        
        # Keressük a párt a könyvtárban, függetlenül a kiterjesztéstől
        for f in image_dir.iterdir():
            if f.is_file() and f.name.lower().startswith(f"{pair_tag}{index_str}."):
                return f
        
        return None
    
    def _update_product_model_on_delete(self, product: Optional[Product], tag: str):
        """ Csökkenti a termék objektum képszámlálóját törléskor. """
        if self._is_temp_mode_active or not product:
            return

        if tag == "original_": product.num_original_images = max(0, product.num_original_images - 1)
        elif tag == "transparent_": product.num_transparent_images = max(0, product.num_transparent_images - 1)
        elif tag == "mixed_": product.num_mixed_images = max(0, product.num_mixed_images - 1)
        
        if not product.needs_upload:
            product.needs_upload = True

    @Slot(bool)
    def set_fb_selection_mode(self, active: bool):
        """
        Bekapcsolja a Facebook képválasztó módot:
        1. Lenyitja a galériát, ha zárva van (csak bekapcsoláskor).
        2. Megjeleníti/elrejti a jelölőnégyzeteket minden bélyegképen.
        """
        # 1. Ha aktiváljuk és nincs lenyitva, nyissuk le
        if active and not self._is_expanded:
            self._toggle_gallery_expansion()

        # 2. Iterálunk az összes widgeten és kapcsoljuk a módot
        for tag in self.IMAGE_TAG_ORDER:
            for widget in self._image_widgets[tag]:
                if isinstance(widget, ImageThumbnailWidget):
                    widget.set_selection_mode(active)

    @Slot(str, bool)
    def _handle_image_selection_toggled(self, filename: str, is_checked: bool):
        if not self._current_product_id:
            return
            
        product = self.product_manager.get_product_by_id(self._current_product_id)
        if not product:
            return

        # Biztosítjuk, hogy a facebook_data létezzen (elvileg a Product init kezeli, de biztos ami biztos)
        if not product.facebook_data:
            from models.product_model import FacebookData
            product.facebook_data = FacebookData()

        selected_list = product.facebook_data.selected_images

        if is_checked:
            if filename not in selected_list:
                selected_list.append(filename)
                self._log(logging.INFO, f"Kép kijelölve FB poszthoz: {filename}")
        else:
            if filename in selected_list:
                selected_list.remove(filename)
                self._log(logging.INFO, f"Kép kijelölés törölve: {filename}")