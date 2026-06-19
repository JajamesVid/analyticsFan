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
    team_id = team["sofascore_id"]
    team_folder = normalize_name(team_name)

    print(f"\n{'='*50}")
    print(f"Equipo {team_index}/{len(teams)}: {team_name} (ID: {team_id})")
    print(f"{'='*50}")

    output_file = os.path.join("team_stats", team_folder, "sofascore_all_matches.json")

    if os.path.exists(output_file):
        print(f"⏭ Ya descargado, saltando")
        continue

    subprocess.run(["python3", "sofa_team_stats_download.py", team_name, str(team_id)])

    print(f"✔ {team_name} completado")
    time.sleep(2)
