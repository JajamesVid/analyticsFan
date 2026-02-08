import json
import os

# Carpeta donde están los archivos JSON
FOLDER = "griezzifrom2022"  # Cambia a tu ruta si es necesario
OUTPUT_FILE = "griezzifrom2022_matchids.json"

resumen = {}

# Recorrer todos los archivos de la carpeta
for filename in os.listdir(FOLDER):
    if filename.endswith(".json"):
        filepath = os.path.join(FOLDER, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except Exception as e:
                print(f"⚠️ Error leyendo {filename}: {e}")
                continue

        # Cada archivo tiene un array "events"
        events = data.get("events", [])
        for event in events:
            event_id = str(event.get("id"))
            if not event_id:
                continue

            # Extraer información relevante
            resumen[event_id] = {
                "homeTeam": {
                    "name": event["homeTeam"].get("name"),
                    "shortName": event["homeTeam"].get("shortName"),
                    "color": event["homeTeam"]["teamColors"].get("primary") if event["homeTeam"].get("teamColors") else None,
                    "score": event["homeScore"].get("current") if event.get("homeScore") else None
                },
                "awayTeam": {
                    "name": event["awayTeam"].get("name"),
                    "shortName": event["awayTeam"].get("shortName"),
                    "color": event["awayTeam"]["teamColors"].get("primary") if event["awayTeam"].get("teamColors") else None,
                    "score": event["awayScore"].get("current") if event.get("awayScore") else None
                },
                "startTimestamp": event.get("startTimestamp"),
                "hasEventPlayerStatistics": event.get("hasEventPlayerStatistics"),
                "isEditor": event.get("isEditor"),
                "slug": event.get("slug"),
                "finalResultOnly": event.get("finalResultOnly")
            }

# Guardar resumen en un archivo
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(resumen, f, indent=2, ensure_ascii=False)

print(f"✅ Resumen generado en {OUTPUT_FILE}")
