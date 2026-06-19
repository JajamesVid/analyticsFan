import time
import httpx
from slugify import slugify

BASE_URL = "https://api.sofascore.com/api/v1"

LALIGA_TOURNAMENT_ID = 8


class SofaScoreClient:
    def __init__(self, timeout=10.0):
        self.client = httpx.Client(timeout=timeout)

    def get_team_id(self, team_name: str) -> int:
        url = f"{BASE_URL}/search/all"
        params = {"q": team_name}

        resp = self.client.get(url, params=params)
        resp.raise_for_status()

        data = resp.json()

        for result in data.get("results", []):
            if result.get("type") == "team":
                return result["entity"]["id"]

        raise ValueError(f"Team not found: {team_name}")

    def get_squad(self, team_id: int):
        url = f"{BASE_URL}/team/{team_id}/players"

        resp = self.client.get(url)
        resp.raise_for_status()

        return resp.json().get("players", [])

    def format_player(self, player: dict) -> dict:
        p = player["player"]

        return {
            "name": slugify(p.get("slug") or p.get("name")),
            "sofascore_id": p["id"],
        }

    def get_team_players(self, team_name: str) -> dict:
        team_id = self.get_team_id(team_name)
        squad = self.get_squad(team_id)

        return {
            "players": [self.format_player(p) for p in squad]
        }

    def get_league_seasons(self, tournament_id: int) -> list:
        url = f"{BASE_URL}/unique-tournament/{tournament_id}/seasons"
        resp = self.client.get(url)
        resp.raise_for_status()
        return resp.json().get("seasons", [])

    def get_league_teams(self, tournament_id: int, season_id: int) -> list:
        url = f"{BASE_URL}/unique-tournament/{tournament_id}/season/{season_id}/teams"
        resp = self.client.get(url)
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

            result.append({
                "name": team_name,
                "sofascore_id": team_id,
                "players": players,
            })

            time.sleep(0.3)

        return {"teams": result}


def main():
    import sys
    import json

    if len(sys.argv) < 2:
        print("Usage: python script.py 'Real Madrid'")
        return

    team_name = sys.argv[1]

    client = SofaScoreClient()

    try:
        result = client.get_team_players(team_name)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()