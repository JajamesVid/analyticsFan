import json
import glob

# Carpeta donde están los JSONs de FutbolFantasy
ff_folder = "puntus_vinijr2226/data_json/"
ff_files = glob.glob(ff_folder + "*.json")

all_ff_data = []

# Cargar todos los JSON y combinar en una lista
for file in ff_files:
    with open(file, "r", encoding="utf-8") as f:
        data = json.load(f)
        # Si cada JSON es una lista de partidos
        all_ff_data.extend(data)

# Guardar en un solo JSON combinado
with open("futbolfantasy_combinado.json", "w", encoding="utf-8") as f:
    json.dump(all_ff_data, f, ensure_ascii=False, indent=2)

print(f"Se han combinado {len(all_ff_data)} partidos de FutbolFantasy.")



# import json
# import unidecode

# # --- Función para normalizar nombres de equipos ---
# def normalize_team(name):
#     name = name.strip().lower().replace(' ', '-')
#     name = unidecode.unidecode(name)  # elimina acentos
#     return name

# # --- Cargar JSONs ---
# with open('futbolfantasy_combinado.json', 'r', encoding='utf-8') as f:
#     ff_data = json.load(f)

# with open('player_stats/Vinicius_Jr_all_matches.json', 'r', encoding='utf-8') as f:
#     ss_data = json.load(f)

# # --- Crear listas de claves de equipos ---
# ff_keys = []
# for partido in ff_data:
#     local = normalize_team(partido['local']['nombre'])
#     visitante = normalize_team(partido['visitante']['nombre'])
#     key = f"{local}_{visitante}"
#     ff_keys.append(key)

# ss_keys = []
# for match_id, match_obj in ss_data.items():
#     local = normalize_team(match_obj['match_info']['homeTeam']['name'])
#     visitante = normalize_team(match_obj['match_info']['awayTeam']['name'])
#     key = f"{local}_{visitante}"
#     ss_keys.append(key)

# # --- Comparar listas y ver diferencias ---
# ff_set = set(ff_keys)
# ss_set = set(ss_keys)

# solo_ff = ff_set - ss_set
# solo_ss = ss_set - ff_set

# print(f"Partidos solo en FutbolFantasy ({len(solo_ff)}):")
# print(solo_ff)
# print()
# print(f"Partidos solo en SofaScore ({len(solo_ss)}):")
# print(solo_ss)
