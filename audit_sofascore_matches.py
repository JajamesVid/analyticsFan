import os
import re
import json
import time

from add_sofascore_id_to_photos import (
    PLAYERS_JSON, FOLDER_TO_TEAM, EXTRA_FOLDERS,
    regenerate_names, best_match, normalize_tokens,
)

if __name__ == "__main__":
    with open(PLAYERS_JSON, encoding="utf-8") as f:
        data = json.load(f)

    rosters = {t["name"]: t["players"] for t in data["teams"]}

    all_targets = [(os.path.join("laliga_player_photos", tf), tn, None) for tf, tn in FOLDER_TO_TEAM.items()]
    all_targets += [(pd, tn, fetcher) for pd, (tn, fetcher) in EXTRA_FOLDERS.items()]

    suspicious = 0

    for photo_dir, team_name, fetcher in all_targets:
        if not os.path.isdir(photo_dir):
            continue

        team_folder = os.path.basename(photo_dir)

        try:
            if fetcher:
                import requests
                slug_to_name = fetcher(requests.Session())
            else:
                slug_to_name = regenerate_names(team_folder)
        except Exception as e:
            print(f"❌ {team_name}: no se pudo regenerar nombres ({e})")
            continue

        roster = rosters.get(team_name, [])

        for filename in sorted(os.listdir(photo_dir)):
            if not filename.endswith(".png"):
                continue

            base = filename[:-4]
            m = re.match(r"^(.*)_(\d{4,})$", base)
            if not m:
                continue

            file_slug, current_id = m.group(1), int(m.group(2))
            display_name = slug_to_name.get(file_slug, file_slug.replace("-", " "))

            name_toks = normalize_tokens(display_name)
            min_score = 2 if len(name_toks) >= 2 else 1

            candidates = best_match(display_name, roster)
            top_score = candidates[0][0] if candidates else 0
            tied = [c for c in candidates if c[0] == top_score]

            if top_score < min_score or len(tied) > 1:
                print(f"⚠️ REVISAR {team_name}/{filename} ({display_name}): con la lógica nueva ya NO tiene match claro (score={top_score}, empatados={len(tied)}) — id actual {current_id}")
                suspicious += 1
                continue

            new_id = tied[0][1]["sofascore_id"]
            if new_id != current_id:
                print(f"❌ DISCREPANCIA {team_name}/{filename} ({display_name}): id actual {current_id}, la lógica nueva diría {new_id} ({tied[0][1]['name']})")
                suspicious += 1

        time.sleep(0.3)

    print(f"\n{'='*50}")
    print(f"Total sospechosos: {suspicious}")
