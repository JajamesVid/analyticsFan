import os
import json
import time
import requests
from bs4 import BeautifulSoup

PLAYERS_URL = "https://www.realmadrid.com/es-ES/futbol/primer-equipo-masculino/plantilla"
OUTPUT_FOLDER = "realmadrid_player_photos"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def slug_from_url(url):
    return url.rstrip("/").split("/")[-1]


def get_players(session):
    resp = session.get(PLAYERS_URL, timeout=20)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    script = soup.find("script", type="application/ld+json")
    data = json.loads(script.string)

    players = []
    for role in data.get("member", []):
        member = role.get("member", {})

        if not member.get("image") or not member.get("url"):
            continue

        players.append({
            "slug": slug_from_url(member["url"]),
            "name": member.get("name"),
            "role": role.get("roleName"),
            "image_url": member["image"],
        })

    return players


def download_photo(session, player):
    dest_path = os.path.join(OUTPUT_FOLDER, f"{player['slug']}.png")

    if os.path.exists(dest_path):
        print(f"⏭ {player['name']} ya existe")
        return

    print(f"→ {player['name']}")

    try:
        resp = session.get(player["image_url"], timeout=20)
        resp.raise_for_status()
    except Exception as e:
        print(f"❌ Error descargando imagen de {player['name']}: {e}")
        return

    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    with open(dest_path, "wb") as f:
        f.write(resp.content)

    print(f"✔️ {player['name']} -> {dest_path}")


if __name__ == "__main__":
    session = requests.Session()
    session.headers.update(HEADERS)

    print(f"🌐 Descargando plantilla: {PLAYERS_URL}")
    players = get_players(session)
    print(f"📋 {len(players)} personas encontradas (jugadores + cuerpo técnico)\n")

    for player in players:
        download_photo(session, player)
        time.sleep(0.5)

    print(f"\n✔ Fotos guardadas en {OUTPUT_FOLDER}/")
