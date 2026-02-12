# src/gui/utils/formatters.py
from PySide6.QtWidgets import QLineEdit
from PySide6.QtCore import QLocale

def format_numeric_input(line_edit: QLineEdit):
    """
    Formázza a megadott QLineEdit tartalmát valós időben, magyar ezres
    elválasztókkal, és intelligensen kezeli a kurzor pozícióját.
    Csak számjegyeket engedélyez.
    """
    if not line_edit.isEnabled():
        return

    locale = QLocale(QLocale.Hungarian)
    original_text = line_edit.text()
    cursor_pos = line_edit.cursorPosition()

    # Csak a számjegyeket tartjuk meg
    cleaned_text = "".join(filter(str.isdigit, original_text))
    if not cleaned_text:
        # Ha a felhasználó mindent kitöröl, hagyjuk üresen a mezőt
        if original_text: # Csak akkor írjunk, ha tényleg volt változás
            line_edit.blockSignals(True)
            line_edit.setText("")
            line_edit.blockSignals(False)
        return

    try:
        value = int(cleaned_text)
        formatted_text = locale.toString(value)

        # Ha a formázott szöveg megegyezik az eredetivel, nincs teendő
        if formatted_text == original_text:
            return

        # A kurzor pozíciójának intelligens visszaállítása
        # Számoljuk meg az ezres elválasztókat a kurzor előtt az eredeti és az új szövegben
        separators_before_cursor_original = original_text[:cursor_pos].count(locale.groupSeparator())
        
        # Ideiglenesen beállítjuk a szöveget, hogy megtaláljuk az új kurzorpozíciót
        line_edit.blockSignals(True)
        line_edit.setText(formatted_text)
        line_edit.blockSignals(False)
        
        # Megkeressük a kurzor új helyét
        # Számoljuk a számjegyeket az eredeti szövegben a kurzorig
        digits_before_cursor = len("".join(filter(str.isdigit, original_text[:cursor_pos])))
        
        new_cursor_pos = 0
        digits_counted = 0
        for char in formatted_text:
            new_cursor_pos += 1
            if char.isdigit():
                digits_counted += 1
            if digits_counted == digits_before_cursor:
                # Ha a következő karakter egy elválasztó, ugorjunk utána
                if new_cursor_pos < len(formatted_text) and formatted_text[new_cursor_pos] == locale.groupSeparator():
                    new_cursor_pos +=1
                break
        
        line_edit.setCursorPosition(new_cursor_pos)

    except (ValueError, TypeError):
        # Ha a konverzió valamiért hibára fut, nem csinálunk semmit
        pass