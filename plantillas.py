"""Mantiene PLAYERS_JSON al día con las plantillas reales de LaLiga.

Fuentes:
- SofaScore /team/{id}/players: quién está en cada equipo (por id, sin
  ambigüedad).
- Página de equipo de FutFantasy (/laliga/equipos/{slug}): el slug que
  FutFantasy da a cada jugador. Es lo que va en "name": update_matchday lo usa
  como nombre de carpeta y como URL de FutFantasy, así que tiene que ser
  exactamente el suyo. Ojo: FutFantasy BORRA las letras con tilde en vez de
  quitarles la tilde ("Álvaro Djaló" -> "lvaro-djalo", "Arda Güler" ->
  "arda-gler"), por eso hay que emparejar y no basta con slugify(nombre).

Detecta:
- nuevos: en la plantilla de SofaScore pero no en la lista.
- traspasos: en la lista con otro equipo. Se mueven al nuevo: el filtro de
  partidos de update_matchday va por el id del equipo de la lista, así que
  con el equipo viejo no se descargaría ningún partido nuevo. Su carpeta del
  equipo anterior se queda como está (son sus partidos con ese equipo).
- renombrados: el "name" no es el slug de FutFantasy (cruce de FutFantasy
  roto). Se renombra también su carpeta en player_stats.
- bajas: en la lista pero en ninguna plantilla de LaLiga y sin partidos esta
  temporada. Se quitan para no gastar peticiones; sus carpetas no se tocan.
  Si ya han jugado esta temporada se mantienen (la plantilla de SofaScore
  varía de una consulta a otra con los canteranos).
- sin_futfantasy: sin slug en FutFantasy (canteranos, recién llegados). Se
  añaden con slugify al estilo FutFantasy; en cuanto FutFantasy los tenga,
  la siguiente sincronización los renombra.

Si falla la plantilla de algún equipo no se da de baja a nadie (no se puede
distinguir una baja de un traspaso a ese equipo).

Uso:
    python3 plantillas.py            # solo muestra los cambios
    python3 plantillas.py --aplicar  # los guarda en PLAYERS_JSON
"""
import difflib
import json
import os
import random
import re
import time
import unicodedata

import httpx

PLAYERS_JSON = "players_to_analyze_26_27.json"

FUTFANTASY_EQUIPOS = {
    "Real Racing Club": "racing",
    "Málaga CF": "malaga",
    "FC Barcelona": "barcelona",
    "Sevilla": "sevilla",
    "Athletic Club": "athletic",
    "Deportivo de A Coruña": "deportivo",
    "Real Madrid": "real-madrid",
    "Deportivo Alavés": "alaves",
    "Celta Vigo": "celta",
    "Real Betis": "betis",
    "Getafe": "getafe",
    "Espanyol": "espanyol",
    "Valencia": "valencia",
    "Atlético Madrid": "atletico",
    "Rayo Vallecano": "rayo-vallecano",
    "Real Sociedad": "real-sociedad",
    "Osasuna": "osasuna",
    "Elche": "elche",
    "Levante UD": "levante",
    "Villarreal": "villarreal",
}


def team_folder(team_name):
    # mismo criterio que normalize() de update_matchday
    return team_name.lower().replace(" ", "_")


def get_squad_sofascore(session, team_id):
    try:
        resp = session.get(
            f"https://www.sofascore.com/api/v1/team/{team_id}/players",
            headers={"Referer": f"https://www.sofascore.com/football/team/{team_id}"},
        )
        if resp.status_code != 200:
            return None, f"HTTP {resp.status_code}"
        return [p["player"] for p in resp.json().get("players", [])], None
    except Exception as e:
        return None, str(e)


def get_slugs_futfantasy(ff_session, team_name):
    slug = FUTFANTASY_EQUIPOS.get(team_name)
    if not slug:
        return None, "equipo sin slug en FUTFANTASY_EQUIPOS"
    try:
        resp = ff_session.get(f"https://www.futbolfantasy.com/laliga/equipos/{slug}", timeout=20)
        if resp.status_code != 200:
            return None, f"HTTP {resp.status_code}"
    except Exception as e:
        return None, str(e)
    return sorted(set(re.findall(r"futbolfantasy\.com/jugadores/([a-z0-9-]+)", resp.text))), None


def _tokens(s):
    return [t for t in re.split(r"[^a-z0-9]+", s.lower()) if t]


def variantes(player):
    """Tokens del nombre de SofaScore sin tildes ("alvaro") y al estilo
    FutFantasy, que borra las letras con tilde ("lvaro")."""
    toks = set()
    for campo in ("name", "slug", "shortName"):
        valor = player.get(campo) or ""
        sin_tildes = "".join(c for c in unicodedata.normalize("NFD", valor) if unicodedata.category(c) != "Mn")
        toks |= set(_tokens(sin_tildes))
        toks |= set(_tokens(re.sub(r"[^\x00-\x7f]", "", valor)))
    return toks


def slug_estilo_futfantasy(nombre):
    return "-".join(_tokens(re.sub(r"[^\x00-\x7f]", "", nombre)))


def similitud(player, ff_slug, tolerancia):
    """Fracción de las palabras del slug de FutFantasy que aparecen en el
    nombre de SofaScore (con tolerancia a erratas: "chrisantus"/"christantus")."""
    nombre = variantes(player)
    slug = [t for t in ff_slug.split("-") if t and not t.isdigit()]
    if not slug:
        return 0
    casa = lambda t: any(t == n or difflib.SequenceMatcher(None, t, n).ratio() >= tolerancia for n in nombre)
    return sum(casa(t) for t in slug) / len(slug)


def emparejar(squad, ff_slugs):
    """{sofascore_id: slug_futfantasy}. Primero solo emparejamientos completos;
    después, entre lo que sobra, los que casan al menos a medias (apodos:
    "Pedri" -> pedri-gonzalez, "Koke" -> koke-resurreccion). Cada slug se
    asigna una sola vez, al mejor candidato."""
    res, usados = {}, set()
    for umbral, tolerancia in ((1, 0.85), (0.5, 0.8)):
        pares = sorted(
            ((similitud(p, f, tolerancia), p["id"], f) for p in squad if p["id"] not in res for f in ff_slugs if f not in usados),
            key=lambda x: -x[0],
        )
        for score, pid, f in pares:
            if score < umbral or pid in res or f in usados:
                continue
            res[pid] = f
            usados.add(f)
    return res


def renombrar_carpeta(team_name, viejo, nuevo):
    origen = os.path.join("player_stats", team_folder(team_name), viejo)
    destino = os.path.join("player_stats", team_folder(team_name), nuevo)
    if os.path.isdir(origen) and not os.path.exists(destino):
        os.rename(origen, destino)


def sincronizar(session, ff_session, teams, aplicar=True):
    """Devuelve (teams_actualizados, cambios). Con aplicar=True también
    renombra las carpetas de los jugadores renombrados."""
    cambios = {k: [] for k in ("nuevos", "traspasos", "renombrados", "bajas", "fuera_de_plantilla", "sin_futfantasy", "errores")}
    # ids a los que update_matchday tiene que rellenar los partidos atrasados
    cambios["ids_relleno"] = []

    plantillas, slugs = {}, {}
    for team in teams:
        squad, error = get_squad_sofascore(session, team["sofascore_id"])
        if error:
            cambios["errores"].append(f"{team['name']}: plantilla SofaScore {error}")
        else:
            plantillas[team["name"]] = squad
        ff, error = get_slugs_futfantasy(ff_session, team["name"])
        if error:
            cambios["errores"].append(f"{team['name']}: FutFantasy {error}")
        slugs[team["name"]] = ff or []
        time.sleep(random.uniform(1, 2))

    en_lista = {p["sofascore_id"]: (team["name"], p) for team in teams for p in team["players"]}
    nuevos_teams = []
    vistos = set()

    for team in teams:
        name = team["name"]
        if name not in plantillas:
            nuevos_teams.append(team)
            vistos |= {p["sofascore_id"] for p in team["players"]}
            continue

        ff = emparejar(plantillas[name], slugs[name])
        players = []
        for p in plantillas[name]:
            pid = p["id"]
            vistos.add(pid)
            slug = ff.get(pid)
            anterior = en_lista.get(pid)

            if anterior and anterior[0] == name:
                nombre = anterior[1]["name"]
                if slug and slug != nombre:
                    cambios["renombrados"].append(f"{name}: {nombre} -> {slug}")
                    cambios["ids_relleno"].append(pid)
                    if aplicar:
                        renombrar_carpeta(name, nombre, slug)
                    nombre = slug
            elif anterior:
                nombre = slug or anterior[1]["name"]
                cambios["traspasos"].append(f"{p['name']}: {anterior[0]} -> {name} ({nombre})")
                cambios["ids_relleno"].append(pid)
            else:
                nombre = slug or slug_estilo_futfantasy(p.get("slug") or p["name"])
                cambios["nuevos"].append(f"{name}: {p['name']} ({nombre})")
                cambios["ids_relleno"].append(pid)

            if not slug:
                cambios["sin_futfantasy"].append(f"{name}: {p['name']} ({nombre})")
            players.append({"name": nombre, "sofascore_id": pid})

        nuevos_teams.append({**team, "players": players})

    # baja = no está en ninguna plantilla. La plantilla de SofaScore baila
    # (canteranos que entran y salen de una consulta a otra), así que solo se
    # quita a quien además no tiene ningún partido esta temporada; el resto se
    # queda en su equipo. Y nada de bajas si alguna plantilla ha fallado:
    # podría ser un traspaso a ese equipo.
    todas_leidas = len(plantillas) == len(teams)
    for pid, (team_name, p) in en_lista.items():
        if pid in vistos:
            continue
        if todas_leidas and not tiene_partidos_temporada(team_name, p["name"]):
            cambios["bajas"].append(f"{team_name}: {p['name']}")
            continue
        if todas_leidas:
            cambios["fuera_de_plantilla"].append(f"{team_name}: {p['name']}")
        next(t for t in nuevos_teams if t["name"] == team_name)["players"].append(p)

    return nuevos_teams, cambios


def tiene_partidos_temporada(team_name, player_name):
    """Si ya hay alguna carpeta de temporada activa (todo menos el histórico
    22_25) para este jugador en este equipo."""
    base = os.path.join("player_stats", team_folder(team_name), player_name)
    return os.path.isdir(base) and any(d != "22_25" and os.path.isdir(os.path.join(base, d)) for d in os.listdir(base))


def imprimir_cambios(cambios):
    titulos = {
        "nuevos": "🆕 Nuevos", "traspasos": "🔁 Traspasos", "renombrados": "✏️ Renombrados (slug FutFantasy)",
        "bajas": "👋 Bajas", "fuera_de_plantilla": "🤔 Fuera de la plantilla de SofaScore pero con partidos esta temporada (se mantienen)",
        "sin_futfantasy": "⚠️ Sin slug en FutFantasy (se reintenta cada vez)", "errores": "❌ Errores",
    }
    for clave, titulo in titulos.items():
        if cambios[clave]:
            print(f"\n{titulo} ({len(cambios[clave])}):")
            for linea in cambios[clave]:
                print(f"  - {linea}")


def guardar(teams):
    with open(PLAYERS_JSON, encoding="utf-8") as f:
        data = json.load(f)
    data["teams"] = teams
    with open(PLAYERS_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    import argparse
    from futFantasy_Pipeline import crear_sesion
    from update_matchday import USER_AGENTS, random_headers

    parser = argparse.ArgumentParser(description="Sincroniza la lista de jugadores con las plantillas reales.")
    parser.add_argument("--aplicar", action="store_true", help="Guarda los cambios (por defecto solo los muestra)")
    args = parser.parse_args()

    headers = random_headers()
    headers["User-Agent"] = USER_AGENTS[0]
    session = httpx.Client(headers=headers, timeout=15)

    with open(PLAYERS_JSON) as f:
        teams = json.load(f)["teams"]

    teams, cambios = sincronizar(session, crear_sesion(), teams, aplicar=args.aplicar)
    imprimir_cambios(cambios)
    if args.aplicar:
        guardar(teams)
        print(f"\n💾 {PLAYERS_JSON} actualizado")
    else:
        print("\n(sin --aplicar: no se ha guardado nada)")
