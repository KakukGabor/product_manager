# src/converter_mixed_to_webp.py

import sys
from pathlib import Path

# Szükségünk van a QApplication-re, mert a QImage használatához
# kell egy futó Qt alkalmazás-példány a háttérben.
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage

# --- KONFIGURÁCIÓ ---
# Ellenőrizd, hogy ez az útvonal helyes-e a te projektstruktúrádban!
# A szkriptet a projekt gyökeréből kell futtatni (a 'src' mappa szülőjéből).
PRODUCT_LIBRARY_PATH = Path("app_data_storage/processed/product_library")
# --------------------

def convert_all_mixed_images():
    """
    Végigmegy az összes termékmappán, megkeresi a 'mixed_*.jpg' fájlokat,
    átkonvertálja őket 'mixed_*.webp' formátumba, majd törli az eredeti JPG-t.
    """
    if not PRODUCT_LIBRARY_PATH.is_dir():
        print(f"HIBA: A termékkönyvtár nem található a megadott útvonalon: '{PRODUCT_LIBRARY_PATH.resolve()}'")
        print("Kérlek, ellenőrizd a PRODUCT_LIBRARY_PATH változót a szkriptben.")
        return

    print("--- Mixed JPG -> WebP Konverter Indítása ---")
    print(f"Forrás könyvtár: {PRODUCT_LIBRARY_PATH.resolve()}")

    # Az összes 'mixed_*.jpg' fájl rekurzív megkeresése
    jpg_files_to_convert = list(PRODUCT_LIBRARY_PATH.rglob("mixed_*.jpg"))

    if not jpg_files_to_convert:
        print("\nNem található egyetlen 'mixed_*.jpg' fájl sem a konvertáláshoz. Lehet, hogy már minden át van alakítva.")
        return

    print(f"\n{len(jpg_files_to_convert)} db 'mixed_*.jpg' fájl konvertálása következik...")

    converted_count = 0
    skipped_count = 0
    error_count = 0

    for i, jpg_path in enumerate(jpg_files_to_convert):
        # Az új, .webp kiterjesztésű fájlnév generálása
        webp_path = jpg_path.with_suffix('.webp')

        # Biztonsági ellenőrzés: ha a WebP verzió már létezik, kihagyjuk
        if webp_path.exists():
            print(f"({i+1}/{len(jpg_files_to_convert)}) KIHAGYVA: '{webp_path.name}' már létezik.")
            skipped_count += 1
            continue

        try:
            # Kép betöltése a QImage segítségével
            image = QImage(str(jpg_path))
            if image.isNull():
                print(f"(!) HIBA: Nem sikerült betölteni a képet: {jpg_path}")
                error_count += 1
                continue

            # Mentés WebP formátumban, 85-ös minőséggel (jó kompromisszum)
            if image.save(str(webp_path), "WEBP", 85):
                # Ha a mentés sikeres, töröljük az eredeti JPG fájlt
                jpg_path.unlink()
                print(f"-> SIKER ({i+1}/{len(jpg_files_to_convert)}): '{jpg_path.name}' -> '{webp_path.name}'")
                converted_count += 1
            else:
                print(f"(!) HIBA: A WebP mentés sikertelen: {webp_path}")
                error_count += 1

        except Exception as e:
            print(f"(!) VÁRATLAN HIBA a(z) '{jpg_path.name}' feldolgozása közben: {e}")
            error_count += 1

    print("\n--- Konverzió Befejeződött ---")
    print(f"Sikeresen átalakítva: {converted_count} fájl")
    print(f"Kihagyva (már létezett): {skipped_count} fájl")
    print(f"Hibás: {error_count} fájl")
    print("---------------------------------")


if __name__ == "__main__":
    # A QImage helyes működéséhez létre kell hozni egy QApplication példányt.
    app = QApplication(sys.argv)
    
    convert_all_mixed_images()
    
    # Nincs szükség az app.exec()-re, a szkript lefutása után kiléphet.