import json
import os
import subprocess
import time

def normalize_name(name):
    return name.lower().replace(" ", "_")

with open("players_to_analyze.json", "r", encoding="utf-8") as f:
    data = json.load(f)

teams = data.get("teams", [])

for team_index, team in enumerate(teams, start=1):
    team_name = team["name"]
    team_folder = normalize_name(team_name)
    players = team["players"]

    print(f"\n{'='*50}")
    print(f"Equipo {team_index}/{len(teams)}: {team_name} ({len(players)} jugadores)")
    print(f"{'='*50}")

    for player in players:
        name = player["name"]
        sofa_id = player["sofascore_id"]

        sofa_file = os.path.join("player_stats", team_folder, name, "sofascore_all_matches.json")

        if os.path.exists(sofa_file):
            print(f"⏭ {name} ya descargado, saltando")
            continue

        print(f"\nProcesando {name}")

        subprocess.run(["python3", "sofa_all_stats_download.py", name, str(sofa_id), team_name])
        time.sleep(1)
        subprocess.run(["python3", "futFantasy_Pipeline.py", name, team_name])
        time.sleep(1)
        subprocess.run(["python3", "merge_to_Excel.py", name, team_name])

        print("-------------")

    print(f"✔ Equipo {team_name} completado")
