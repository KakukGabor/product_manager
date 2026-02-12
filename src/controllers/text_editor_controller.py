# src/controllers/text_editor_controller.py
import logging
from typing import Optional
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QFileDialog, QMessageBox

from managers.settings_manager import SettingsManager
from managers.resource_manager import ResourceManager
from gui.text_editor.text_editor_dialog import TextEditorDialog

logger = logging.getLogger(__name__)

class TextEditorController(QObject):
    statusUpdated = Signal(str, int, object)
    editorClosed = Signal()

    def __init__(self, settings_manager: SettingsManager, resource_manager: ResourceManager, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.resource_manager = resource_manager
        self._dialog: Optional[TextEditorDialog] = None

        self._save_dir = self.settings_manager.app_root / "app_data_storage" / "text_editor_saves"
        self._autosave_path = self._save_dir / "autosave.html"
        self._current_filepath: Path = self._autosave_path

    @Slot()
    def show_editor(self, initial_content: Optional[str] = None):
        """
        Megjeleníti a szövegszerkesztőt.
        - Ha kap `initial_content`-et, azzal indul, és MÓDOSÍTOTTNAK jelöli.
        - Ha nem kap, az autosave fájl tartalmát tölti be MÓDOSÍTATLANként.
        """
        if not self._dialog:
            self._dialog = TextEditorDialog(
                self.settings_manager,
                self.resource_manager,
                parent=None 
            )
            self._dialog.saveRequested.connect(self._handle_save_request)
            self._dialog.loadRequested.connect(self._handle_load_request)
            # --- JAVÍTÁS: Az új, okosabb mentési metódushoz kötjük ---
            self._dialog.closingWithUnsavedChanges.connect(self._handle_save_on_close)
            self._dialog.finished.connect(self._on_dialog_finished)

        if initial_content is not None:
            self._dialog.set_content(initial_content)
            self._dialog.editor_widget.text_edit.document().setModified(True)
            
            # A riportok és egyéb ideiglenes tartalmak mindig az autosave-be kerüljenek
            self._current_filepath = self._autosave_path
            self._update_dialog_title()
            logger.info("Szövegszerkesztő megnyitva induló tartalommal (automatikus mentésbe fog kerülni).")

        else:
            try:
                if self._autosave_path.exists():
                    with open(self._autosave_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    self._dialog.set_content(content, mark_as_unmodified=True)
                    logger.info("Automatikus mentés betöltve.")
                else:
                    self._dialog.set_content("", mark_as_unmodified=True)
            except Exception as e:
                logger.warning(f"Nem sikerült betölteni az automatikus mentést: {e}")
                self._dialog.set_content("")

            # Induláskor, ha nem töltünk be fájlt, az autosave az aktív
            self._current_filepath = self._autosave_path
            self._update_dialog_title()
        
        self._dialog.show()
        self._dialog.raise_()
        self._dialog.activateWindow()

    @Slot(int)
    def _on_dialog_finished(self, result: int):
        logger.info("TextEditor dialógus bezárult.")
        self.editorClosed.emit()

    def _update_dialog_title(self):
        if not self._dialog:
            return
        if self._current_filepath == self._autosave_path:
            self._dialog.setWindowTitle("Szövegszerkesztő (Automatikus mentés)")
        else:
            self._dialog.setWindowTitle(f"Szövegszerkesztő - {self._current_filepath.name}")

    @Slot()
    def _handle_save_request(self):
        if not self._dialog: return

        if self._current_filepath == self._autosave_path:
            file_path_str, _ = QFileDialog.getSaveFileName(
                self._dialog, "Fájl mentése másként", str(self._save_dir), "HTML Fájlok (*.html);;Minden fájl (*.*)"
            )
            if not file_path_str: return

            target_path = Path(file_path_str)
            try:
                with open(target_path, "w", encoding="utf-8") as f:
                    f.write(self._dialog.get_content())
                self._current_filepath = target_path
                self._update_dialog_title()
                self._dialog.editor_widget.text_edit.document().setModified(False)
                self.statusUpdated.emit(f"Fájl sikeresen mentve: {target_path.name}", logging.INFO, "green")
            except Exception as e:
                QMessageBox.critical(self._dialog, "Mentési Hiba", f"Hiba történt a fájl mentésekor:\n{e}")
                self.statusUpdated.emit("Hiba a fájl mentésekor!", logging.ERROR, "red")
        else:
            try:
                with open(self._current_filepath, "w", encoding="utf-8") as f:
                    f.write(self._dialog.get_content())
                self._dialog.editor_widget.text_edit.document().setModified(False)
                self.statusUpdated.emit(f"Fájl sikeresen frissítve: {self._current_filepath.name}", logging.INFO, "green")
            except Exception as e:
                QMessageBox.critical(self._dialog, "Mentési Hiba", f"Hiba történt a fájl felülírásakor:\n{e}")
                self.statusUpdated.emit("Hiba a fájl felülírásakor!", logging.ERROR, "red")

    @Slot()
    def _handle_load_request(self):
        if not self._dialog: return

        if self._dialog.editor_widget.text_edit.document().isModified():
            reply = QMessageBox.question(self._dialog, "Mentetlen változások",
                                         "Vannak mentetlen változások. Biztosan új fájlt töltesz be?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                return

        file_path_str, _ = QFileDialog.getOpenFileName(
            self._dialog, "Fájl megnyitása", str(self._save_dir), "HTML Fájlok (*.html);;Minden fájl (*.*)"
        )
        if not file_path_str: return

        target_path = Path(file_path_str)
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                content = f.read()
            self._dialog.set_content(content)
            self._current_filepath = target_path
            self._update_dialog_title()
            self.statusUpdated.emit(f"Fájl betöltve: {target_path.name}", logging.INFO, "blue")
        except Exception as e:
            QMessageBox.critical(self._dialog, "Betöltési Hiba", f"Hiba történt a fájl betöltésekor:\n{e}")
            self.statusUpdated.emit("Hiba a fájl betöltésekor!", logging.ERROR, "red")

    # --- JAVÍTÁS: Ez az új, okosabb mentési metódus ---
    @Slot(str)
    def _handle_save_on_close(self, content: str):
        """
        A dialógus bezárásakor elmenti a tartalmat a megfelelő helyre:
        - Ha egyedi fájl van megnyitva, akkor azt írja felül.
        - Ha nincs, akkor az automatikus mentésbe ment.
        """
        target_path = self._current_filepath
        
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(content)
            
            if target_path == self._autosave_path:
                log_message = f"Tartalom automatikusan mentve ide: {target_path.name}"
                status_message = "Változások automatikusan mentve."
                status_color = None
            else:
                log_message = f"Változások mentve a(z) '{target_path.name}' fájlba bezáráskor."
                status_message = f"'{target_path.name}' frissítve."
                status_color = "blue"

            logger.info(log_message)
            self.statusUpdated.emit(status_message, logging.INFO, status_color)

        except Exception as e:
            logger.error(f"Hiba a mentéskor bezáráskor ({target_path}): {e}", exc_info=True)
            self.statusUpdated.emit(f"Hiba a(z) '{target_path.name}' mentésekor!", logging.ERROR, "red")
