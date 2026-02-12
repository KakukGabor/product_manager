# src/automation/sites/jf_core/jf_product_locator.py
import logging
import math
import asyncio
from typing import Callable

from playwright.async_api import Page, TimeoutError
from models.product_model import Product

class JofogasProductLocator:
    """
    Ez az osztály felelős egy hirdetés félautomata megkereséséért, görgetéséért
    és vizuális kiemeléséért a Jófogás "Hirdetéseim" oldalán.
    """
    ITEMS_PER_PAGE = 10

    def __init__(self, log_callback: Callable[..., None]):
        self.log = log_callback

    async def locate_and_highlight(self, page: Page, product: Product):
        """
        A fő végrehajtó metódus. Siker esetén lefut, hiba esetén kivételt dob.
        """
        if not product.jf_position:
            raise RuntimeError("A termékhez nincs elmentett Jófogás pozíció. Futtasson egy adatkinyerést!")
        
        # Rövid várakozás, hogy az oldal biztosan stabilizálódjon a hívás előtt.
        await page.wait_for_timeout(1500)

        # 1. Céloldal kiszámítása és naplózás
        target_page = math.ceil(product.jf_position / self.ITEMS_PER_PAGE)
        self.log(f"Navigálás a(z) {target_page}. Jófogás oldalra...", logging.INFO, "processing")

        # 2. Aktuális oldalszám meghatározása
        try:
            current_page_text = await page.locator("li.pagination-page.active a").text_content(timeout=5000)
            current_page = int(current_page_text)
        except (ValueError, TimeoutError):
            current_page = 1

        # 3. Lapozás a céloldalra a LEegyszerűsített logikával
        while current_page < target_page:
            try:
                # Rákattintunk a "Következő" gombra
                await page.locator("li.pagination-next:not(.disabled) a").click()

                # === A DÖNTŐ VÁLTOZTATÁS: FIX IDEJŰ VÁRAKOZÁS ===
                # Várunk 2 másodpercet, hogy az oldalnak legyen ideje frissíteni a tartalmát.
                # Ez helyettesíti a megbízhatatlan "detached" várakozást.
                await page.wait_for_timeout(2000)

                current_page += 1
            except (TimeoutError, Exception) as e:
                 raise RuntimeError(f"Hiba a(z) {current_page + 1}. oldalra lapozáskor: {e}")

        # 4. A termék megkeresése, kiemelése és hibakezelés
        row_handle = None
        try:
            # Biztonsági várakozás a keresés előtt.
            await page.wait_for_timeout(1000)

            findRowByTitlePartsAndPriceJs = r"""
                (args) => {
                    const productTitle = args.productTitle.toLowerCase();
                    const productPrice = args.productPrice;
                    const searchWords = productTitle.replace(/[.,\/#!$%\^&\*;:{}=\-_`~()]/g, "").split(/\s+/).filter(word => word.length > 2);

                    const adElements = document.querySelectorAll('.jfg-item.my-item');
                    for (const adElement of adElements) {
                        const titleElement = adElement.querySelector('.my-item-subject .subject');
                        const priceElement = adElement.querySelector('.my-item-price .price');

                        if (titleElement && priceElement) {
                            const adTitle = titleElement.textContent.trim().toLowerCase();
                            const titleMatch = searchWords.every(word => adTitle.includes(word));
                            const adPriceRaw = priceElement.textContent || '';
                            const adPriceClean = adPriceRaw.replace(/\D/g, '');
                            const adPriceNumeric = parseFloat(adPriceClean);
                            const priceMatch = Math.abs(adPriceNumeric - productPrice) < 0.01;

                            if (titleMatch && priceMatch) {
                                return adElement;
                            }
                        }
                    }
                    return null;
                }
            """
            
            row_handle = await page.evaluate_handle(
                findRowByTitlePartsAndPriceJs, 
                { "productTitle": product.title, "productPrice": product.price_numeric }
            )

            if await row_handle.evaluate("element => !element"):
                 raise RuntimeError(f"A(z) '{product.title}' című, {product.price_numeric} Ft árú termék nem található a várt ({target_page}.) oldalon.")

            # Görgetés és vizuális kiemelés (változatlan)
            await page.evaluate("(element) => { element.scrollIntoView({ behavior: 'smooth', block: 'center' }); }", row_handle)
            await page.evaluate("""
                (element) => {
                    const originalColor = element.style.backgroundColor;
                    const highlightColor = '#FFD700';
                    element.style.transition = 'background-color 0.2s ease-in-out';
                    let count = 0;
                    const intervalId = setInterval(() => {
                        element.style.backgroundColor = (count % 2 === 0) ? highlightColor : originalColor;
                        count++;
                        if (count > 5) { clearInterval(intervalId); element.style.backgroundColor = highlightColor; }
                    }, 300);
                }
            """, row_handle)
            
        finally:
            if row_handle:
                await row_handle.dispose()