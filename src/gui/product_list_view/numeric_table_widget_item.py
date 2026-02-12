from PySide6.QtWidgets import QTableWidgetItem
from PySide6.QtCore import Qt

class NumericTableWidgetItem(QTableWidgetItem):
   
    def __init__(self, text: str, data: float | int | None = None, role=Qt.DisplayRole):
        super().__init__(text, role)
       
        if data is not None:
            self.setData(Qt.UserRole, data)
        elif text:
            try:
                cleaned_text = text.replace(' ', '').replace('Ft', '').replace('$', '').strip()
                self.setData(Qt.UserRole, float(cleaned_text) if '.' in cleaned_text else int(cleaned_text))
            except ValueError:
                self.setData(Qt.UserRole, None)
        else:
            self.setData(Qt.UserRole, None)

    def __lt__(self, other: QTableWidgetItem) -> bool:
        self_data = self.data(Qt.UserRole)
        other_data = other.data(Qt.UserRole)

        if self_data is None and other_data is None:
            return False
        if self_data is None:
            return False
        if other_data is None:
            return True

        return self_data < other_data