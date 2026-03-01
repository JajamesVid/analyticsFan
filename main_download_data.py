import json
import subprocess
import time

with open("players_to_analyze.json", "r", encoding="utf-8") as f:
    data = json.load(f)

for player in data["players"]:
    name = player["name"]
    sofa_id = player["sofascore_id"]

    print(f"Procesando {name}")

    subprocess.run(["python3", "futFantasy_Pipeline.py", name])
    time.sleep(2)
    subprocess.run(["python3", "sofa_all_stats_download.py", name, str(sofa_id)])
    time.sleep(2)
    subprocess.run(["python3", "merge_to_Excel.py", name])


    print("-------------")