import sys
import os
import json
import time
import random
import base64
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

PLAYERS_JSON = "players_to_analyze.json"
IMAGE_FILENAME = "photo.jpg"

FETCH_IMAGE_SCRIPT = """
var callback = arguments[arguments.length - 1];
fetch(arguments[0])
  .then(r => {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.arrayBuffer();
  })
  .then(buf => {
      var bytes = new Uint8Array(buf);
      var binary = '';
      for (var i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
      callback(btoa(binary));
  })
  .catch(e => callback(null));
"""


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

    driver.execute_cdp_cmd("Network.enable", {})
    driver.execute_cdp_cmd("Network.setExtraHTTPHeaders", {
        "headers": {"X-Requested-With": "463ab6"}
    })

    print("🌍 Obteniendo cookies de SofaScore...")
    driver.get("https://www.sofascore.com")
    time.sleep(4)

    return driver


def download_player_image(driver, player_id, dest_path):
    url = f"https://api.sofascore.com/api/v1/player/{player_id}/image"

    try:
        b64_data = driver.execute_async_script(FETCH_IMAGE_SCRIPT, url)
    except Exception as e:
        print(f"❌ Error descargando imagen: {e}")
        return False

    if not b64_data:
        print("❌ Respuesta vacía (imagen no disponible)")
        return False

    try:
        img_bytes = base64.b64decode(b64_data)
    except Exception as e:
        print(f"❌ Error decodificando imagen: {e}")
        return False

    with open(dest_path, "wb") as f:
        f.write(img_bytes)

    return True


if __name__ == "__main__":

    if len(sys.argv) < 2:
        print("Uso: python3 download_player_photos.py 'Nombre Equipo'")
        sys.exit(1)

    team_name_arg = sys.argv[1].lower()

    with open(PLAYERS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    team = next((t for t in data["teams"] if t["name"].lower() == team_name_arg), None)

    if not team:
        print(f"❌ Equipo '{sys.argv[1]}' no encontrado en {PLAYERS_JSON}")
        print("Equipos disponibles:")
        for t in data["teams"]:
            print(f"  - {t['name']}")
        sys.exit(1)

    team_folder = normalize_name(team["name"])
    players = team["players"]

    print(f"\n🔵 FOTOS — {team['name']} ({len(players)} jugadores)")
    print("=" * 50)

    driver = start_browser()

    try:
        for player in players:
            name = player["name"]
            sofa_id = player["sofascore_id"]

            player_folder = os.path.join("player_stats", team_folder, name)
            os.makedirs(player_folder, exist_ok=True)
            dest_path = os.path.join(player_folder, IMAGE_FILENAME)

            if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
                print(f"⏭ {name} ya tiene foto")
                continue

            print(f"→ {name} (ID: {sofa_id})")
            ok = download_player_image(driver, sofa_id, dest_path)
            if ok:
                print(f"✔️ {name}")
            else:
                print(f"❌ {name} — no se pudo descargar")

            time.sleep(random.uniform(1.0, 2.5))

    finally:
        driver.quit()

    print(f"\n🟢 {team['name']} completado")
