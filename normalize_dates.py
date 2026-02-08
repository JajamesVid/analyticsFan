import json
import re
from datetime import datetime

# -------- Archivos --------
FF_INPUT = "player_stats/griezmann_futfantasy_con_fecha.json"
SS_INPUT = "player_stats/Griezmann_all_matches.json"

FF_OUTPUT = "player_stats/griezmann_futfantasy_normalized.json"
SS_OUTPUT = "player_stats/Griezmann_all_matches_normalized.json"


# -------- Meses --------
SPANISH_MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12
}


# -------- FutbolFantasy --------
def parse_ff_date(date_str):
    if not date_str:
        return None

    # Regex mucho más tolerante
    pattern = r"(\d{1,2})\s+de\s+([a-záéíóú]+)\s+(?:del\s+)?(\d{4})"

    match = re.search(pattern, date_str.lower())

    if not match:
        print("Formato FF no reconocido:", date_str)
        return None

    day = int(match.group(1))
    month_name = match.group(2)
    year = int(match.group(3))

    month = SPANISH_MONTHS.get(month_name)

    if not month:
        print("Mes FF no reconocido:", month_name)
        return None

    dt = datetime(year, month, day)
    print("year: ", year, " month: ", month," day: ", day)
    return dt.strftime("%Y-%m-%d")


# -------- SofaScore --------
def parse_ss_date(timestamp):
    if not timestamp:
        return None

    try:
        dt = datetime.utcfromtimestamp(timestamp)
        return dt.strftime("%Y-%m-%d")
    except Exception as e:
        print(f"Error SS timestamp {timestamp}: {e}")
        return None


# -------- Procesar FutbolFantasy --------
def process_futfantasy():
    with open(FF_INPUT, "r", encoding="utf-8") as f:
        ff_data = json.load(f)

    for partido in ff_data:
        ff_raw_date = partido.get("fecha_partido")
        print(partido)
        partido["fecha_normalizada"] = parse_ff_date(ff_raw_date)

    with open(FF_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(ff_data, f, ensure_ascii=False, indent=2)

    print("✔ FutbolFantasy normalizado")


# -------- Procesar SofaScore --------
def process_sofascore():
    with open(SS_INPUT, "r", encoding="utf-8") as f:
        ss_data = json.load(f)

    for match_id, match_obj in ss_data.items():
        ts = match_obj["match_info"].get("startTimestamp")
        match_obj["match_info"]["fecha_normalizada"] = parse_ss_date(ts)

    with open(SS_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(ss_data, f, ensure_ascii=False, indent=2)

    print("✔ SofaScore normalizado")


# -------- Main --------
if __name__ == "__main__":
    process_futfantasy()
    process_sofascore()
