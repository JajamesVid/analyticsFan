import json
import sys
import os
import re
from datetime import datetime


SPANISH_MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12
}


def normalize(name):
    return name.lower().replace(" ", "_")


def parse_ff_date(date_str):
    if not date_str:
        return None

    pattern = r"(\d{1,2})\s+de\s+([a-záéíóú]+)\s+(?:del\s+)?(\d{4})"
    match = re.search(pattern, date_str.lower())

    if not match:
        return None

    day = int(match.group(1))
    month_name = match.group(2)
    year = int(match.group(3))

    month = SPANISH_MONTHS.get(month_name)
    if not month:
        return None

    return datetime(year, month, day).strftime("%Y-%m-%d")


def parse_ss_date(timestamp):
    if not timestamp:
        return None
    try:
        return datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d")
    except:
        return None


def merge(base_path):
    ff_input = os.path.join(base_path, "futfantasy.json")
    ss_input = os.path.join(base_path, "sofascore_all_matches.json")
    full_output = os.path.join(base_path, "full_stats.json")

    with open(ff_input, "r", encoding="utf-8") as f:
        ff_data = json.load(f)

    with open(ss_input, "r", encoding="utf-8") as f:
        ss_data = json.load(f)

    for partido in ff_data:
        partido["fecha_normalizada"] = parse_ff_date(partido.get("fecha_partido"))

    ff_index = {}
    for partido in ff_data:
        fecha = partido.get("fecha_normalizada")
        if fecha:
            ff_index.setdefault(fecha, []).append(partido)

    combined_matches = []

    for match_id, match_obj in ss_data.items():
        ts = match_obj.get("match_info", {}).get("startTimestamp")
        fecha = parse_ss_date(ts)

        if not fecha or fecha not in ff_index:
            continue

        for ff_match in ff_index[fecha]:
            combined_matches.append({
                "equipos": {
                    "local": ff_match["local"],
                    "visitante": ff_match["visitante"]
                },
                "resultado": ff_match["resultado"],
                "fecha": fecha,
                "url_ficha": ff_match["url_ficha"],
                "puntuaciones": ff_match["puntuaciones"],
                "sofascore": match_obj
            })

    with open(full_output, "w", encoding="utf-8") as f:
        json.dump(combined_matches, f, ensure_ascii=False, indent=2)

    print(f"✔ Matches combinados: {len(combined_matches)} -> {full_output}")

    return combined_matches


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python3 merge_full_stats.py nombre_jugador_normalizado ['Nombre Equipo']")
        sys.exit(1)

    player_name = sys.argv[1]
    team_name = sys.argv[2] if len(sys.argv) >= 3 else None

    base_path = os.path.join("player_stats", normalize(team_name), player_name) if team_name else os.path.join("player_stats", player_name)

    merge(base_path)
