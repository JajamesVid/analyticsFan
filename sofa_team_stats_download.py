import sys
import json
import time
import os
from datetime import datetime, timezone
from seleniumwire import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options


def normalize_name(name: str) -> str:
    return name.lower().replace(" ", "_")


def start_browser():
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )

    driver.execute_cdp_cmd(
        "Network.setUserAgentOverride",
        {"userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"}
    )

    # Visitar homepage para pasar el challenge de Cloudflare y obtener cookies
    print("🌍 Obteniendo cookies de SofaScore...")
    driver.get("https://www.sofascore.com")
    time.sleep(4)

    return driver


def get_all_team_events(driver, team_id, since_timestamp, max_pages=50):
    unique_events = {}

    for number in range(max_pages):
        url = f"https://www.sofascore.com/api/v1/team/{team_id}/events/last/{number}"
        print(f"📡 {url}")

        driver.get(url)
        time.sleep(1.5)

        try:
            json_text = driver.find_element("tag name", "pre").text
            data = json.loads(json_text)

            if "events" not in data:
                print(f"⚠️  Respuesta inesperada: {json_text[:300]}")
                break

            events = data["events"]
            print(f"   → {len(events)} eventos en página {number}")

            if not events:
                print("✅ No hay más eventos.")
                break

            page_oldest = min(e.get("startTimestamp", 0) for e in events)

            for event in events:
                if event.get("startTimestamp", 0) >= since_timestamp:
                    event_id = str(event.get("id"))
                    if event_id:
                        unique_events[event_id] = event

            if page_oldest < since_timestamp:
                print(f"✅ Llegamos a la fecha límite en página {number}.")
                break

        except Exception as e:
            print(f"❌ Error en página {number}: {e}")
            print(f"   HTML: {driver.page_source[:300]}")

        time.sleep(0.5)

    return unique_events


def scrape_event_team_stats(driver, event_id):
    url = f"https://www.sofascore.com/api/v1/event/{event_id}/statistics"
    print(f"🌐 {url}")

    driver.get(url)
    time.sleep(1.5)

    try:
        json_text = driver.find_element("tag name", "pre").text
        return json.loads(json_text)
    except Exception as e:
        print(f"❌ Error leyendo stats para {event_id}: {e}")
        return None


if __name__ == "__main__":

    if len(sys.argv) not in (3, 4):
        print("Uso: python3 sofa_team_stats_download.py 'Nombre Equipo' sofascore_team_id [desde_fecha]")
        print("  desde_fecha: formato YYYY-MM-DD, por defecto 2022-08-01 (inicio temporada 22-23)")
        sys.exit(1)

    team_name_raw = sys.argv[1]
    team_id = sys.argv[2]
    since_date_str = sys.argv[3] if len(sys.argv) == 4 else "2022-08-01"

    if not team_id.isdigit():
        print("❌ sofascore_team_id debe ser numérico")
        sys.exit(1)

    try:
        since_timestamp = int(datetime.strptime(since_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
    except ValueError:
        print("❌ Formato de fecha inválido. Usa YYYY-MM-DD")
        sys.exit(1)

    team_name = normalize_name(team_name_raw)
    team_folder = os.path.join("team_stats", team_name)
    os.makedirs(team_folder, exist_ok=True)

    driver = start_browser()

    try:
        print(f"\n🔹 Equipo: {team_name_raw} (ID: {team_id})")
        print(f"📅 Descargando desde: {since_date_str}")

        events = get_all_team_events(driver, team_id, since_timestamp)
        print(f"📊 Partidos únicos encontrados: {len(events)}")

        all_stats = {}

        for event_id, event in events.items():

            raw_stats = scrape_event_team_stats(driver, event_id)

            if not raw_stats:
                continue

            home_team = event.get("homeTeam", {})
            away_team = event.get("awayTeam", {})

            match_info = {
                "homeTeam": {
                    "id": home_team.get("id"),
                    "name": home_team.get("name"),
                    "shortName": home_team.get("shortName") or (home_team.get("name") or "")[:3].upper(),
                    "color": home_team.get("teamColors", {}).get("primary"),
                    "score": event.get("homeScore", {}).get("current") if event.get("homeScore") else None
                },
                "awayTeam": {
                    "id": away_team.get("id"),
                    "name": away_team.get("name"),
                    "shortName": away_team.get("shortName") or (away_team.get("name") or "")[:3].upper(),
                    "color": away_team.get("teamColors", {}).get("primary"),
                    "score": event.get("awayScore", {}).get("current") if event.get("awayScore") else None
                },
                "startTimestamp": event.get("startTimestamp"),
                "slug": event.get("slug"),
                "tournament": event.get("tournament", {}).get("name"),
                "season": event.get("season", {}).get("name")
            }

            all_stats[event_id] = {
                "id": int(event_id),
                "match_info": match_info,
                "statistics": raw_stats.get("statistics", [])
            }

            print(f"✔️ {event_id}")
            time.sleep(0.5)

        output_file = os.path.join(team_folder, "sofascore_all_matches.json")

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(all_stats, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Stats guardados en: {output_file}")

    finally:
        driver.quit()
