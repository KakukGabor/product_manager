import google.generativeai as genai
import json
import os

# --- BEÁLLÍTÁSOK ---
# A szkript feltételezi, hogy a settings.json a mappában van.
SETTINGS_FILE_PATH = 'settings.json'
# --- VÉGE ---

print("Csatlakozás a Google API-hoz...")

api_key = None
try:
    with open(SETTINGS_FILE_PATH, 'r') as f:
        settings = json.load(f)
        api_key = settings.get('ai_settings', {}).get('google_api_key')
except FileNotFoundError:
    print(f"Hiba: A '{SETTINGS_FILE_PATH}' fájl nem található.")
except Exception as e:
    print(f"Hiba a beállítások olvasásakor: {e}")

if not api_key:
    print("Nincs érvényes API kulcs a beállításokban. A szkript leáll.")
else:
    try:
        genai.configure(api_key=api_key)

        print("\nElérhető modellek, amelyek támogatják a tartalomgenerálást ('generateContent'):")
        print("-------------------------------------------------------------------------")
        
        found_model = False
        for m in genai.list_models():
            # Csak azokat a modelleket listázzuk, amik tudnak szöveget generálni
            if 'generateContent' in m.supported_generation_methods:
                print(f"- {m.name}")
                found_model = True

        if not found_model:
            print("Nem található egyetlen használható modell sem.")

        print("-------------------------------------------------------------------------")

    except Exception as e:
        print(f"\nHiba történt a modellek listázásakor: {e}")