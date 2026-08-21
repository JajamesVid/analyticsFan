import json
import os
import re
import time
import random
import httpx
from datetime import datetime

from futFantasy_Pipeline import crear_sesion, parsear_partidos

PLAYERS_JSON = "players_to_analyze.json"

# temporadas que ya tenemos descargadas y viven juntas en la carpeta "22_25"
HISTORICAL_SEASONS = {"22/23", "23/24", "24/25", "25/26"}
HISTORICAL_FOLDER = "22_25"

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


def season_folder_name(season_year):
    """Las temporadas ya descargadas (22/23 a 25/26) viven juntas en HISTORICAL_FOLDER.
    Cualquier temporada nueva (26/27 en adelante) recibe su propia subcarpeta."""
    if not season_year or season_year in HISTORICAL_SEASONS:
        return HISTORICAL_FOLDER

    return season_year.replace("/", "_")


def team_folder_for_season(team_name, season_year):
    return os.path.join("team_stats", normalize(team_name), season_folder_name(season_year))


def player_folder_for_season(team_name, player_name, season_year):
    return os.path.join("player_stats", normalize(team_name), player_name, season_folder_name(season_year))


def create_session():
    return httpx.Client(headers=random_headers())


def normalize_team(name):
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def parse_ss_date(timestamp):
    if not timestamp:
        return None
    try:
        return datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d")
    except:
        return None


def filter_last_matchday(events, team_id):
    """De todos los eventos de un equipo/jugador, se queda solo con el partido
    de LaLiga más reciente (el de mayor startTimestamp), sea de la temporada
    que sea — así siempre coge la última jornada disputada, dinámicamente."""
    laliga_events = [
        e for e in events
        if (e.get("homeTeam", {}).get("id") == team_id or e.get("awayTeam", {}).get("id") == team_id)
        and e.get("tournament", {}).get("name") == "LaLiga"
        and e.get("status", {}).get("type") == "finished"
    ]

    if not laliga_events:
        return []

    last_event = max(laliga_events, key=lambda e: e.get("startTimestamp", 0))

    return [last_event]


def update_team_stats(session, team_name, team_id):
    try:
        resp = session.get(
            f"https://www.sofascore.com/api/v1/team/{team_id}/events/last/0",
            headers={"Referer": f"https://www.sofascore.com/football/team/{team_id}"}
        )
        events = resp.json().get("events", [])
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False

    events = filter_last_matchday(events, team_id)

    if not events:
        print(f"  ⏭ Sin partidos de LaLiga")
        return False

    event = events[0]
    event_id = str(event["id"])
    season_year = event.get("season", {}).get("year")

    team_folder = team_folder_for_season(team_name, season_year)
    output_file = os.path.join(team_folder, "sofascore_all_matches.json")

    existing = {}
    if os.path.exists(output_file):
        with open(output_file) as f:
            try:
                existing = json.load(f)
            except:
                pass

    if event_id in existing:
        print(f"  ⏭ Sin eventos nuevos")
        return False

    print(f"  → 1 evento nuevo ({season_year})")

    try:
        resp = session.get(f"https://www.sofascore.com/api/v1/event/{event_id}/statistics")
        raw_stats = resp.json()
    except Exception as e:
        print(f"  ❌ Error stats {event_id}: {e}")
        return False

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
            "season": season_year,
            "jornada": event.get("roundInfo", {}).get("round")
        },
        "statistics": raw_stats.get("statistics", [])
    }

    print(f"  ✔️ {event_id}")
    sleep()

    os.makedirs(team_folder, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)

    return True


def update_player_stats(session, player_name, player_id, team_name, team_id):
    try:
        resp = session.get(
            f"https://www.sofascore.com/api/v1/player/{player_id}/events/last/0",
            headers={"Referer": f"https://www.sofascore.com/football/player/{player_id}"}
        )
        events = resp.json().get("events", [])
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return {}, None

    events = filter_last_matchday(events, team_id)

    if not events:
        print(f"  ⏭ Sin partidos de LaLiga")
        return {}, None

    event = events[0]
    event_id = str(event["id"])
    season_year = event.get("season", {}).get("year")

    player_folder = player_folder_for_season(team_name, player_name, season_year)
    output_file = os.path.join(player_folder, "sofascore_all_matches.json")

    existing = {}
    if os.path.exists(output_file):
        with open(output_file) as f:
            try:
                existing = json.load(f)
            except:
                pass

    if event_id in existing:
        print(f"  ⏭ Sin eventos nuevos")
        return {}, player_folder

    print(f"  → 1 evento nuevo ({season_year})")

    try:
        resp = session.get(
            f"https://www.sofascore.com/api/v1/event/{event_id}/player/{player_id}/statistics"
        )
        match_stats = resp.json()
    except Exception as e:
        print(f"  ❌ Error stats {event_id}: {e}")
        return {}, player_folder

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
            "slug": event.get("slug"),
            "season": season_year,
            "jornada": event.get("roundInfo", {}).get("round")
        },
        "player_stats": match_stats
    }

    print(f"  ✔️ {event_id}")
    sleep()

    os.makedirs(player_folder, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)

    return {event_id: existing[event_id]}, player_folder


def fetch_futfantasy_season(ff_session, player_slug, season):
    url = f"https://www.futbolfantasy.com/jugadores/{player_slug}/laliga-{season}"

    try:
        resp = ff_session.get(url, timeout=15)
        if resp.status_code != 200:
            print(f"  ⚠️ FutFantasy {resp.status_code} en {url}")
            return []
    except Exception as e:
        print(f"  ❌ Error FutFantasy: {e}")
        return []

    return parsear_partidos([resp.text])


def find_partido_for_event(partidos, match_info):
    home_n = normalize_team(match_info.get("homeTeam", {}).get("name"))
    away_n = normalize_team(match_info.get("awayTeam", {}).get("name"))

    for partido in reversed(partidos):
        local_n = normalize_team(partido["local"]["nombre"])
        visit_n = normalize_team(partido["visitante"]["nombre"])

        if (home_n and (home_n in local_n or local_n in home_n)) and \
           (away_n and (away_n in visit_n or visit_n in away_n)):
            return partido

    return None


def update_futfantasy_and_merge(ff_session, player_name, player_folder, new_sofascore_events):
    if not new_sofascore_events:
        return

    ff_file = os.path.join(player_folder, "futfantasy.json")
    full_file = os.path.join(player_folder, "full_stats.json")

    ff_data = []
    if os.path.exists(ff_file):
        with open(ff_file) as f:
            try:
                ff_data = json.load(f)
            except:
                ff_data = []

    full_data = []
    if os.path.exists(full_file):
        with open(full_file) as f:
            try:
                full_data = json.load(f)
            except:
                full_data = []

    full_event_ids = {m.get("sofascore", {}).get("id") for m in full_data}
    ff_urls = {p.get("url_ficha") for p in ff_data if p.get("url_ficha")}
    ff_cache = {}

    for event_id, sofa_entry in new_sofascore_events.items():
        event_int = int(event_id)

        if event_int in full_event_ids:
            continue

        season_year = sofa_entry["match_info"].get("season")
        if not season_year:
            print(f"  ⚠️ Sin temporada registrada para el evento {event_id}, no se puede consultar FutFantasy")
            continue

        season_ff = season_year.replace("/", "-")
        if season_ff not in ff_cache:
            ff_cache[season_ff] = fetch_futfantasy_season(ff_session, player_name, season_ff)
            sleep()

        partido = find_partido_for_event(ff_cache[season_ff], sofa_entry["match_info"])

        if partido is None:
            print(f"  ⚠️ Sin partido de FutFantasy para el evento {event_id}")
            continue

        if not partido.get("url_ficha") or partido.get("url_ficha") not in ff_urls:
            ff_data.append(partido)

        full_data.append({
            "equipos": {
                "local": partido["local"],
                "visitante": partido["visitante"]
            },
            "resultado": partido["resultado"],
            "fecha": parse_ss_date(sofa_entry["match_info"].get("startTimestamp")),
            "url_ficha": partido["url_ficha"],
            "puntuaciones": partido["puntuaciones"],
            "sofascore": sofa_entry
        })
        full_event_ids.add(event_int)

        print(f"  ✔️ FutFantasy + merge OK ({event_id})")

    with open(ff_file, "w", encoding="utf-8") as f:
        json.dump(ff_data, f, ensure_ascii=False, indent=2)

    with open(full_file, "w", encoding="utf-8") as f:
        json.dump(full_data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    with open(PLAYERS_JSON) as f:
        teams = json.load(f).get("teams", [])

    session = create_session()
    ff_session = crear_sesion()

    for i, team in enumerate(teams, 1):
        team_name = team["name"]
        team_id = team["sofascore_id"]
        players = team["players"]

        print(f"\n{'='*50}")
        print(f"Equipo {i}/{len(teams)}: {team_name}")
        print(f"{'='*50}")

        print(f"\n🟢 Stats de equipo")
        team_has_new_event = update_team_stats(session, team_name, team_id)
        sleep()

        if not team_has_new_event:
            print(f"  ⏭ El equipo no tiene partido nuevo, se salta a los jugadores")
            continue

        print(f"\n🔵 Jugadores ({len(players)})")
        for player in players:
            name = player["name"]
            sofa_id = player["sofascore_id"]
            print(f"\n  → {name}")

            new_events, player_folder = update_player_stats(session, name, sofa_id, team_name, team_id)
            sleep()

            if new_events:
                update_futfantasy_and_merge(ff_session, name, player_folder, new_events)
                sleep()

        sleep()

    print("\n✔ Actualización completada")
