import os
import json
import pandas as pd

# --------------------------
# CONFIGURACIÓN
# --------------------------
INPUT_FOLDER = "player_stats_&_puntus"   # carpeta con JSON de jugadores
OUTPUT_FILE = "JUGADORES_Y_PUNTUACIONES.xlsx"

# --------------------------
# Función para aplanar dicts
# --------------------------
def flatten_dict(d, parent_key="", sep="_"):
    """
    Convierte un diccionario anidado en columnas planas.
    """
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)

# --------------------------
# Leer todos los JSON de la carpeta
# --------------------------
player_files = [f for f in os.listdir(INPUT_FOLDER) if f.endswith(".json")]

all_rows = []

for file in player_files:
    player_name = file.replace("_all_matches.json", "")
    input_path = os.path.join(INPUT_FOLDER, file)

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for event_data in data:  # antes era: for event_id, event_data in data.items():
        row = {}
        row["event_id"] = event_data.get("sofascore", {}).get("id") 
        # --- Equipos y resultado ---
        equipos = event_data.get("equipos", {})
        for side in ["local", "visitante"]:
            info = equipos.get(side, {})
            for k, v in info.items():
                row[f"{side}_{k}"] = v
        row["resultado"] = event_data.get("resultado")
        row["url_ficha"] = event_data.get("url_ficha")

        # --- Puntuaciones ---
        puntuaciones = event_data.get("puntuaciones", {})
        for k, v in puntuaciones.items():
            if k == "detalladas" and isinstance(v, dict):
                # Desglosar detalladas en columnas independientes
                for det_k, det_v in v.items():
                    row[f"puntus_{det_k}"] = det_v
            else:
                row[f"puntus_{k}"] = v

        # --- SofaScore ---
        sofascore = event_data.get("sofascore", {})
        match_info = sofascore.get("match_info", {})
        row.update(flatten_dict(match_info, "ss_match"))

        player_stats = sofascore.get("player_stats", {})
        row.update(flatten_dict(player_stats, "ss_stats"))

        all_rows.append(row)

# --------------------------
# Crear DataFrame final
# --------------------------
df = pd.DataFrame(all_rows)

# Ordenar por fecha si existe
if "ss_match_startTimestamp" in df.columns:
    df = df.sort_values("ss_match_startTimestamp")

# --------------------------
# Exportar Excel final
# --------------------------
df.to_excel(OUTPUT_FILE, index=False)
print(f"✔ Excel final generado: {OUTPUT_FILE}")
