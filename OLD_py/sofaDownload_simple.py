from seleniumwire import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import json
import time
import os


#"https://www.sofascore.com/api/v1/event/14083158/player/826643/statistics" # Real Madrid celta
#OVERALL stats "https://www.sofascore.com/api/v1/player/826643/unique-tournament/8/season/77559/statistics/overall"

def start_browser():
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--headless=new")  # Cambiar a False para ver navegador

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )

    # Establecer User-Agent de navegador real para que Sofascore no bloquee
    driver.execute_cdp_cmd('Network.setUserAgentOverride', {
        "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                     "AppleWebKit/537.36 (KHTML, like Gecko) "
                     "Chrome/120.0.0.0 Safari/537.36"
    })

    return driver

def scrape_sofascore_json(player_id):
    driver = start_browser()
    print(f"🌐 Abriendo directamente la URL de la API…")
    API_URL = "https://www.sofascore.com/api/v1/event/14083139/player/"+str(player_id)+"/statistics"
    driver.get(API_URL)

    time.sleep(5)  # Esperar a que cargue completamente la respuesta

    # La respuesta JSON de Sofascore se guarda como texto en la página
    try:
        json_text = driver.find_element('tag name', 'pre').text  # La respuesta viene como <pre>JSON</pre>
        data = json.loads(json_text)
    except Exception as e:
        print("❌ No se pudo obtener el JSON:", e)

    driver.quit()
    return data

if __name__ == "__main__":
    
    FILENAME = "all_stats_madrid_girona.json"

    # --- 1. Crear archivo si no existe ---
    if not os.path.exists(FILENAME):
        with open(FILENAME, "w", encoding="utf-8") as f:
            json.dump({}, f, indent=2, ensure_ascii=False)
        print(f"📄 Archivo creado: {FILENAME}")

    # --- 2. Cargar datos existentes ---
    with open(FILENAME, "r", encoding="utf-8") as f:
        try:
            all_stats = json.load(f)
            print("📥 Datos cargados desde archivo")
        except:
            all_stats = {}
            print("⚠️ Archivo vacío o corrupto, inicializando dict vacío")

    # --- 3. Cargar jugadores ---
    with open("real_madrid_ids.json", "r", encoding="utf-8") as f:
        players = json.load(f)

    # --- 4. Loop scraping ---
    for name, player_id in players.items():
        print("Analyzing:", name, player_id)

        match_stats = scrape_sofascore_json(player_id)

        if match_stats:   # evitar guardar None
            all_stats[name] = match_stats
            print(f"✔️ Guardado: {name}")
        else:
            print(f"⚠️ Sin datos para {name}")

    # --- 5. Guardar resultados EN EL MISMO ARCHIVO ---
    with open(FILENAME, "w", encoding="utf-8") as f:
        json.dump(all_stats, f, indent=2, ensure_ascii=False)

    print(f"💾 Guardado en {FILENAME}")

