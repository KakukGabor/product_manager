# src/gui/widgets/formatted_double_spinbox.py
from PySide6.QtWidgets import QDoubleSpinBox
from PySide6.QtCore import QLocale
from PySide6.QtGui import QValidator

class FormattedDoubleSpinBox(QDoubleSpinBox):
    """
    Egy QDoubleSpinBox alosztály, amely magyar ezres elválasztókat használ
    és helyesen kezeli a bevitelt és a fókuszvesztést.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setLocale(QLocale(QLocale.Hungarian))
        # Ez a beállítás önmagában nem elég, a validálást is kezelni kell.
        self.setGroupSeparatorShown(True)

    def validate(self, input_str: str, pos: int) -> tuple[QValidator.State, str, int]:
        """
        Felüldefiniálja a validátort, hogy elfogadja az ezres elválasztókat
        és az üres stringet is gépelés közben.
        """
        # Az üres stringet engedélyezzük, ez egy elfogadható köztes állapot.
        if not input_str:
            return (QValidator.State.Intermediate, input_str, pos)

        # Megpróbáljuk a szöveget számmá alakítani a magyar lokálé szerint.
        # Ez a hívás kezeli az ezres elválasztókat (szóközöket).
        _, ok = self.locale().toDouble(input_str)

        if ok:
            # Ha a konverzió sikeres, a szöveg elfogadható.
            return (QValidator.State.Acceptable, input_str, pos)
        
        # Ha a konverzió nem sikerül, az lehet azért, mert a felhasználó
        # éppen egy szám közepén tart (pl. "1 23"). Ezt engedélyezzük
        # köztes állapotként, hogy folytathassa a gépelést.
        return (QValidator.State.Intermediate, input_str, pos)

    def textFromValue(self, value: float) -> str:
        """A numerikus értékből a megjelenítendő szöveget hozza létre."""
        # Egyszerűen használjuk a lokálé szerinti formázást.
        return self.locale().toString(value, 'f', self.decimals())

    def valueFromText(self, text: str) -> float:
        """A beírt szövegből (ami lehet formázott is) hozza létre a numerikus értéket."""
        # Az üres szöveg értéke 0.0
        if not text:
            return 0.0
        return self.locale().toDouble(text)[0]