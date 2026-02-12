import logging
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QWidget
from PySide6.QtCore import Signal, Slot, QRect
from PySide6.QtGui import QCloseEvent
from managers.settings_manager import SettingsManager
from managers.resource_manager import ResourceManager
from .text_editor_widget import TextEditorWidget

logger = logging.getLogger(__name__)

# === JAVÍTÁS KEZDETE: Új stíluslap a FilterDialog mintájára ===
TEXT_EDITOR_STYLESHEET = """
    #textEditorDialog {
        background-color: #F0F8FF;
        border: 1px solid #4682B4;
    }
    #buttonContainer {
        background-color: #A0C4FF;
        border-top: 1px solid #8FAADC;
    }
    QPushButton {
        padding: 8px 20px;
        border: 1px solid #777;
        border-radius: 4px;
        font-size: 10pt;
        background-color: #F0F0F0;
    }
    QPushButton:hover {
        background-color: #E0E0E0;
    }
    /* A "Bezárás" gomb megkapja a szűrő "Alkalmaz" gombjának kék stílusát */
    #closeButton {
        font-weight: bold;
        background-color: #007bff;
        color: white;
        border-color: #0056b3;
    }
    #closeButton:hover {
        background-color: #0069d9;
    }
"""
# === JAVÍTÁS VÉGE ===

class TextEditorDialog(QDialog):
    saveRequested = Signal()
    loadRequested = Signal()
    closingWithUnsavedChanges = Signal(str)

    def __init__(self, settings_manager: SettingsManager, resource_manager: ResourceManager, parent: QWidget | None = None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.setWindowTitle("Szövegszerkesztő")
        
        # === JAVÍTÁS: Stíluslap és objectName-ek beállítása ===
        self.setObjectName("textEditorDialog")
        self.setStyleSheet(TEXT_EDITOR_STYLESHEET)
        # === JAVÍTÁS VÉGE ===

        main_layout = QVBoxLayout(self)

        self.editor_widget = TextEditorWidget(settings_manager, resource_manager, self)
        main_layout.addWidget(self.editor_widget)

        button_container = QWidget()
        # === JAVÍTÁS: ObjectName a célzott stílushoz ===
        button_container.setObjectName("buttonContainer")
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(15, 8, 15, 8) # Margók hozzáadva a szebb kinézethez

        self.close_button = QPushButton("Bezárás")
        # === JAVÍTÁS: ObjectName a célzott stílushoz ===
        self.close_button.setObjectName("closeButton")

        self.cancel_button = QPushButton("Mégse")
        self.cancel_button.setObjectName("cancelButton") # Konzisztencia kedvéért

        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.close_button)
        main_layout.addWidget(button_container)

        self.close_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

        self.editor_widget.saveRequested.connect(self.saveRequested.emit)
        self.editor_widget.loadRequested.connect(self.loadRequested.emit)

        self._restore_state()

    def _restore_state(self):
        try:
            geometry_data = self.settings_manager.get_setting("text_editor_settings.geometry")
            if isinstance(geometry_data, list) and len(geometry_data) == 4:
                self.setGeometry(QRect(*geometry_data))
            else:
                self.resize(800, 600)
                if self.parent():
                    parent_rect = self.parent().geometry()
                    self_rect = self.frameGeometry()
                    self.move(parent_rect.center() - self_rect.center())
        except Exception as e:
            logger.error(f"TextEditorDialog: Hiba a geometria betöltésekor: {e}", exc_info=True)
            self.resize(800, 600)

    def _save_state(self):
        try:
            geom = self.geometry()
            geometry_data = [geom.x(), geom.y(), geom.width(), geom.height()]
            self.settings_manager.set_setting("text_editor_settings.geometry", geometry_data)
        except Exception as e:
            logger.error(f"TextEditorDialog: Hiba a geometria mentésekor: {e}", exc_info=True)

    def closeEvent(self, event: QCloseEvent):
        self._save_state()
        if self.editor_widget.text_edit.document().isModified():
            self.closingWithUnsavedChanges.emit(self.editor_widget.get_content())
        super().closeEvent(event)

    def set_content(self, html_content: str, mark_as_unmodified: bool = False):
        self.editor_widget.set_content(html_content)
        if mark_as_unmodified:
            self.editor_widget.text_edit.document().setModified(False)

    def get_content(self) -> str:
        return self.editor_widget.get_content()