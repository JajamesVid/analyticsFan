import json
import sys
import os
import re
from datetime import datetime
import pandas as pd


# ==========================
# VALIDACIÓN ARGUMENTOS
# ==========================
if len(sys.argv) < 2:
    print("Uso: python3 merge_to_excel.py nombre_jugador_normalizado")
    sys.exit(1)

player_name = sys.argv[1]
base_path = os.path.join("player_stats", player_name)

FF_INPUT = os.path.join(base_path, "futfantasy.json")
SS_INPUT = os.path.join(base_path, "sofascore_all_matches.json")

FF_NORMALIZED = os.path.join(base_path, "futfantasy_normalized.json")
SS_NORMALIZED = os.path.join(base_path, "sofascore_all_matches_normalized.json")

FULL_OUTPUT = os.path.join(base_path, "full_stats.json")
UNMATCHED_FF = os.path.join(base_path, "unmatched_futfantasy.json")
UNMATCHED_SS = os.path.join(base_path, "unmatched_sofascore.json")

EXCEL_OUTPUT = os.path.join(base_path, f"{player_name}_full_stats.xlsx")


# ==========================
# MESES
# ==========================
SPANISH_MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12
}


# ==========================
# PARSERS FECHA
# ==========================
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


# ==========================
# NORMALIZACIÓN
# ==========================
with open(FF_INPUT, "r", encoding="utf-8") as f:
    ff_data = json.load(f)

for partido in ff_data:
    partido["fecha_normalizada"] = parse_ff_date(
        partido.get("fecha_partido")
    )

with open(FF_NORMALIZED, "w", encoding="utf-8") as f:
    json.dump(ff_data, f, ensure_ascii=False, indent=2)


with open(SS_INPUT, "r", encoding="utf-8") as f:
    ss_data = json.load(f)

for match_id, match_obj in ss_data.items():
    ts = match_obj.get("match_info", {}).get("startTimestamp")
    match_obj["match_info"]["fecha_normalizada"] = parse_ss_date(ts)

with open(SS_NORMALIZED, "w", encoding="utf-8") as f:
    json.dump(ss_data, f, ensure_ascii=False, indent=2)

print("✔ Fechas normalizadas")


# ==========================
# INDEX FUTBOLFANTASY
# ==========================
ff_index = {}
for partido in ff_data:
    fecha = partido.get("fecha_normalizada")
    if fecha:
        ff_index.setdefault(fecha, []).append(partido)


# ==========================
# MATCHING + UNMATCHED
# ==========================
combined_matches = []
matched_ff_ids = set()
matched_ss_ids = set()

for match_id, match_obj in ss_data.items():

    fecha = match_obj.get("match_info", {}).get("fecha_normalizada")
    if not fecha:
        continue

    if fecha in ff_index:
        for ff_match in ff_index[fecha]:
            combined_matches.append({
                'equipos': {
                    'local': ff_match['local'],
                    'visitante': ff_match['visitante']
                },
                'resultado': ff_match['resultado'],
                'fecha': fecha,
                'url_ficha': ff_match['url_ficha'],
                'puntuaciones': ff_match['puntuaciones'],
                'sofascore': match_obj
            })
            matched_ff_ids.add(id(ff_match))
            matched_ss_ids.add(match_id)


# -------- UNMATCHED --------
unmatched_ff = [
    partido for partido in ff_data
    if id(partido) not in matched_ff_ids
]

unmatched_ss = {
    match_id: match_obj
    for match_id, match_obj in ss_data.items()
    if match_id not in matched_ss_ids
}

with open(UNMATCHED_FF, "w", encoding="utf-8") as f:
    json.dump(unmatched_ff, f, ensure_ascii=False, indent=2)

with open(UNMATCHED_SS, "w", encoding="utf-8") as f:
    json.dump(unmatched_ss, f, ensure_ascii=False, indent=2)


# ==========================
# GUARDAR FULL JSON
# ==========================
with open(FULL_OUTPUT, "w", encoding="utf-8") as f:
    json.dump(combined_matches, f, ensure_ascii=False, indent=2)

print(f"✔ Matches combinados: {len(combined_matches)}")
print(f"✔ FF sin match: {len(unmatched_ff)}")
print(f"✔ SS sin match: {len(unmatched_ss)}")


# ==========================
# FLATTEN
# ==========================
def flatten_dict(d, parent_key="", sep="_"):
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


# ==========================
# EXCEL
# ==========================
rows = []

for event_data in combined_matches:

    row = {}
    row["event_id"] = event_data.get("sofascore", {}).get("id")

    equipos = event_data.get("equipos", {})
    for side in ["local", "visitante"]:
        info = equipos.get(side, {})
        for k, v in info.items():
            row[f"{side}_{k}"] = v

    row["resultado"] = event_data.get("resultado")
    row["url_ficha"] = event_data.get("url_ficha")

    puntuaciones = event_data.get("puntuaciones", {})
    for k, v in puntuaciones.items():
        if k == "detalladas" and isinstance(v, dict):
            for det_k, det_v in v.items():
                row[f"puntus_{det_k}"] = det_v
        else:
            row[f"puntus_{k}"] = v

    sofascore = event_data.get("sofascore", {})
    row.update(flatten_dict(sofascore.get("match_info", {}), "ss_match"))
    row.update(flatten_dict(sofascore.get("player_stats", {}), "ss_stats"))

    rows.append(row)

df = pd.DataFrame(rows)

if "ss_match_startTimestamp" in df.columns:
    df = df.sort_values("ss_match_startTimestamp")

df.to_excel(EXCEL_OUTPUT, index=False)

print(f"✔ Excel generado: {EXCEL_OUTPUT}")