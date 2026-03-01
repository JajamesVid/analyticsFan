import sys
import json
import time
import os
from seleniumwire import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options


# =========================
# UTIL
# =========================

def normalize_name(name: str) -> str:
    return name.lower().replace(" ", "_")


# =========================
# Browser
# =========================
def start_browser():
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )

    driver.execute_cdp_cmd(
        "Network.setUserAgentOverride",
        {"userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    )

    return driver


# =========================
# Obtener eventos jugador
# =========================
def get_all_events(driver, player_id, max_pages=7):
    unique_events = {}

    for number in range(max_pages):
        url = f"https://www.sofascore.com/api/v1/player/{player_id}/events/last/{number}"
        print(f"📡 {url}")

        driver.get(url)
        time.sleep(2)

        try:
            json_text = driver.find_element("tag name", "pre").text
            data = json.loads(json_text)

            for event in data.get("events", []):
                event_id = str(event.get("id"))
                if event_id:
                    unique_events[event_id] = event

        except Exception as e:
            print("❌ Error obteniendo eventos:", e)

    return unique_events


# =========================
# Stats partido
# =========================
def scrape_match_stats(driver, event_id, player_id):
    url = f"https://www.sofascore.com/api/v1/event/{event_id}/player/{player_id}/statistics"
    print(f"🌐 {url}")

    driver.get(url)
    time.sleep(2)

    try:
        json_text = driver.find_element("tag name", "pre").text
        return json.loads(json_text)
    except Exception as e:
        print(f"❌ Error leyendo stats para {event_id}: {e}")
        return None


# =========================
# MAIN
# =========================
if __name__ == "__main__":

    if len(sys.argv) != 3:
        print("Uso: python3 sofa_all_stats_download.py 'Nombre Jugador' sofascore_id")
        sys.exit(1)

    player_name_raw = sys.argv[1]
    player_id = sys.argv[2]

    if not player_id.isdigit():
        print("❌ sofascore_id debe ser numérico")
        sys.exit(1)

    player_name = normalize_name(player_name_raw)

    # Crear carpeta destino
    base_folder = "player_stats"
    player_folder = os.path.join(base_folder, player_name)

    os.makedirs(player_folder, exist_ok=True)

    driver = start_browser()

    try:
        print(f"\n🔹 Jugador {player_name_raw} (ID: {player_id})")

        # ---- Paso 1: recolectar eventos únicos ----
        events = get_all_events(driver, player_id)
        print(f"📊 Eventos únicos encontrados: {len(events)}")

        all_stats = {}

        # ---- Paso 2: scrapear stats de cada evento ----
        for event_id, event in events.items():

            match_stats = scrape_match_stats(driver, event_id, player_id)

            if not match_stats:
                continue

            home_team = event.get("homeTeam", {})
            away_team = event.get("awayTeam", {})

            match_info = {
                "homeTeam": {
                    "name": home_team.get("name"),
                    "shortName": home_team.get("shortName") or (home_team.get("name") or "")[:3].upper(),
                    "color": home_team.get("teamColors", {}).get("primary"),
                    "score": event.get("homeScore", {}).get("current") if event.get("homeScore") else None
                },
                "awayTeam": {
                    "name": away_team.get("name"),
                    "shortName": away_team.get("shortName") or (away_team.get("name") or "")[:3].upper(),
                    "color": away_team.get("teamColors", {}).get("primary"),
                    "score": event.get("awayScore", {}).get("current") if event.get("awayScore") else None
                },
                "startTimestamp": event.get("startTimestamp"),
                "slug": event.get("slug")
            }

            all_stats[event_id] = {
                "id": int(event_id),
                "match_info": match_info,
                "player_stats": match_stats
            }

            print(f"✔️ {event_id}")
            time.sleep(1)

        # ---- Guardar resultado ----
        output_file = os.path.join(player_folder, "sofascore_all_matches.json")

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(all_stats, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Stats guardados en: {output_file}")

    finally:
        driver.quit()