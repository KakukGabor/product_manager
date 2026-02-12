# src/config/folder_config.py

# --- MAPPANEVEK KONSTANSKÉNT ---
FOLDER_APP_DATA = "app_data_storage"
FOLDER_CHROME_PROFILE = "chrome_profile"
FOLDER_IMAGE_BACKGROUNDS = "image_backgrounds"
FOLDER_PROCESSED = "processed"
FOLDER_PRODUCT_LIBRARY = "product_library"
FOLDER_RAW = "raw"
FOLDER_RAW_GS = "galeria_savaria"
FOLDER_RAW_JF = "jofogas"
FOLDER_TEMP_FILES = "temp_files"
FOLDER_TEXT_SAVES = "text_editor_saves"


# --- A STRUKTÚRA MOST MÁR A KONSTANSOKBÓL ÉPÜL FEL ---
APP_FOLDER_STRUCTURE = {
    FOLDER_APP_DATA: {
        FOLDER_CHROME_PROFILE: {},
        FOLDER_IMAGE_BACKGROUNDS: {},
        FOLDER_PROCESSED: {
            FOLDER_PRODUCT_LIBRARY: {}
        },
        FOLDER_RAW: {
            FOLDER_RAW_GS: {},
            FOLDER_RAW_JF: {}
        },
        FOLDER_TEMP_FILES: {},
        FOLDER_TEXT_SAVES: {}
    }
}