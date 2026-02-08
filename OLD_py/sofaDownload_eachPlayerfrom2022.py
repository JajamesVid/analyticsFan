from seleniumwire import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import json
import time
import os

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

    # Establecer User-Agent para Sofascore
    driver.execute_cdp_cmd('Network.setUserAgentOverride', {
        "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                     "AppleWebKit/537.36 (KHTML, like Gecko) "
                     "Chrome/120.0.0.0 Safari/537.36"
    })

    return driver

def scrape_sofascore_json(player_id, number):
    driver = start_browser()
    print(f"🌐 Abriendo URL de la API…")
    API_URL = f"https://www.sofascore.com/api/v1/player/{player_id}/events/last/{number}"
    driver.get(API_URL)

    time.sleep(5)  # Esperar que cargue completamente

    # Leer JSON de la página
    try:
        json_text = driver.find_element('tag name', 'pre').text
        data = json.loads(json_text)
    except Exception as e:
        print("❌ No se pudo obtener el JSON:", e)
        data = None

    driver.quit()
    return data

if __name__ == "__main__":
    # Solo un jugador (por ejemplo Mbappé)
    player_id = 85859 #868812
    player_name = "Griezmann" #"vinijr"

    for number in range(7):  # números 0 a 3
        print(f"📊 Obteniendo datos para {player_name}, número {number}")
        match_stats = scrape_sofascore_json(player_id, number)

        if match_stats:
            filename = f"{player_name}_{number}.json"
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(match_stats, f, indent=2, ensure_ascii=False)
            print(f"💾 Guardado en {filename}")
        else:
            print(f"⚠️ No se obtuvieron datos para número {number}")
