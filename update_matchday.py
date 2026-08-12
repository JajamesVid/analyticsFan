import json
import os
import time
import random
import httpx

PLAYERS_JSON = "players_to_analyze.json"
TARGET_SEASON = "25/26"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:136.0) Gecko/20100101 Firefox/136.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36 Edg/141.0.0.0",
]

ACCEPT_LANGUAGES = [
    "en-US,en;q=0.9",
    "en-GB,en;q=0.8",
    "es-ES,es;q=0.9,en;q=0.8",
    "en-US,en;q=0.5",
    "es;q=0.9,en-US;q=0.8,en;q=0.7",
    "en-US,en;q=0.9,es;q=0.7",
]


def random_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "*/*",
        "Accept-Language": random.choice(ACCEPT_LANGUAGES),
        "X-Requested-With": "463ab6",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }


def sleep():
    time.sleep(random.uniform(1.0, 3.0))


def normalize(name):
    return name.lower().replace(" ", "_")


def create_session():
    return httpx.Client(headers=random_headers())


def filter_last_matchday(events, team_id):
    """De todos los eventos de un equipo/jugador, se queda solo con los de
    LaLiga de la temporada TARGET_SEASON, y de esos solo con la última jornada."""
    laliga_events = [
        e for e in events
        if (e.get("homeTeam", {}).get("id") == team_id or e.get("awayTeam", {}).get("id") == team_id)
        and e.get("tournament", {}).get("name") == "LaLiga"
        and e.get("season", {}).get("year") == TARGET_SEASON
    ]

    if not laliga_events:
        return []

    last_round = max(e.get("roundInfo", {}).get("round", 0) for e in laliga_events)

    return [e for e in laliga_events if e.get("roundInfo", {}).get("round") == last_round]


def update_team_stats(session, team_name, team_id):
    team_folder = normalize(team_name)
    output_file = os.path.join("team_stats", team_folder, "sofascore_all_matches.json")

    existing = {}
    if os.path.exists(output_file):
        with open(output_file) as f:
            try:
                existing = json.load(f)
            except:
                pass

    existing_ids = set(existing.keys())

    try:
        resp = session.get(
            f"https://www.sofascore.com/api/v1/team/{team_id}/events/last/0",
            headers={"Referer": f"https://www.sofascore.com/football/team/{team_id}"}
        )
        events = resp.json().get("events", [])
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return 0

    events = filter_last_matchday(events, team_id)

    new_events = {str(e["id"]): e for e in events if str(e["id"]) not in existing_ids}

    if not new_events:
        print(f"  ⏭ Sin eventos nuevos")
        return 0

    print(f"  → {len(new_events)} eventos nuevos")

    for event_id, event in new_events.items():
        try:
            resp = session.get(f"https://www.sofascore.com/api/v1/event/{event_id}/statistics")
            raw_stats = resp.json()
        except Exception as e:
            print(f"  ❌ Error stats {event_id}: {e}")
            continue

        home = event.get("homeTeam", {})
        away = event.get("awayTeam", {})

        existing[event_id] = {
            "id": int(event_id),
            "match_info": {
                "homeTeam": {
                    "id": home.get("id"),
                    "name": home.get("name"),
                    "shortName": home.get("shortName") or (home.get("name") or "")[:3].upper(),
                    "color": home.get("teamColors", {}).get("primary"),
                    "score": event.get("homeScore", {}).get("current") if event.get("homeScore") else None
                },
                "awayTeam": {
                    "id": away.get("id"),
                    "name": away.get("name"),
                    "shortName": away.get("shortName") or (away.get("name") or "")[:3].upper(),
                    "color": away.get("teamColors", {}).get("primary"),
                    "score": event.get("awayScore", {}).get("current") if event.get("awayScore") else None
                },
                "startTimestamp": event.get("startTimestamp"),
                "slug": event.get("slug"),
                "tournament": event.get("tournament", {}).get("name"),
                "season": event.get("season", {}).get("name")
            },
            "statistics": raw_stats.get("statistics", [])
        }

        print(f"  ✔️ {event_id}")
        sleep()

    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)

    return len(new_events)


def update_player_stats(session, player_name, player_id, team_name, team_id):
    team_folder = normalize(team_name)
    player_folder = os.path.join("player_stats", team_folder, player_name)
    output_file = os.path.join(player_folder, "sofascore_all_matches.json")

    existing = {}
    if os.path.exists(output_file):
        with open(output_file) as f:
            try:
                existing = json.load(f)
            except:
                pass

    existing_ids = set(existing.keys())

    try:
        resp = session.get(
            f"https://www.sofascore.com/api/v1/player/{player_id}/events/last/0",
            headers={"Referer": f"https://www.sofascore.com/football/player/{player_id}"}
        )
        events = resp.json().get("events", [])
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return 0

    events = filter_last_matchday(events, team_id)

    new_events = {str(e["id"]): e for e in events if str(e["id"]) not in existing_ids}

    if not new_events:
        print(f"  ⏭ Sin eventos nuevos")
    else:
        print(f"  → {len(new_events)} eventos nuevos")

        for event_id, event in new_events.items():
            try:
                resp = session.get(
                    f"https://www.sofascore.com/api/v1/event/{event_id}/player/{player_id}/statistics"
                )
                match_stats = resp.json()
            except Exception as e:
                print(f"  ❌ Error stats {event_id}: {e}")
                continue

            home = event.get("homeTeam", {})
            away = event.get("awayTeam", {})

            existing[event_id] = {
                "id": int(event_id),
                "match_info": {
                    "homeTeam": {
                        "name": home.get("name"),
                        "shortName": home.get("shortName") or (home.get("name") or "")[:3].upper(),
                        "color": home.get("teamColors", {}).get("primary"),
                        "score": event.get("homeScore", {}).get("current") if event.get("homeScore") else None
                    },
                    "awayTeam": {
                        "name": away.get("name"),
                        "shortName": away.get("shortName") or (away.get("name") or "")[:3].upper(),
                        "color": away.get("teamColors", {}).get("primary"),
                        "score": event.get("awayScore", {}).get("current") if event.get("awayScore") else None
                    },
                    "startTimestamp": event.get("startTimestamp"),
                    "slug": event.get("slug")
                },
                "player_stats": match_stats
            }

            print(f"  ✔️ {event_id}")
            sleep()

        os.makedirs(player_folder, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)

    return len(new_events)


if __name__ == "__main__":
    with open(PLAYERS_JSON) as f:
        teams = json.load(f).get("teams", [])

    session = create_session()

    for i, team in enumerate(teams, 1):
        team_name = team["name"]
        team_id = team["sofascore_id"]
        players = team["players"]

        print(f"\n{'='*50}")
        print(f"Equipo {i}/{len(teams)}: {team_name}")
        print(f"{'='*50}")

        print(f"\n🟢 Stats de equipo")
        update_team_stats(session, team_name, team_id)
        sleep()

        print(f"\n🔵 Jugadores ({len(players)})")
        for player in players:
            name = player["name"]
            sofa_id = player["sofascore_id"]
            print(f"\n  → {name}")

            update_player_stats(session, name, sofa_id, team_name, team_id)
            sleep()

        sleep()

    print("\n✔ Actualización completada")
