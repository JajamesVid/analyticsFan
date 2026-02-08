from seleniumwire import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import json
import time
import os

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

    # Jugadores a scrapear (puedes agregar más)
    players = {
        "Griezmann": 85859
    }

    OUTPUT_FOLDER = "player_stats"
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    driver = start_browser()

    try:
        for player_name, player_id in players.items():

            print(f"\n🔹 Jugador {player_name}")

            # ---- Paso 1: recolectar eventos únicos ----
            events = get_all_events(driver, player_id)
            print(f"📊 Eventos únicos encontrados: {len(events)}")

            all_stats = {}

            # ---- Paso 2: scrapear stats de cada evento ----
            for event_id, event in events.items():

                match_stats = scrape_match_stats(driver, event_id, player_id)

                if not match_stats:
                    continue

                # --- Reconstruir objeto estilo matchids para tu pipeline ---
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
                    "hasEventPlayerStatistics": event.get("hasEventPlayerStatistics"),
                    "isEditor": event.get("isEditor"),
                    "slug": event.get("slug"),
                    "finalResultOnly": event.get("finalResultOnly")
                }

                # --- Guardar en all_stats ---
                all_stats[event_id] = {
                    "id": int(event_id),
                    "match_info": match_info,
                    "player_stats": match_stats
                }

                print(f"✔️ {event_id}")
                time.sleep(1)

            # ---- Guardar solo all_matches.json ----
            output_file = os.path.join(
                OUTPUT_FOLDER,
                f"{player_name}_all_matches.json"
            )
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(all_stats, f, indent=2, ensure_ascii=False)

            print(f"💾 Stats guardados: {output_file}")

    finally:
        driver.quit()
