import os
import re
import io
import json
import time
import html as html_lib
import requests
from bs4 import BeautifulSoup
from PIL import Image

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

OUTPUT_ROOT = "laliga_player_photos"


# =========================================================
# UTILIDADES COMPARTIDAS
# =========================================================

def get_html(session, url, **kwargs):
    resp = session.get(url, headers=HEADERS, timeout=20, **kwargs)
    resp.raise_for_status()
    return resp.text


def get_next_data(html_text):
    soup = BeautifulSoup(html_text, "html.parser")
    script = soup.find("script", id="__NEXT_DATA__")
    return json.loads(script.string)


def parse_llt_squads(html_text, grid_index, data_key="squads", filter_player_type=True):
    """Sitios construidos sobre la misma plataforma (llt-services.com):
    Getafe, Elche, Levante, Rayo Vallecano, Racing de Santander."""
    data = get_next_data(html_text)
    squads = data["props"]["pageProps"]["data"]["page"]["grids"][grid_index]["areas"][0]["modules"][0]["data"][data_key]

    players = []
    for s in squads:
        p = s["player"]

        if filter_player_type and p.get("position", {}).get("type") != "player":
            continue

        image_url = p.get("imageMainUrl") or (p.get("image") or {}).get("url")
        if not image_url:
            continue

        players.append({
            "slug": p["slug"],
            "name": p["name"],
            "image_url": image_url,
        })

    return players


def save_player(session, team_folder, player, needs_rembg=False, extra_headers=None):
    folder = os.path.join(OUTPUT_ROOT, team_folder)
    os.makedirs(folder, exist_ok=True)
    dest = os.path.join(folder, f"{player['slug']}.png")

    if os.path.exists(dest):
        print(f"⏭ {player['name']} ya existe")
        return

    print(f"→ {player['name']}")

    try:
        req_headers = dict(HEADERS)
        if extra_headers:
            req_headers.update(extra_headers)
        resp = session.get(player["image_url"], headers=req_headers, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        print(f"❌ Error descargando imagen de {player['name']}: {e}")
        return

    try:
        img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
    except Exception as e:
        print(f"❌ Error abriendo imagen de {player['name']}: {e}")
        return

    if needs_rembg:
        from rembg import remove
        img = remove(img)

    img.save(dest)
    print(f"✔️ {player['name']} -> {dest}")


# =========================================================
# PARSERS POR EQUIPO -> devuelven list[{"slug","name","image_url"}]
# =========================================================

def parse_alaves(html_text):
    soup = BeautifulSoup(html_text, "html.parser")
    script = soup.find("script", id="serverApp-state")
    data = json.loads(script.string)
    members = data["page-equipos-equipo-masculino-es-alaves"]["extendedPage"]["page"]["data"]["attributes"]["content"][1]["team"]["data"]["attributes"]["members"]["data"]

    players = []
    for m in members:
        a = m["attributes"]
        if a.get("team_member_role", {}).get("data", {}).get("attributes", {}).get("key") != "Player":
            continue
        photo = (a.get("photo") or {}).get("data")
        if not photo:
            continue
        players.append({
            "slug": a["slug"],
            "name": f"{a['name']} {a['lastName']}".strip(),
            "image_url": "https://cms.deportivoalaves.com" + photo["attributes"]["url"],
        })
    return players


def parse_celta(html_text):
    soup = BeautifulSoup(html_text, "html.parser")
    players = []
    for c in soup.select("article.card-player"):
        a = c.select_one("a.card-player__inner")
        img = c.select_one("figure.card-player__img img")
        name = c.select_one("h3.card-player__name")
        if not (a and img and name):
            continue
        slug = a["href"].rstrip("/").split("/")[-1]
        players.append({"slug": slug, "name": name.get_text(strip=True), "image_url": img["src"]})
    return players


def parse_betis(html_text):
    soup = BeautifulSoup(html_text, "html.parser")
    players = []
    for c in soup.select("div.player"):
        a = c.select_one("a")
        img = c.select_one("img")
        name = c.select_one("p.name")
        if not (a and img and name):
            continue
        slug = a["href"].rstrip("/").split("/")[-1]
        players.append({"slug": slug, "name": name.get_text(strip=True), "image_url": img["src"]})
    return players


def parse_espanyol(html_text):
    soup = BeautifulSoup(html_text, "html.parser")
    plantilla = soup.select_one("div#plantilla")
    staff = soup.select_one("div#coaching-staff")
    staff_ids = set(id(c) for c in staff.select("div.cell.small-6.medium-4.large-3.clickable")) if staff else set()

    players = []
    for c in plantilla.select("div.cell.small-6.medium-4.large-3.clickable"):
        if id(c) in staff_ids:
            continue
        a = c.select_one("a")
        img = c.select_one("figure img")
        name = c.select_one("h3")
        if not (a and img and name):
            continue
        slug = a["href"].rstrip("/").split("/")[-1]
        players.append({
            "slug": slug,
            "name": name.get_text(strip=True),
            "image_url": "https://www.rcdespanyol.com" + img["src"],
        })
    return players


def parse_getafe(html_text):
    return parse_llt_squads(html_text, grid_index=0)


def parse_real_sociedad(html_text):
    soup = BeautifulSoup(html_text, "html.parser")
    players = []
    for c in soup.select("div.item.equal-height"):
        a = c.select_one("a")
        img = c.select_one("div.thumb-inner img")
        if not (a and img):
            continue
        slug = a["href"].rstrip("/").split("/")[-1]
        players.append({"slug": slug, "name": a.get("title", slug), "image_url": img["src"]})
    return players


def parse_osasuna(html_text):
    soup = BeautifulSoup(html_text, "html.parser")
    players = []
    for c in soup.select("div.card-player"):
        a = c.select_one("a")
        img = c.select_one("div.card-player__photo img")
        name = c.select_one("h3.card-player__name")
        if not (a and img and name):
            continue
        slug = a["href"].rstrip("/").split("/")[-1]
        img_url = img["src"]
        if img_url.startswith("/"):
            img_url = "https://www.osasuna.es" + img_url
        players.append({"slug": slug, "name": name.get_text(strip=True), "image_url": img_url})
    return players


def parse_elche(html_text):
    return parse_llt_squads(html_text, grid_index=0, data_key="playerStats", filter_player_type=False)


def parse_levante(html_text):
    return parse_llt_squads(html_text, grid_index=1)


def parse_villarreal(html_text):
    blocks = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', html_text, re.DOTALL)
    joined = "".join(blocks)
    joined = joined.replace('\\\\"', "@@Q@@").replace('\\"', '"').replace("@@Q@@", '\\"')

    players = []
    for m in re.finditer(r'"href":"(/player/[^"]+)/"', joined):
        slug = m.group(1).rsplit("/", 1)[-1]
        window = joined[m.end():m.end() + 700]
        src = re.search(r'"src":"(https://panel\.villarrealcf\.es/wp-content/uploads/[^"]+\.png)"', window)
        alt = re.search(r'"alt":"([^"]+)"', window)
        if not src:
            continue
        players.append({"slug": slug, "name": alt.group(1).title() if alt else slug, "image_url": src.group(1)})
    return players


def parse_sevilla(html_text):
    pattern = r'\\"id\\":\\"(\d+)\\",\\"medium_shot\\":\\"([^\\]+)\\",\\"role\\":\\"([^\\]+)\\",\\"short_name\\":\\"([^\\]+)\\",\\"slug\\":\\"([^\\]+)\\",\\"type\\":\\"player\\"'
    players = []
    for _id, image_url, role, short_name, slug_path in re.findall(pattern, html_text):
        slug = slug_path.rstrip("/").split("/")[-1]
        players.append({"slug": slug, "name": short_name, "image_url": image_url})
    return players


def parse_racing(html_text):
    return parse_llt_squads(html_text, grid_index=1)


def parse_deportivo(html_text):
    img_pattern = r'\\"(https://cdn\.bff\.rcdeportivo\.app/players/\d+-small\?v=\d+)\\",\\"(https://cdn\.bff\.rcdeportivo\.app/players/\d+-large\?v=\d+)\\",\\"([a-z0-9-]+)\\"'
    players = []
    for _small, large, slug in re.findall(img_pattern, html_text):
        name = slug.replace("-", " ").title()
        players.append({"slug": slug, "name": name, "image_url": large})
    return players


def parse_athletic(html_text):
    idx = html_text.find("DetailTeamFeature")
    start = html_text.rfind("<astro-island", 0, idx)
    props_start = html_text.find('props="', start) + len('props="')
    tag_end = html_text.find('">', props_start)
    props_raw = html_text[props_start:tag_end]
    props_unescaped = html_lib.unescape(props_raw)

    decoder = json.JSONDecoder()
    data, _ = decoder.raw_decode(props_unescaped)

    def unwrap(v):
        if isinstance(v, list) and len(v) == 2 and isinstance(v[0], int):
            return unwrap(v[1])
        if isinstance(v, list):
            return [unwrap(x) for x in v]
        if isinstance(v, dict):
            return {k: unwrap(x) for k, x in v.items()}
        return v

    clean = unwrap(data)
    raw_players = clean["initialData"]["players"]

    players = []
    for p in raw_players:
        img = (p.get("profileImage") or {}).get("src")
        if not img:
            continue
        players.append({"slug": p["slug"], "name": p["name"], "image_url": img})
    return players


def parse_atletico(html_text, session):
    # OJO: la rejilla de /jugadores-primer-equipo/ solo muestra una tarjeta
    # gráfica "nombre + dorsal" (foto_listados/<id>/thumb_.../<dorsal>.jpg),
    # no una foto real, ni siquiera para jugadores como Koke o Julián Álvarez.
    # La foto de estudio real está en la ficha individual de cada jugador;
    # construir la URL a partir del nombre mostrado falla en muchos casos
    # (iniciales, apellidos compuestos, tildes), así que se visita cada
    # ficha y se extrae la URL de "destacado_..." directamente de su HTML.
    soup = BeautifulSoup(html_text, "html.parser")
    profiles = []
    for c in soup.select("article.cromo"):
        a = c.select_one("a")
        if not a:
            continue
        slug = a["href"].rstrip("/").split("/")[-1]
        name = a.get("title", slug)
        profiles.append((slug, name, "https://www.atleticodemadrid.com" + a["href"]))

    players = []
    for slug, name, profile_url in profiles:
        try:
            profile_html = get_html(session, profile_url)
        except Exception as e:
            print(f"⚠️ {name}: no se pudo abrir la ficha ({e})")
            continue

        matches = re.findall(r'(fotos/\d+/destacado_(\d+)x\d+/[^"\']+-ficha\.(?:png|jpg))', profile_html)
        if not matches:
            print(f"⚠️ {name}: sin foto 'destacado' en su ficha")
            continue

        best_path = max(matches, key=lambda m: int(m[1]))[0]
        image_url = f"https://img-estaticos.atleticodemadrid.com/system/{best_path}"
        players.append({"slug": slug, "name": name, "image_url": image_url})
        time.sleep(0.3)

    return players


def parse_rayo(html_text):
    return parse_llt_squads(html_text, grid_index=1)


TEAMS = {
    "deportivo_alavés": {
        "url": "https://deportivoalaves.com/equipos/equipo-masculino",
        "parser": parse_alaves,
    },
    "celta_vigo": {
        "url": "https://rccelta.es/equipos/primer-equipo/",
        "parser": parse_celta,
    },
    "real_betis": {
        "url": "https://www.realbetisbalompie.es/primer-equipo/plantilla/",
        "parser": parse_betis,
    },
    "espanyol": {
        "url": "https://www.rcdespanyol.com/es/equipos/plantilla/primer-equipo-masculino/1",
        "parser": parse_espanyol,
    },
    "getafe": {
        "url": "https://www.getafecf.com/en/players",
        "parser": parse_getafe,
    },
    "real_sociedad": {
        "url": "https://www.realsociedad.eus/en/e/squad/real-sociedad",
        "parser": parse_real_sociedad,
    },
    "osasuna": {
        "url": "https://www.osasuna.es/plantilla",
        "parser": parse_osasuna,
    },
    "elche": {
        "url": "https://www.elchecf.es/estadisticas",
        "parser": parse_elche,
    },
    "levante_ud": {
        "url": "https://www.levanteud.com/plantilla",
        "parser": parse_levante,
    },
    "villarreal": {
        "url": "https://villarrealcf.es/es/primer-equipo/",
        "parser": parse_villarreal,
    },
    "sevilla": {
        "url": "https://sevillafc.es/es/equipos/primer-equipo",
        "parser": parse_sevilla,
        "fetch_kwargs": {"allow_redirects": True},
    },
    "real_racing_club": {
        "url": "https://www.realracingclub.es/jugadores",
        "parser": parse_racing,
    },
    "deportivo_de_la_coruña": {
        "url": "https://www.rcdeportivo.es/es/depor",
        "parser": parse_deportivo,
        "image_headers": {"Accept": "image/webp,*/*"},
    },
    "athletic_club": {
        "url": "https://www.athletic-club.eus/equipos/athletic-club/2026-27/plantilla/",
        "parser": parse_athletic,
    },
    "atlético_madrid": {
        "url": "https://www.atleticodemadrid.com/jugadores-primer-equipo/",
        "parser": parse_atletico,
        "parser_needs_session": True,
        "needs_rembg": True,
    },
    "rayo_vallecano": {
        "url": "https://www.rayovallecano.es/jugadores",
        "parser": parse_rayo,
        "needs_rembg": True,
    },
}


if __name__ == "__main__":
    import sys

    session = requests.Session()

    only = sys.argv[1] if len(sys.argv) > 1 else None
    teams = {only: TEAMS[only]} if only else TEAMS

    for team_folder, cfg in teams.items():
        print(f"\n{'='*50}")
        print(f"Equipo: {team_folder}")
        print(f"{'='*50}")

        try:
            html_text = get_html(session, cfg["url"], **cfg.get("fetch_kwargs", {}))
        except Exception as e:
            print(f"❌ Error descargando la página: {e}")
            continue

        try:
            if cfg.get("parser_needs_session"):
                players = cfg["parser"](html_text, session)
            else:
                players = cfg["parser"](html_text)
        except Exception as e:
            print(f"❌ Error parseando la plantilla: {e}")
            continue

        print(f"📋 {len(players)} jugadores encontrados")

        for player in players:
            save_player(
                session,
                team_folder,
                player,
                needs_rembg=cfg.get("needs_rembg", False),
                extra_headers=cfg.get("image_headers"),
            )
            time.sleep(0.5)

    print(f"\n✔ Fotos guardadas en {OUTPUT_ROOT}/")
