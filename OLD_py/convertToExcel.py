import os
import json
import pandas as pd

# --------------------------
# CONFIGURACIÓN DE RUTAS
# --------------------------

IDS_FILE = "real_madrid_ids.json"
MATCHES_FOLDER = "Real_madrid_matches_2025"
OUTPUT_FOLDER = "EXCEL_JUGADORES"

os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# ------------------------------------
# Cargar nombres del Real Madrid
# ------------------------------------
with open(IDS_FILE, "r", encoding="utf-8") as f:
    madrid_ids = json.load(f)   # dict: name → id

madrid_names = set(madrid_ids.keys())

all_stats = {name: [] for name in madrid_names}

# ------------------------------------
# Leer todos los archivos del folder
# ------------------------------------
match_files = [
    os.path.join(MATCHES_FOLDER, f)
    for f in os.listdir(MATCHES_FOLDER)
    if f.endswith(".json")
]

for file in match_files:
    with open(file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Recorrer jugadores del diccionario del JSON
    for player_name, info in data.items():

        if "error" in info:
            continue

        # Solo registrar si es del Madrid
        if player_name in madrid_names:

            stats = info.get("statistics", {})
            player = info.get("player", {})
            team = info.get("team", {})

            row = {"match_file": os.path.basename(file)}

            # ------------------------------------
            # ➤ Añadir estadísticas dinámicas
            # ------------------------------------
            for k, v in stats.items():
                row[k] = v

            # ------------------------------------
            # ➤ Campos extra solicitados
            # ------------------------------------
            row["player_jerseyNumber"] = player.get("jerseyNumber")
            row["player_position"] = info.get("position")

            # proposedMarketValueRaw → value
            pmv = player.get("proposedMarketValueRaw", {})
            row["player_proposedMarketValueRaw_value"] = pmv.get("value")

            # Team colors
            colors = team.get("teamColors", {})
            row["team_teamColors_primary"] = colors.get("primary")
            row["team_teamColors_secondary"] = colors.get("secondary")

            all_stats[player_name].append(row)

# ------------------------------------
# Crear un Excel por jugador
# ------------------------------------
for player, rows in all_stats.items():
    if not rows:
        print(f"⚠ El jugador {player} no aparece en ningún archivo.")
        continue

    df = pd.DataFrame(rows)

    output_path = os.path.join(OUTPUT_FOLDER, f"{player}.xlsx")
    df.to_excel(output_path, index=False)
    print(f"✔ Excel generado para {player}")
