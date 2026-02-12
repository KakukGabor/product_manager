# src/managers/email_manager.py
import asyncio
import logging
import smtplib
import ssl
from email.message import EmailMessage
from typing import Optional, List
from pathlib import Path
import mimetypes

from PySide6.QtCore import QObject, Signal, Slot

from managers.settings_manager import SettingsManager
from automation.core.async_loop_worker import AsyncLoopWorker
from models.product_model import Product

logger = logging.getLogger(__name__)

class EmailManager(QObject):
    emailSent = Signal(bool, str)

    def __init__(self, settings_manager: SettingsManager, loop_worker: AsyncLoopWorker, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.loop_worker = loop_worker

    async def _send_email_with_attachments_async(self, sender: str, password: str, recipient: str, subject: str, body: str, attachment_paths: List[Path]):
        """Aszinkron metódus, ami elküldi az emailt a mellékletekkel együtt."""
        try:
            msg = EmailMessage()
            msg["From"] = sender
            msg["To"] = recipient
            msg["Subject"] = subject
            msg.set_content(body, subtype='html')

            for path in attachment_paths:
                ctype, encoding = mimetypes.guess_type(path)
                if ctype is None or encoding is not None:
                    ctype = 'application/octet-stream'
                maintype, subtype = ctype.split('/', 1)
                
                with open(path, 'rb') as fp:
                    msg.add_attachment(fp.read(),
                                       maintype=maintype,
                                       subtype=subtype,
                                       filename=path.name)
            
            logger.info(f"{len(attachment_paths)} kép csatolva az emailhez.")

            await asyncio.to_thread(
                self._smtp_worker,
                sender,
                password,
                recipient,
                msg
            )
            
            logger.info(f"Email sikeresen elküldve a(z) '{recipient}' címre mellékletekkel.")
            self.emailSent.emit(True, "Email sikeresen elküldve a képekkel.")

        except Exception as e:
            logger.error(f"Hiba az email küldésekor: {e}", exc_info=True)
            self.emailSent.emit(False, f"Hiba az email küldésekor: {e}")

    def _smtp_worker(self, sender: str, password: str, recipient: str, msg: EmailMessage):
        """Ez a metódus fut egy külön szálon, hogy ne blokkolja az async loop-ot."""
        context = ssl.create_default_context()
        server = None
        try:
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls(context=context)
            server.login(sender, password)
            server.send_message(msg)
        finally:
            if server:
                server.quit()

    @Slot(Product, str, list)
    def send_product_email_with_attachments_slot(self, product: Product, recipient_override: str, attachment_paths: List[Path]):
        """Slot, ami elindítja a levélküldést mellékletekkel."""
        sender_email = self.settings_manager.get_setting("email_settings.sender_email")
        app_password = self.settings_manager.get_setting("email_settings.app_password")
        recipient_email = recipient_override

        if not all([sender_email, app_password, recipient_email]):
            msg = "Hiányzó email beállítások (küldő, jelszó vagy címzett). Kérlek, add meg őket a Beállítások menüben!"
            self.emailSent.emit(False, msg)
            return

        subject = f"Termékadatlap: {product.title} (ID: {product.id})"
        price_str = f"{int(product.price_numeric):,} Ft".replace(',', ' ')
        attachment_notice = f"<p><b>A termékről {len(attachment_paths)} kép található a mellékletben.</b></p>" if attachment_paths else ""

        body = f"""
        <html>
        <head>
            <style>
                body {{ font-family: sans-serif; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #dddddd; text-align: left; padding: 8px; }}
                th {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
            <h2>Termékadatok: {product.title}</h2>
            {attachment_notice}
            <table>
                <tr><th>ID</th><td>{product.id}</td></tr>
                <tr><th>Ár</th><td>{price_str}</td></tr>
                <tr><th>Kategória</th><td>{product.main_category.display_name} > {product.product_type}</td></tr>
            </table>
            <h3>Leírás:</h3>
            <p>{product.description.replace('\n', '<br>') if product.description else 'Nincs leírás.'}</p>
        </body>
        </html>
        """

        coro = self._send_email_with_attachments_async(sender_email, app_password, recipient_email, subject, body, attachment_paths)
        self.loop_worker.run_coro_threadsafe(coro)