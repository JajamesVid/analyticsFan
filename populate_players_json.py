import json
import sys
from get_sofa_ids import SofaScoreClient, LALIGA_TOURNAMENT_ID

OUTPUT_FILE = "players_to_analyze.json"


def main():
    client = SofaScoreClient()

    print("📡 Obteniendo temporadas de LaLiga...")
    seasons = client.get_league_seasons(LALIGA_TOURNAMENT_ID)

    if not seasons:
        print("❌ No se encontraron temporadas")
        sys.exit(1)

    # La API devuelve la más reciente primero
    current_season = seasons[0]
    season_id = current_season["id"]
    season_name = current_season["name"]

    print(f"✅ Temporada detectada: {season_name} (ID: {season_id})")
    print(f"\n📋 Obteniendo equipos y plantillas...\n")

    data = client.get_all_league_teams_with_players(LALIGA_TOURNAMENT_ID, season_id)

    total_players = sum(len(t["players"]) for t in data["teams"])
    print(f"\n💾 Guardando {len(data['teams'])} equipos y {total_players} jugadores en {OUTPUT_FILE}")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"✔ Listo: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
