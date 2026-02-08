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
    chrome_options.add_argument("--headless=new")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )

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

    time.sleep(5)

    try:
        json_text = driver.find_element('tag name', 'pre').text
        data = json.loads(json_text)
    except Exception as e:
        print("❌ No se pudo obtener el JSON:", e)
        data = None

    driver.quit()
    return data


if __name__ == "__main__":
    player_id = 85859
    player_name = "Griezmann"

    all_stats = {}   # 👈 contenedor único

    for number in range(7):
        print(f"📊 Obteniendo datos para {player_name}, número {number}")

        match_stats = scrape_sofascore_json(player_id, number)

        if match_stats:
            all_stats[number] = match_stats   # 👈 acumulamos
        else:
            print(f"⚠️ No se obtuvieron datos para número {number}")

    # 👇 Guardar TODO en un solo archivo
    filename = f"{player_name}_all.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(all_stats, f, indent=2, ensure_ascii=False)

    print(f"💾 Todo guardado en {filename}")
