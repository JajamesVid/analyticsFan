from seleniumwire import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import json
import time
import os


# =========================
#  Browser
# =========================
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

    driver.execute_cdp_cmd(
        "Network.setUserAgentOverride",
        {
            "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/120.0.0.0 Safari/537.36"
        }
    )
    return driver


# =========================
#  Scraping
# =========================
def scrape_sofascore_json(driver, event_id, player_id):
    url = f"https://www.sofascore.com/api/v1/event/{event_id}/player/{player_id}/statistics"
    print(f"🌐 {url}")
    driver.get(url)

    time.sleep(2)

    try:
        json_text = driver.find_element("tag name", "pre").text
        return json.loads(json_text)
    except Exception as e:
        print(f"❌ Error leyendo JSON | evento {event_id} | jugador {player_id}: {e}")
        return None


# =========================
#  MAIN
# =========================
if __name__ == "__main__":

    # ---- cargar partidos ----
    with open("vinifrom2022_matchids.json", "r", encoding="utf-8") as f:
        resumen_partidos = json.load(f)

    # ---- cargar jugadores ----
    with open("test_ids.json", "r", encoding="utf-8") as f:
        players = json.load(f)

    # ---- carpeta salida ----
    OUTPUT_FOLDER = "player_stats"
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    # ---- iniciar navegador UNA VEZ ----
    driver = start_browser()

    try:
        for player_name, player_id in players.items():
            print(f"\n🔹 Procesando jugador: {player_name} ({player_id})")

            output_file = os.path.join(
                OUTPUT_FOLDER,
                f"{player_name}_all_matches.json"
            )

            # cargar datos existentes
            if os.path.exists(output_file):
                with open(output_file, "r", encoding="utf-8") as f:
                    all_stats = json.load(f)
            else:
                all_stats = {}

            # ---- loop partidos ----
            for event_id, match_info in resumen_partidos.items():

                if str(event_id) in all_stats:
                    continue

                match_stats = scrape_sofascore_json(
                    driver,
                    event_id,
                    player_id
                )

                if match_stats:
                    all_stats[str(event_id)] = {
                        "id": int(event_id),              # 👈 ID DEL PARTIDO
                        "match_info": match_info,         # datos resumen
                        "player_stats": match_stats       # scraping
                    }
                    print(f"✔️ Guardado {player_name} | partido {event_id}")
                else:
                    print(f"⚠️ Sin datos {player_name} | partido {event_id}")

                time.sleep(1)  # ⛑️ evita bloqueos

            # ---- guardar ----
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(all_stats, f, indent=2, ensure_ascii=False)

            print(f"💾 Guardado archivo: {output_file}")

    finally:
        driver.quit()
        print("🧹 Navegador cerrado correctamente")
