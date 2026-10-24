import json
import os
import re
import time
import random
import httpx
from datetime import datetime

from futFantasy_Pipeline import crear_sesion, parsear_partidos

PLAYERS_JSON = "players_to_analyze_26_27.json"

# temporadas que ya tenemos descargadas y viven juntas en la carpeta "22_25"
HISTORICAL_SEASONS = {"22/23", "23/24", "24/25", "25/26"}
HISTORICAL_FOLDER = "22_25"

# sin User-Agents de Chrome/Edge: SofaScore compara el UA con la huella TLS
# de la conexión, y httpx no se parece a un Chrome real → 403 "challenge".
# Con UA de Firefox/Safari pasa (y X-Requested-With da igual).
USER_AGENTS = [
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:136.0) Gecko/20100101 Firefox/136.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
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
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "X-Requested-With": "78e7e7",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "Connection": "keep-alive",
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


def discover_current_season_folders(team_name, player_name):
    """Subcarpetas de temporada "activa" (todo menos el histórico 22_25) que
    ya existan para este jugador. Se usa para reintentar el cruce con
    FutFantasy de partidos que ya tienen SofaScore pero se quedaron sin
    `full_stats.json` en una ejecución anterior (p.ej. porque el nombre del
    jugador en FutFantasy no coincidía)."""
    base = os.path.join("player_stats", normalize(team_name), player_name)

    if not os.path.isdir(base):
        return []

    return [
        os.path.join(base, d) for d in os.listdir(base)
        if d != HISTORICAL_FOLDER and os.path.isdir(os.path.join(base, d))
    ]


def get_live_api_headers(user_agent):
    """SofaScore manda headers anti-bot que rotan (X-Requested-With cambió
    de valor de un día para otro, y hay un x-captcha con JWT de ~1h atado
    a la IP) — intentar adivinarlos o dejarlos fijos en el código caduca
    solo. En vez de eso, abrimos un Chrome headless con seleniumwire (que
    permite INSPECCIONAR las peticiones reales que hace el navegador),
    visitamos una página que dispare llamadas a su API, y copiamos tal
    cual los headers que el propio navegador mandó en una de ellas.

    Devuelve (headers_capturados: dict, cookies: dict). Si no se consigue
    capturar nada, devuelve ({}, {}) y el llamador sigue con los headers
    fijos de random_headers() (arriesgándose a un 403)."""
    from seleniumwire import webdriver
    from webdriver_manager.chrome import ChromeDriverManager
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options

    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--ignore-certificate-errors")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )

    try:
        driver.execute_cdp_cmd("Network.setUserAgentOverride", {"userAgent": user_agent})

        print("🌍 Capturando headers reales de SofaScore (home)...")
        # la home ya dispara de sobra llamadas a /api/v1/... (marcador en vivo, etc.)
        driver.get("https://www.sofascore.com")

        captured = {}
        api_requests_seen = 0

        for _ in range(25):
            for req in driver.requests:
                if "/api/v1/" not in req.url:
                    continue
                api_requests_seen += 1
                if not req.response:
                    continue
                for key in ("x-requested-with", "x-captcha"):
                    value = req.headers.get(key)
                    if value and key not in captured:
                        captured[key] = value
                if "x-requested-with" in captured and "x-captcha" in captured:
                    break
            if "x-requested-with" in captured and "x-captcha" in captured:
                break
            time.sleep(1)

        cookies = {c["name"]: c["value"] for c in driver.get_cookies()}

        if captured:
            print(f"🔑 Headers capturados: {', '.join(captured.keys())}")
        else:
            # diagnóstico: ¿no hubo NINGUNA llamada a la API (interceptación
            # rota) o hubo llamadas pero sin esos headers (otra causa)?
            print(f"⚠️ No se capturaron los headers. Peticiones totales: {len(driver.requests)}, "
                  f"a /api/v1/: {api_requests_seen}, cookies: {list(cookies.keys())}")
            if driver.requests:
                sample = [r.url for r in driver.requests[:5]]
                print(f"   Primeras URLs vistas: {sample}")

        return captured, cookies
    finally:
        driver.quit()


def create_session():
    user_agent = random.choice(USER_AGENTS)
    headers = random_headers()
    headers["User-Agent"] = user_agent

    captured_headers, cookies = get_live_api_headers(user_agent)
    headers.update(captured_headers)

    session = httpx.Client(headers=headers)

    for name, value in cookies.items():
        session.cookies.set(name, value, domain="www.sofascore.com")

    return session


def normalize_team(name):
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def parse_ss_date(timestamp):
    if not timestamp:
        return None
    try:
        return datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d")
    except:
        return None


class Budget:
    """Límite de cuántas JORNADAS distintas (completas: todos los equipos
    y todos sus jugadores) se ponen al día en esta ejecución. Permite
    relanzar el script varias veces e ir avanzando jornada a jornada en
    vez de descargar todo el atraso de golpe.

    `allowed` se fija de antemano con `seed()` (la(s) jornada(s) más
    antigua(s) que falten de verdad en la liga) — no se va rellenando
    sobre la marcha según a qué equipo le toque primero, porque eso
    puede dejar huecos si un equipo ya tiene alguna jornada posterior
    pero no la más antigua."""

    def __init__(self, n):
        self.max_jornadas = n
        self.allowed = set()
        self.missing = set()

    def seed(self, missing_jornadas):
        self.missing = set(missing_jornadas)
        self.allowed = set(sorted(missing_jornadas)[:self.max_jornadas])

    def allows(self, jornada):
        return jornada in self.allowed

    def is_closed(self, jornada):
        """La jornada ya la tienen todos los equipos (no falta en la liga)."""
        return jornada not in self.missing


def filter_laliga_matches(events, team_id):
    """Todos los partidos de LaLiga ya finalizados de este equipo/jugador,
    ordenados del más antiguo al más reciente. Antes solo devolvíamos el
    último, pero si se acumulan varias jornadas sin actualizar hace falta
    recuperarlas todas (el filtrado por `existing` se hace en el llamador)."""
    laliga_events = [
        e for e in events
        if (e.get("homeTeam", {}).get("id") == team_id or e.get("awayTeam", {}).get("id") == team_id)
        and e.get("tournament", {}).get("name") == "LaLiga"
        and e.get("status", {}).get("type") == "finished"
        # events/last también trae partidos de la temporada pasada: el
        # histórico (22_25) ya está descargado, solo nos interesa la activa
        and e.get("season", {}).get("year") not in HISTORICAL_SEASONS | {None}
    ]

    laliga_events.sort(key=lambda e: e.get("startTimestamp", 0))

    return laliga_events


def fetch_events(session, url, referer):
    """Devuelve (events, error). Si SofaScore bloquea/limita la petición
    suele devolver 200 con un JSON de error en vez de lanzar una excepción,
    así que hay que comprobarlo explícitamente — si no, parecería
    simplemente "sin partidos nuevos" cuando en realidad es un bloqueo."""
    try:
        resp = session.get(url, headers={"Referer": referer})
    except Exception as e:
        return [], f"petición fallida: {e}"

    if resp.status_code != 200:
        return [], f"HTTP {resp.status_code}"

    try:
        data = resp.json()
    except Exception as e:
        return [], f"respuesta no es JSON: {e}"

    if "events" not in data:
        return [], f"respuesta inesperada: {str(data)[:200]}"

    return data["events"], None


def fetch_json(session, url):
    """Igual que fetch_events pero para endpoints que no devuelven una lista
    de eventos (ej. /statistics) — misma idea: un bloqueo silencioso de
    SofaScore no debe confundirse con "sin datos"."""
    try:
        resp = session.get(url)
    except Exception as e:
        return None, f"petición fallida: {e}"

    if resp.status_code != 200:
        return None, f"HTTP {resp.status_code}"

    try:
        return resp.json(), None
    except Exception as e:
        return None, f"respuesta no es JSON: {e}"


def discover_missing_jornadas(session, teams, stats):
    """Pasada previa barata (solo a nivel de equipo, sin guardar nada) para
    saber qué números de jornada faltan DE VERDAD en la liga — así el cupo
    de la ejecución siempre va a por la(s) más antigua(s) pendiente(s), en
    vez de a por la que le toque primero al equipo que se procese antes."""
    missing = set()

    for team in teams:
        team_name = team["name"]
        team_id = team["sofascore_id"]

        events, error = fetch_events(
            session,
            f"https://www.sofascore.com/api/v1/team/{team_id}/events/last/0",
            f"https://www.sofascore.com/football/team/{team_id}"
        )
        if error:
            print(f"  ❌ {team_name}: {error}")
            stats["errors"] += 1
            continue

        events = filter_laliga_matches(events, team_id)

        folders_cache = {}
        for event in events:
            event_id = str(event["id"])
            season_year = event.get("season", {}).get("year")
            team_folder = team_folder_for_season(team_name, season_year)

            if team_folder not in folders_cache:
                existing = {}
                output_file = os.path.join(team_folder, "sofascore_all_matches.json")
                if os.path.exists(output_file):
                    with open(output_file) as f:
                        try:
                            existing = json.load(f)
                        except:
                            pass
                folders_cache[team_folder] = existing

            if event_id not in folders_cache[team_folder]:
                missing.add(event.get("roundInfo", {}).get("round"))

        sleep()

    return missing


def update_team_stats(session, team_name, team_id, budget, stats):
    """Devuelve (saved, has_pending): saved = partidos nuevos guardados en
    esta llamada (solo los de jornadas admitidas por el presupuesto);
    has_pending = si el equipo tiene ALGÚN partido de LaLiga sin descargar
    todavía, esté o no dentro del cupo de esta ejecución (sirve para decidir
    si merece la pena mirar también a sus jugadores)."""
    events, error = fetch_events(
        session,
        f"https://www.sofascore.com/api/v1/team/{team_id}/events/last/0",
        f"https://www.sofascore.com/football/team/{team_id}"
    )

    if error:
        print(f"  ❌ Error: {error}")
        stats["errors"] += 1
        return 0, False

    events = filter_laliga_matches(events, team_id)

    if not events:
        print(f"  ⏭ Sin partidos de LaLiga")
        return 0, False

    folders_cache = {}
    saved = 0
    has_pending = False

    for event in events:
        event_id = str(event["id"])
        season_year = event.get("season", {}).get("year")

        team_folder = team_folder_for_season(team_name, season_year)
        output_file = os.path.join(team_folder, "sofascore_all_matches.json")

        if team_folder not in folders_cache:
            existing = {}
            if os.path.exists(output_file):
                with open(output_file) as f:
                    try:
                        existing = json.load(f)
                    except:
                        pass
            folders_cache[team_folder] = existing

        existing = folders_cache[team_folder]

        if event_id in existing:
            continue

        has_pending = True

        jornada = event.get("roundInfo", {}).get("round")
        if not budget.allows(jornada):
            continue

        print(f"  → evento nuevo {event_id} ({season_year}, jornada {jornada})")

        raw_stats, error = fetch_json(session, f"https://www.sofascore.com/api/v1/event/{event_id}/statistics")
        if error:
            print(f"  ❌ Error stats {event_id}: {error}")
            stats["errors"] += 1
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
                "season": season_year,
                "jornada": jornada
            },
            "statistics": raw_stats.get("statistics", [])
        }

        saved += 1
        print(f"  ✔️ {event_id}")
        sleep()

        os.makedirs(team_folder, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)

    if not has_pending:
        print(f"  ⏭ Sin eventos nuevos")
    elif saved == 0:
        print(f"  ⏭ Tiene jornadas pendientes, pero ninguna dentro del cupo de esta ejecución")

    return saved, has_pending


def update_player_stats(session, player_name, player_id, team_name, team_id, budget, stats):
    """Devuelve added_by_folder: {carpeta_de_temporada: {event_id: entry}}
    con lo nuevo guardado en esta llamada (solo jornadas admitidas por el
    presupuesto; normalmente una sola carpeta, salvo cambio de temporada)."""
    events, error = fetch_events(
        session,
        f"https://www.sofascore.com/api/v1/player/{player_id}/events/last/0",
        f"https://www.sofascore.com/football/player/{player_id}"
    )

    if error:
        print(f"  ❌ Error: {error}")
        stats["errors"] += 1
        return {}

    events = filter_laliga_matches(events, team_id)

    if not events:
        print(f"  ⏭ Sin partidos de LaLiga")
        return {}

    folders_cache = {}
    team_events_cache = {}
    added_by_folder = {}
    has_pending = False

    for event in events:
        event_id = str(event["id"])
        season_year = event.get("season", {}).get("year")

        player_folder = player_folder_for_season(team_name, player_name, season_year)
        output_file = os.path.join(player_folder, "sofascore_all_matches.json")

        if player_folder not in folders_cache:
            existing = {}
            if os.path.exists(output_file):
                with open(output_file) as f:
                    try:
                        existing = json.load(f)
                    except:
                        pass
            folders_cache[player_folder] = existing

        existing = folders_cache[player_folder]

        if event_id in existing:
            continue

        has_pending = True

        # si el equipo ya tiene este partido y la jornada está cerrada en toda
        # la liga, es un hueco del jugador (p.ej. carpeta nueva tras corregir
        # su nombre de FutFantasy): se rellena aunque no entre en el cupo.
        # Si a algún equipo aún le falta esa jornada, espera a su turno.
        jornada = event.get("roundInfo", {}).get("round")
        team_file = os.path.join(team_folder_for_season(team_name, season_year), "sofascore_all_matches.json")
        if team_file not in team_events_cache:
            team_events_cache[team_file] = {}
            if os.path.exists(team_file):
                with open(team_file) as f:
                    try:
                        team_events_cache[team_file] = json.load(f)
                    except:
                        pass
        backfill = event_id in team_events_cache[team_file] and budget.is_closed(jornada)

        if not backfill and not budget.allows(jornada):
            continue

        print(f"  → evento nuevo {event_id} ({season_year}, jornada {jornada})")

        match_stats, error = fetch_json(
            session, f"https://www.sofascore.com/api/v1/event/{event_id}/player/{player_id}/statistics"
        )
        if error:
            print(f"  ❌ Error stats {event_id}: {error}")
            stats["errors"] += 1
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
                "slug": event.get("slug"),
                "season": season_year,
                "jornada": jornada
            },
            "player_stats": match_stats
        }

        added_by_folder.setdefault(player_folder, {})[event_id] = existing[event_id]
        print(f"  ✔️ {event_id}")
        sleep()

        os.makedirs(player_folder, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)

    if not has_pending:
        print(f"  ⏭ Sin eventos nuevos")
    elif not added_by_folder:
        print(f"  ⏭ Tiene jornadas pendientes, pero ninguna dentro del cupo de esta ejecución")

    return added_by_folder


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


def update_futfantasy_and_merge(ff_session, team_name, player_name, player_folder, new_sofascore_events, report):
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
            report.append({
                "team": team_name, "player": player_name, "event_id": event_id,
                "motivo": "sin temporada registrada en el dato de SofaScore",
            })
            continue

        season_ff = season_year.replace("/", "-")
        if season_ff not in ff_cache:
            ff_cache[season_ff] = fetch_futfantasy_season(ff_session, player_name, season_ff)
            sleep()

        partido = find_partido_for_event(ff_cache[season_ff], sofa_entry["match_info"])

        if partido is None:
            mi = sofa_entry["match_info"]
            rival = f"{mi.get('homeTeam', {}).get('name')} vs {mi.get('awayTeam', {}).get('name')}"
            print(f"  ⚠️ Sin partido de FutFantasy para el evento {event_id} ({rival})")
            report.append({
                "team": team_name, "player": player_name, "event_id": event_id,
                "partido": rival, "jornada": mi.get("jornada"),
                "motivo": "no se encontró el partido en FutFantasy (probable nombre distinto en esa web)",
            })
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
    import argparse

    parser = argparse.ArgumentParser(description="Actualiza los datos de LaLiga, jornada a jornada.")
    parser.add_argument(
        "--max-jornadas", type=int, default=1,
        help="Máximo de jornadas distintas (completas: todos los equipos y jugadores) a poner al "
             "día en esta ejecución (por defecto 1). Si queda atraso, vuelve a lanzar el script."
    )
    args = parser.parse_args()

    budget = Budget(args.max_jornadas)
    stats = {"errors": 0}
    report = []
    print(f"🎯 Presupuesto de esta ejecución: {args.max_jornadas} jornada(s)")

    with open(PLAYERS_JSON) as f:
        teams = json.load(f).get("teams", [])

    session = create_session()
    ff_session = crear_sesion()

    print("\n🔍 Comprobando qué jornadas faltan en la liga...")
    missing_jornadas = discover_missing_jornadas(session, teams, stats)
    budget.seed(missing_jornadas)

    if budget.allowed:
        print(f"📋 Esta ejecución pondrá al día la(s) jornada(s): {', '.join(str(j) for j in sorted(budget.allowed))}")
    elif missing_jornadas:
        print(f"📋 Faltan jornadas ({', '.join(str(j) for j in sorted(missing_jornadas))}) pero el cupo es 0, nada que hacer")
    else:
        print("✔ No se ha encontrado ninguna jornada pendiente en ningún equipo.")

    for i, team in enumerate(teams, 1):
        team_name = team["name"]
        team_id = team["sofascore_id"]
        players = team["players"]

        print(f"\n{'='*50}")
        print(f"Equipo {i}/{len(teams)}: {team_name}")
        print(f"{'='*50}")

        print(f"\n🟢 Stats de equipo")
        _, team_has_pending = update_team_stats(session, team_name, team_id, budget, stats)
        sleep()

        if not team_has_pending:
            print(f"  ⏭ El equipo ya está al día en SofaScore, pero se revisan igualmente "
                  f"los cruces de FutFantasy pendientes de sus jugadores")

        print(f"\n🔵 Jugadores ({len(players)})")
        for player in players:
            name = player["name"]
            sofa_id = player["sofascore_id"]
            print(f"\n  → {name}")

            if team_has_pending:
                added_by_folder = update_player_stats(session, name, sofa_id, team_name, team_id, budget, stats)
                sleep()
            else:
                added_by_folder = {}

            # además de lo recién descargado, reintenta el cruce con FutFantasy
            # de cualquier partido de la temporada activa que ya tenga SofaScore
            # pero se quedara sin full_stats.json (p.ej. nombre distinto en esa web)
            events_by_folder = dict(added_by_folder)
            for folder in discover_current_season_folders(team_name, name):
                ss_file = os.path.join(folder, "sofascore_all_matches.json")
                if not os.path.exists(ss_file):
                    continue
                with open(ss_file) as f:
                    try:
                        all_events = json.load(f)
                    except:
                        continue
                events_by_folder.setdefault(folder, {}).update(all_events)

            for player_folder, events in events_by_folder.items():
                update_futfantasy_and_merge(ff_session, team_name, name, player_folder, events, report)
                sleep()

        sleep()

    print(f"\n{'='*50}")
    if stats["errors"] == 0:
        if not budget.allowed:
            print(f"✔ Todo al día — no se ha encontrado ninguna jornada pendiente, no hay más que descargar.")
        else:
            jornadas = ", ".join(str(j) for j in sorted(budget.allowed))
            print(f"✔ Actualización completada, sin errores. Jornada(s) puesta(s) al día: {jornadas}")
            print("  Si todavía quedaba atraso de más jornadas, vuelve a lanzar el script para seguir.")
    else:
        print(f"⚠️ Terminado con {stats['errors']} error(es) de red/bloqueo — esto NO significa que esté todo al día.")
        print("  Espera un poco (puede ser un bloqueo temporal de SofaScore) y vuelve a lanzar el script.")

    report_path = "update_matchday_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "fecha": datetime.now().isoformat(),
            "jornadas_al_dia": sorted(budget.allowed),
            "errores_red": stats["errors"],
            "fallos_futfantasy": report,
        }, f, ensure_ascii=False, indent=2)

    if report:
        print(f"\n⚠️ {len(report)} partido(s) sin cruzar con FutFantasy (se reintentarán solos la próxima ejecución):")
        for fallo in report:
            detalle = fallo.get("partido", "")
            print(f"  - {fallo['team']} / {fallo['player']} / evento {fallo['event_id']} {detalle} — {fallo['motivo']}")
    else:
        print(f"\n✔ Sin fallos de cruce con FutFantasy en esta ejecución.")

    print(f"📄 Informe guardado en {report_path}")
