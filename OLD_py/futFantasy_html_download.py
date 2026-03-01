import requests
import sys
import os

# =========================
# Config
# =========================
SEASONS = ["22-23", "23-24", "24-25", "25-26"]

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


# =========================
# Helper para slug jugador
# =========================
def format_player_slug(player_name):
    return player_name.lower().replace(" ", "-")


# =========================
# MAIN
# =========================
if __name__ == "__main__":

    if len(sys.argv) < 2:
        print("❌ Uso: python script.py 'Nombre Jugador'")
        sys.exit(1)

    player_name = sys.argv[1]
    player_slug = format_player_slug(player_name)

    output_folder = f"{player_slug}_html"
    os.makedirs(output_folder, exist_ok=True)

    for season in SEASONS:

        url = f"https://www.futbolfantasy.com/jugadores/{player_slug}/laliga-{season}"
        print(f"🌐 Descargando {url}")

        try:
            response = requests.get(url, headers=HEADERS)

            if response.status_code == 200:

                filename = os.path.join(
                    output_folder,
                    f"{player_slug}_{season}.html"
                )

                with open(filename, "w", encoding="utf-8") as f:
                    f.write(response.text)

                print(f"✅ Guardado {filename}")

            else:
                print(f"⚠️ Error {response.status_code} en {season}")

        except Exception as e:
            print(f"❌ Error descargando {season}: {e}")
