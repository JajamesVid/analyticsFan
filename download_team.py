import sys
import json
import os
import random
import subprocess
import time
from datetime import datetime

PLAYERS_JSON = "players_to_analyze.json"
STATE_FILE = "download_state.txt"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:136.0) Gecko/20100101 Firefox/136.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36 Edg/141.0.0.0",
]

ACCEPT_LANGUAGES = [
    "en-US,en;q=0.9",
    "en-GB,en;q=0.8",
    "es-ES,es;q=0.9,en;q=0.8",
    "en-US,en;q=0.5",
    "es;q=0.9,en-US;q=0.8,en;q=0.7",
    "en-US,en;q=0.9,es;q=0.7",
]


def normalize(name):
    return name.lower().replace(" ", "_")


def sleep():
    time.sleep(random.uniform(1.0, 3.0))


def has_data(path):
    if not os.path.exists(path):
        return False, 0
    try:
        with open(path) as f:
            d = json.load(f)
        n = len(d)
        return n > 0, n
    except:
        return False, 0


def write_state(teams):
    lines = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines.append(f"Actualizado: {now}\n")

    lines.append("=" * 55)
    lines.append("ESTADÍSTICAS DE EQUIPO (team_stats/)")
    lines.append("=" * 55)
    downloaded_teams = 0
    for team in teams:
        folder = normalize(team["name"])
        path = os.path.join("team_stats", folder, "sofascore_all_matches.json")
        ok, n = has_data(path)
        if ok:
            lines.append(f"  ✔ {team['name']:<25} {n} partidos")
            downloaded_teams += 1
        else:
            lines.append(f"  ✗ {team['name']}")
    lines.append(f"\n  Total: {downloaded_teams}/{len(teams)} equipos")

    lines.append("")
    lines.append("=" * 55)
    lines.append("JUGADORES POR EQUIPO (sofascore_all_matches.json)")
    lines.append("=" * 55)
    for team in teams:
        folder = normalize(team["name"])
        players = team["players"]
        downloaded = sum(
            1 for p in players
            if has_data(os.path.join("player_stats", folder, p["name"], "sofascore_all_matches.json"))[0]
        )
        pct = downloaded / len(players) * 100 if players else 0
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        lines.append(f"  {team['name']:<25} {bar} {downloaded:>2}/{len(players)} ({pct:.0f}%)")

    with open(STATE_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"📄 Estado guardado en {STATE_FILE}")


if __name__ == "__main__":

    if len(sys.argv) < 2:
        print("Uso: python3 download_team.py 'Nombre Equipo'")
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

    # Rotar User-Agent para esta sesión
    os.environ["HTTP_USER_AGENT"] = random.choice(USER_AGENTS)
    os.environ["HTTP_ACCEPT_LANGUAGE"] = random.choice(ACCEPT_LANGUAGES)

    team_name = team["name"]
    team_id = team["sofascore_id"]
    team_folder = normalize(team_name)
    players = team["players"]

    print(f"\n🔵 JUGADORES — {team_name} ({len(players)} jugadores)")
    print("=" * 50)

    for player in players:
        name = player["name"]
        sofa_id = player["sofascore_id"]
        sofa_file = os.path.join("player_stats", team_folder, name, "sofascore_all_matches.json")

        ok, n = has_data(sofa_file)
        if ok:
            print(f"⏭ {name} ya descargado ({n} partidos)")
            continue

        print(f"\n→ {name}")
        subprocess.run(["python3", "sofa_all_stats_download.py", name, str(sofa_id), team_name])
        sleep()
        subprocess.run(["python3", "futFantasy_Pipeline.py", name, team_name])
        sleep()
        subprocess.run(["python3", "merge_to_Excel.py", name, team_name])
        print("---")

    print(f"\n🟢 STATS DE EQUIPO — {team_name}")
    print("=" * 50)

    team_stats_file = os.path.join("team_stats", team_folder, "sofascore_all_matches.json")
    ok, n = has_data(team_stats_file)
    if ok:
        print(f"⏭ Stats de equipo ya descargadas ({n} partidos)")
    else:
        subprocess.run(["python3", "sofa_team_stats_download.py", team_name, str(team_id)])

    print(f"\n📊 Generando Excel de equipo...")
    subprocess.run(["python3", "team_stats_to_excel.py", team_name, str(team_id)])

    print(f"\n✔ {team_name} completado")

    write_state(data["teams"])
