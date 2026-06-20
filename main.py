import sys
import json
import os
import subprocess
import time

PLAYERS_JSON = "players_to_analyze.json"


def normalize(name):
    return name.lower().replace(" ", "_")


def load_teams():
    with open(PLAYERS_JSON, "r", encoding="utf-8") as f:
        return json.load(f).get("teams", [])


def download_players(teams):
    for i, team in enumerate(teams, 1):
        team_name = team["name"]
        team_folder = normalize(team_name)
        players = team["players"]

        print(f"\n{'='*50}")
        print(f"Equipo {i}/{len(teams)}: {team_name} ({len(players)} jugadores)")
        print(f"{'='*50}")

        for player in players:
            name = player["name"]
            sofa_id = player["sofascore_id"]
            sofa_file = os.path.join("player_stats", team_folder, name, "sofascore_all_matches.json")

            if os.path.exists(sofa_file):
                print(f"⏭ {name} ya descargado")
                continue

            print(f"\n→ {name}")
            subprocess.run(["python3", "sofa_all_stats_download.py", name, str(sofa_id), team_name])
            time.sleep(1)
            subprocess.run(["python3", "futFantasy_Pipeline.py", name, team_name])
            time.sleep(1)
            subprocess.run(["python3", "merge_to_Excel.py", name, team_name])
            print("---")

        print(f"✔ {team_name} completado")


def download_teams(teams):
    for i, team in enumerate(teams, 1):
        team_name = team["name"]
        team_id = team["sofascore_id"]
        team_folder = normalize(team_name)

        print(f"\n{'='*50}")
        print(f"Equipo {i}/{len(teams)}: {team_name}")
        print(f"{'='*50}")

        output_file = os.path.join("team_stats", team_folder, "sofascore_all_matches.json")
        if os.path.exists(output_file):
            with open(output_file) as f:
                n = len(json.load(f))
            if n > 0:
                print(f"⏭ Ya descargado ({n} partidos)")
                continue

        subprocess.run(["python3", "sofa_team_stats_download.py", team_name, str(team_id)])
        time.sleep(2)

        print(f"✔ {team_name} completado")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"

    if mode not in ("players", "teams", "all"):
        print("Uso: python3 main.py [players|teams|all]")
        print("  players → descarga stats de jugadores")
        print("  teams   → descarga stats de equipos")
        print("  all     → descarga todo (por defecto)")
        sys.exit(1)

    teams = load_teams()

    if mode in ("players", "all"):
        print("\n🔵 DESCARGANDO STATS DE JUGADORES")
        download_players(teams)

    if mode in ("teams", "all"):
        print("\n🟢 DESCARGANDO STATS DE EQUIPOS")
        download_teams(teams)
