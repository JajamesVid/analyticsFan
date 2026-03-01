import json
import sys

player_name = sys.argv[1]

# --- Rutas a los archivos ---
ff_json_file = 'player_stats/'+player_name+'/futfantasy.json'
ss_json_file = 'player_stats/'+player_name+'/sofascore_all_matches.json'

# --- Cargar JSON ---
with open(ff_json_file, 'r', encoding='utf-8') as f:
    ff_data = json.load(f)

with open(ss_json_file, 'r', encoding='utf-8') as f:
    ss_data = json.load(f)


# --- Crear índice FutbolFantasy SOLO por fecha ---
ff_index = {}

for partido in ff_data:
    fecha = partido.get("fecha_normalizada")

    if not fecha:
        continue

    # Guardamos lista por si hay más de un partido el mismo día
    ff_index.setdefault(fecha, []).append(partido)


# --- Combinar con SofaScore ---
combined_matches = []

for match_id, match_obj in ss_data.items():

    fecha = match_obj['match_info'].get("fecha_normalizada")

    if not fecha:
        continue

    if fecha in ff_index:

        # Puede haber varios partidos el mismo día
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


# --- Guardar resultado ---
with open('player_stats/'+player_name+'/full_stats.json', 'w', encoding='utf-8') as f:
    json.dump(combined_matches, f, ensure_ascii=False, indent=2)

print(f"Se han combinado {len(combined_matches)} partidos.")
