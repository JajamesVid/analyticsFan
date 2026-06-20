import sys
import json
import time
import httpx
from slugify import slugify

BASE_URL = "https://api.sofascore.com/api/v1"
LALIGA_TOURNAMENT_ID = 8
OUTPUT_FILE = "players_to_analyze.json"


class SofaScoreClient:
    def __init__(self, timeout=10.0):
        self.client = httpx.Client(timeout=timeout)

    def get_team_id(self, team_name: str) -> int:
        url = f"{BASE_URL}/search/all"
        resp = self.client.get(url, params={"q": team_name})
        resp.raise_for_status()
        for result in resp.json().get("results", []):
            if result.get("type") == "team":
                return result["entity"]["id"]
        raise ValueError(f"Team not found: {team_name}")

    def get_squad(self, team_id: int):
        resp = self.client.get(f"{BASE_URL}/team/{team_id}/players")
        resp.raise_for_status()
        return resp.json().get("players", [])

    def format_player(self, player: dict) -> dict:
        p = player["player"]
        return {
            "name": slugify(p.get("slug") or p.get("name")),
            "sofascore_id": p["id"],
        }

    def get_league_seasons(self, tournament_id: int) -> list:
        resp = self.client.get(f"{BASE_URL}/unique-tournament/{tournament_id}/seasons")
        resp.raise_for_status()
        return resp.json().get("seasons", [])

    def get_league_teams(self, tournament_id: int, season_id: int) -> list:
        resp = self.client.get(f"{BASE_URL}/unique-tournament/{tournament_id}/season/{season_id}/teams")
        resp.raise_for_status()
        return resp.json().get("teams", [])

    def get_all_league_teams_with_players(self, tournament_id: int, season_id: int) -> dict:
        teams = self.get_league_teams(tournament_id, season_id)
        result = []
        for team in teams:
            team_id = team["id"]
            team_name = team["name"]
            print(f"  → {team_name} (ID: {team_id})")
            try:
                squad = self.get_squad(team_id)
                players = [self.format_player(p) for p in squad]
            except Exception as e:
                print(f"    ❌ Error obteniendo plantilla: {e}")
                players = []
            result.append({"name": team_name, "sofascore_id": team_id, "players": players})
            time.sleep(0.3)
        return {"teams": result}


def populate():
    client = SofaScoreClient()

    print("📡 Obteniendo temporadas de LaLiga...")
    seasons = client.get_league_seasons(LALIGA_TOURNAMENT_ID)

    if not seasons:
        print("❌ No se encontraron temporadas")
        sys.exit(1)

    current_season = seasons[0]
    print(f"✅ Temporada: {current_season['name']} (ID: {current_season['id']})")
    print("\n📋 Obteniendo equipos y plantillas...\n")

    data = client.get_all_league_teams_with_players(LALIGA_TOURNAMENT_ID, current_season["id"])
    total_players = sum(len(t["players"]) for t in data["teams"])

    print(f"\n💾 Guardando {len(data['teams'])} equipos y {total_players} jugadores en {OUTPUT_FILE}")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"✔ Listo: {OUTPUT_FILE}")


if __name__ == "__main__":
    populate()
