# src/automation/sites/gs_core/gs_product_locator.py
import logging
from typing import Callable

from playwright.async_api import Page
from models.product_model import Product

class GaleriaSavariaProductLocator:
    """
    Ez az osztály felelős egy termék félautomata megkereséséért, görgetéséért
    és vizuális kiemeléséért a Galéria Savaria oldalon.
    """
    def __init__(self, log_callback: Callable[..., None]):
        """
        Inicializálás.
        :param log_callback: Egy függvény, amivel a státuszüzeneteket lehet naplózni.
        """
        # A log_callback itt megmarad a jövőbeli bővíthetőség és a
        # többi core komponenssel való konzisztencia érdekében.
        self.log = log_callback

    async def locate_and_highlight(self, page: Page, product: Product):
        """
        A fő végrehajtó metódus. Siker esetén lefut, hiba esetén kivételt dob.
        """
        row_handle = None
        try:
            # 1. Explicit várakozás a táblázatra
            await page.wait_for_selector("table.table_full tbody", state="visible", timeout=10000)

            # 2. JavaScript funkció a sor megkereséséhez a termékkód alapján
            findRowByProductIdJs = """
                (productId) => {
                    const rows = document.querySelectorAll('table.table_full tbody > tr[class^="prod"]');
                    for (const row of rows) {
                        const codeElement = row.querySelector('td:nth-child(3) div.view_full.mt5');
                        if (codeElement && codeElement.textContent.includes(`Termékkód: ${productId}`)) {
                            return row;
                        }
                    }
                    return null;
                }
            """
            row_handle = await page.evaluate_handle(findRowByProductIdJs, product.id)

            # Ha a handle érvénytelen, kivételt dobunk, amit a hívó fog elkapni
            if await row_handle.evaluate("element => !element"):
                 raise RuntimeError(f"A(z) '{product.id}' azonosítójú termék nem található az oldalon.")

            # 3. Görgetés
            await page.evaluate(
                "(element) => { element.scrollIntoView({ behavior: 'smooth', block: 'center' }); }", 
                row_handle
            )
            
            # 4. Vizuális kiemelés
            await page.evaluate("""
                (element) => {
                    const originalColor = element.style.backgroundColor;
                    const highlightColor = '#FFD700';
                    element.style.transition = 'background-color 0.2s ease-in-out';
                    let count = 0;
                    const intervalId = setInterval(() => {
                        element.style.backgroundColor = (count % 2 === 0) ? highlightColor : originalColor;
                        count++;
                        if (count > 5) {
                            clearInterval(intervalId);
                            element.style.backgroundColor = highlightColor; 
                        }
                    }, 300);
                }
            """, row_handle)
            
            # Ha idáig eljutott, a művelet sikeres, nincs szükség visszatérési értékre.
            
        finally:
            # A 'finally' blokk biztosítja, hogy a handle erőforrás mindig felszabaduljon.
            if row_handle:
                await row_handle.dispose()