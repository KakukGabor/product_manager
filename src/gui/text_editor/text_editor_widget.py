# src/gui/text_editor/text_editor_widget.py
import logging
from typing import Optional
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextEdit
from PySide6.QtGui import QColor, QFont
from PySide6.QtCore import Qt, Slot, Signal, QTimer # <-- QTIMER IMPORTÁLÁSA

from gui.toolbar_widget.toolbar_widget import ToolbarWidget
from managers.settings_manager import SettingsManager
from managers.resource_manager import ResourceManager
from .special_character_dialog import SpecialCharacterDialog

logger = logging.getLogger(__name__)

class TextEditorWidget(QWidget):
    saveRequested = Signal()
    loadRequested = Signal()

    def __init__(self, settings_manager: SettingsManager, resource_manager: ResourceManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings_manager = settings_manager
        self._resource_manager = resource_manager
        self._special_char_dialog: Optional[SpecialCharacterDialog] = None

        self.setObjectName("textEditorWidget")
        self.setAutoFillBackground(True)

        self._setup_ui()
        self._connect_signals()
        self._update_formatting_buttons()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        self.setStyleSheet("#textEditorWidget { background-color: #DDDDDD; }")
        main_layout.setSpacing(0)

        toolbar_configs = self._resource_manager.get_toolbar_config("text_editor_toolbar")
        self.toolbar = ToolbarWidget(
            self._settings_manager,
            toolbar_configs,
            orientation=Qt.Orientation.Horizontal,
            settings_key="text_editor_settings.toolbar_button_order",
            parent=self
        )
        
        self.toolbar.set_toolbar_background_color(QColor("#4682B4"))
        self.toolbar.set_highlighted_slot_color(QColor(180, 200, 220, 120))
        self.toolbar.set_button_background_color(QColor("#A0C4FF"))

        self.text_edit = QTextEdit(self)
        self.text_edit.setStyleSheet("background-color: #F0F8FF; color: #000000; border: 1px solid #B0C4DE;")

        main_layout.addWidget(self.toolbar)
        main_layout.addWidget(self.text_edit)

    def _connect_signals(self) -> None:
        self.toolbar.buttonClicked.connect(self._handle_toolbar_button_click)
        self.text_edit.selectionChanged.connect(self._update_formatting_buttons)

    @Slot(str)
    def _handle_toolbar_button_click(self, button_id: str) -> None:
        if button_id == "bold_btn":
            self.toggle_bold()
        elif button_id == "save_btn":
            self.saveRequested.emit()
        elif button_id == "load_btn":
            self.loadRequested.emit()
        elif button_id == "special_chr_btn":
            self._open_special_character_dialog()

    def set_content(self, html_content: str) -> None:
        self.text_edit.setHtml(html_content)
        
    def get_content(self) -> str:
        return self.text_edit.toHtml()

    def toggle_bold(self) -> None:
        is_bold = self.text_edit.fontWeight() > QFont.Weight.Normal
        self.text_edit.setFontWeight(QFont.Weight.Normal if is_bold else QFont.Weight.Bold)

    @Slot()
    def _update_formatting_buttons(self) -> None:
        cursor = self.text_edit.textCursor()
        char_format = cursor.charFormat()
        is_bold = char_format.fontWeight() > QFont.Weight.Normal
        self.toolbar.set_button_on_state("bold_btn", is_bold)

    def _open_special_character_dialog(self):
        """Megnyitja a speciális karaktereket tartalmazó dialógusablakot."""
        if not self._special_char_dialog:
            self._special_char_dialog = SpecialCharacterDialog(self)
            self._special_char_dialog.characterSelected.connect(self._insert_special_character)

        self._special_char_dialog.open()

    @Slot(str)
    def _insert_special_character(self, character: str):
        """Beszúrja a kiválasztott karaktert a kurzor aktuális pozíciójába."""
        # 1. Kérjük a fókuszt
        self.text_edit.setFocus()
        
        # --- JAVÍTÁS ITT ---
        # 2. A beszúrást egy 0ms-os időzítőbe tesszük, ami megvárja,
        #    hogy az eseménykezelő feldolgozza a fókuszváltást.
        QTimer.singleShot(0, lambda: self.text_edit.insertPlainText(character))
        # --- JAVÍTÁS VÉGE ---