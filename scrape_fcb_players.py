import os
import re
import time
import io
import requests
from bs4 import BeautifulSoup
from PIL import Image
from rembg import remove

PLAYERS_URL = "https://www.fcbarcelona.es/es/futbol/primer-equipo/jugadores"
OUTPUT_FOLDER = "fcb_player_photos"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def slug_from_href(href):
    return href.rstrip("/").split("/")[-1]


def get_players(session):
    resp = session.get(PLAYERS_URL, timeout=20)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    players = []

    for li in soup.select("li.team-list__person-container"):
        link = li.select_one("a[href]")
        picture = li.select_one("picture[data-img-src]")

        if not link or not picture:
            continue

        first_name = li.select_one(".team-person__first-name")
        last_name = li.select_one(".team-person__last-name")

        first_name = first_name.get_text(strip=True) if first_name else ""
        last_name = last_name.get_text(strip=True) if last_name else ""
        display_name = f"{first_name} {last_name}".strip()

        players.append({
            "id": li.get("data-player-id"),
            "slug": slug_from_href(link["href"]),
            "name": display_name,
            "image_url": picture["data-img-src"] + "?width=940&height=940",
        })

    return players


def download_and_remove_bg(session, player):
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

    try:
        img = Image.open(io.BytesIO(resp.content))
        out = remove(img)
    except Exception as e:
        print(f"❌ Error quitando el fondo de {player['name']}: {e}")
        return

    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    out.save(dest_path)
    print(f"✔️ {player['name']} -> {dest_path}")


if __name__ == "__main__":
    session = requests.Session()
    session.headers.update(HEADERS)

    print(f"🌐 Descargando lista de jugadores: {PLAYERS_URL}")
    players = get_players(session)
    print(f"📋 {len(players)} jugadores encontrados\n")

    for player in players:
        download_and_remove_bg(session, player)
        time.sleep(1)

    print(f"\n✔ Fotos guardadas en {OUTPUT_FOLDER}/")
