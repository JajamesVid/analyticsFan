import sys
import json
import os
from datetime import datetime
import pandas as pd


def normalize_name(name: str) -> str:
    return name.lower().replace(" ", "_")


def parse_timestamp(ts):
    if not ts:
        return None
    return datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")


def extract_stats_for_period(statistics, period="ALL"):
    stats = {}
    for block in statistics:
        if block.get("period") != period:
            continue
        for group in block.get("groups", []):
            for item in group.get("statisticsItems", []):
                key = item.get("key")
                if key:
                    stats[f"{key}_home"] = item.get("homeValue")
                    stats[f"{key}_away"] = item.get("awayValue")
    return stats


if __name__ == "__main__":

    if len(sys.argv) not in (3, 4):
        print("Uso: python3 team_stats_to_excel.py 'Nombre Equipo' sofascore_team_id [periodo]")
        print("  periodo: ALL (defecto), 1ST, 2ND")
        sys.exit(1)

    team_name_raw = sys.argv[1]
    team_id = int(sys.argv[2])
    period = sys.argv[3] if len(sys.argv) == 4 else "ALL"

    team_name = normalize_name(team_name_raw)
    team_folder = os.path.join("team_stats", team_name)
    input_file = os.path.join(team_folder, "sofascore_all_matches.json")

    if not os.path.exists(input_file):
        print(f"❌ No se encuentra: {input_file}")
        sys.exit(1)

    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    rows = []

    for event_id, match in data.items():
        match_info = match.get("match_info", {})
        home = match_info.get("homeTeam", {})
        away = match_info.get("awayTeam", {})

        is_home = home.get("id") == team_id

        row = {
            "event_id": match.get("id"),
            "date": parse_timestamp(match_info.get("startTimestamp")),
            "tournament": match_info.get("tournament"),
            "season": match_info.get("season"),
            "home_team": home.get("name"),
            "away_team": away.get("name"),
            "home_score": home.get("score"),
            "away_score": away.get("score"),
            "is_home": is_home,
            "team_score": home.get("score") if is_home else away.get("score"),
            "opponent_score": away.get("score") if is_home else home.get("score"),
            "opponent_name": away.get("name") if is_home else home.get("name"),
        }

        row.update(extract_stats_for_period(match.get("statistics", []), period))

        rows.append(row)

    df = pd.DataFrame(rows)
    df = df.sort_values("date").reset_index(drop=True)

    output_file = os.path.join(team_folder, f"{team_name}_{period.lower()}_stats.xlsx")
    df.to_excel(output_file, index=False)

    print(f"✔ Excel generado: {output_file} ({len(df)} partidos)")
