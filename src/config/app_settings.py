# src/config/settings_config.py
from pathlib import Path
from config.app_folders import (
    FOLDER_APP_DATA,
    FOLDER_IMAGE_BACKGROUNDS
)

def get_default_settings(app_root_path: Path) -> dict:
    """
    Visszaadja az alapértelmezett beállítások teljes struktúráját.
    A dinamikus útvonalakat a megadott 'app_root_path' alapján generálja.
    """
    # 1. A dinamikus értékek generálása itt, a függvényen belül történik.
    default_download_folder = str(Path.home())
    default_background_image_path = str(app_root_path / FOLDER_APP_DATA / FOLDER_IMAGE_BACKGROUNDS / "default_background.jpg")

    # 2. Visszaadjuk a teljes szótárat, már a helyes értékekkel.
    return {
        "version": "1.2",
        "general_settings": {
            "is_first_run": True,
            "last_run_date": ""
        },
        "client_settings": {
            "download_folder": default_download_folder,
            "main_splitter_sizes": [1, 1, 1],
            "list_view_sort_column": 6,
            "list_view_sort_order": 1,
            "list_view_font_size": 10,
            "list_view_row_padding": 8
        },
        "server_settings": {
            "website_url": "",
            "ftp_host": "",
            "ftp_user": "",
            "ftp_pass": "",
            "ftp_port": 22
        },
        "browser_settings": {
            "headless": False,
            "browser_type": "chromium",
            "auto_accept_cookies": True,
            "default_navigation_timeout_ms": 30000,
            "element_visibility_timeout_ms": 5000,
            "browser_close_timeout_s": 5,
            "post_action_delay_ms": 500,
            "cookie_acceptance_status": {}
        },
        "site_configs": {
            "galeria_savaria": {
                "button_target_url": "https://galeriasavaria.hu/",
                "products_url": "https://galeriasavaria.hu/felhasznalo/eladas/elado-termekeim/",
                "new_product_url": "https://galeriasavaria.hu/felhasznalo/eladas/uj-termek-feltoltese/alapadatok/"
            },
            "jofogas": {
                "button_target_url": "https://www.jofogas.hu/",
                "products_url": "https://www.jofogas.hu/fiok/hirdeteseim",
                "new_product_url": "https://www2.jofogas.hu/ai/form/1",
                "upload_success_url": "https://www2.jofogas.hu/ai/confirm/0"
            },
            "facebook": {
                "button_target_url": "https://www.facebook.com/",
                "page_id": "",
                "access_token": ""
            }
        },
        "image_settings": {
            "background_image_path": default_background_image_path
        },
        "ai_settings": {
            "google_api_key": "AIzaSyA_O-nZz5OnsSdLhRsTQbmx0mqWR02JvOA"
        },
        "email_settings": {
            "sender_email": "",
            "app_password": "",
            "recipient_email": ""
        },
        "text_editor_settings": {
            "geometry": None,
            "toolbar_button_order": [],
            "button_states": {}
        },
        "toolbar_button_order": []
    }