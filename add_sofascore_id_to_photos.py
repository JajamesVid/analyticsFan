import os
import re
import json
import time
import unicodedata
import requests

import scrape_laliga_players as scraper
import scrape_realmadrid_players as rm_scraper
import scrape_fcb_players as fcb_scraper

PLAYERS_JSON = "players_to_analyze_26_27.json"

# carpeta de fotos -> nombre de equipo en players_to_analyze_26_27.json
FOLDER_TO_TEAM = {
    "deportivo_alavés": "Deportivo Alavés",
    "celta_vigo": "Celta Vigo",
    "real_betis": "Real Betis",
    "espanyol": "Espanyol",
    "getafe": "Getafe",
    "real_sociedad": "Real Sociedad",
    "osasuna": "Osasuna",
    "elche": "Elche",
    "levante_ud": "Levante UD",
    "villarreal": "Villarreal",
    "sevilla": "Sevilla",
    "real_racing_club": "Real Racing Club",
    "deportivo_de_la_coruña": "Deportivo de A Coruña",
    "athletic_club": "Athletic Club",
    "atlético_madrid": "Atlético Madrid",
    "rayo_vallecano": "Rayo Vallecano",
}


def rm_names(session):
    players = rm_scraper.get_players(session)
    return {p["slug"]: p["name"] for p in players}


def fcb_names(session):
    players = fcb_scraper.get_players(session)
    return {p["slug"]: p["name"] for p in players}


# carpetas que NO viven bajo laliga_player_photos/ y usan su propio scraper
EXTRA_FOLDERS = {
    "realmadrid_player_photos": ("Real Madrid", rm_names),
    "fcb_player_photos": ("FC Barcelona", fcb_names),
}


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def normalize_tokens(s):
    s = strip_accents(s).lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return [t for t in s.split() if t]


def slug_tokens(slug):
    # quita sufijos de desambiguación tipo "-1", "-2"
    slug = re.sub(r"-\d+$", "", slug)
    return normalize_tokens(slug.replace("-", " "))


def score(name_tokens, slug_toks):
    if not name_tokens or not slug_toks:
        return 0
    matches = 0
    for t in name_tokens:
        if len(t) < 2:
            continue
        for st in slug_toks:
            # ambos tokens deben ser lo bastante largos para un match parcial:
            # si no, "el" (de "omar-el-hilali") "matchea" como substring de
            # "gorosabel". Los apodos cortos tipo "Cala"->"Calatrava" siguen
            # aceptándose porque ambos superan la longitud mínima.
            if t == st or (len(t) > 3 and len(st) > 3 and (t in st or st in t)):
                matches += 1
                break
    return matches


def best_match(display_name, roster):
    name_toks = normalize_tokens(display_name)
    scored = []
    for player in roster:
        s = score(name_toks, slug_tokens(player["name"]))
        scored.append((s, player))
    scored.sort(key=lambda x: -x[0])
    return scored


def regenerate_names(team_folder):
    """Vuelve a pedir la web y el parser para recuperar slug->nombre (sin descargar fotos)."""
    cfg = scraper.TEAMS[team_folder]
    session = requests.Session()
    html_text = scraper.get_html(session, cfg["url"], **cfg.get("fetch_kwargs", {}))

    if cfg.get("parser_needs_session"):
        players = cfg["parser"](html_text, session)
    else:
        players = cfg["parser"](html_text)

    return {p["slug"]: p["name"] for p in players}


def process_folder(photo_dir, team_name, slug_to_name, roster, apply_renames, unmatched):
    print(f"\n{'='*50}")
    print(f"{team_name}")
    print(f"{'='*50}")

    for filename in sorted(os.listdir(photo_dir)):
        if not filename.endswith(".png"):
            continue

        file_slug = filename[:-4]

        if "_" in file_slug and file_slug.rsplit("_", 1)[-1].isdigit() and len(file_slug.rsplit("_", 1)[-1]) >= 4:
            print(f"⏭ {filename} ya tiene id")
            continue

        display_name = slug_to_name.get(file_slug, file_slug.replace("-", " "))

        name_toks = normalize_tokens(display_name)
        min_score = 2 if len(name_toks) >= 2 else 1

        candidates = best_match(display_name, roster)
        top_score = candidates[0][0] if candidates else 0

        tied = [c for c in candidates if c[0] == top_score]

        if top_score < min_score or len(tied) > 1:
            print(f"⚠️ {filename} ({display_name}) -> sin match claro (score={top_score}, empatados={len(tied)})")
            unmatched.append((team_name, filename, display_name))
            continue

        sofa_id = tied[0][1]["sofascore_id"]
        new_filename = f"{file_slug}_{sofa_id}.png"
        if apply_renames:
            os.rename(os.path.join(photo_dir, filename), os.path.join(photo_dir, new_filename))
        print(f"✔️ {filename} -> {new_filename} ({tied[0][1]['name']})")


if __name__ == "__main__":
    import sys
    APPLY = "--apply" in sys.argv

    with open(PLAYERS_JSON, encoding="utf-8") as f:
        data = json.load(f)

    rosters = {t["name"]: t["players"] for t in data["teams"]}

    unmatched = []

    for team_folder, team_name in FOLDER_TO_TEAM.items():
        photo_dir = os.path.join("laliga_player_photos", team_folder)
        if not os.path.isdir(photo_dir):
            continue

        try:
            slug_to_name = regenerate_names(team_folder)
        except Exception as e:
            print(f"❌ No se pudo regenerar nombres de {team_folder}: {e}")
            continue

        process_folder(photo_dir, team_name, slug_to_name, rosters.get(team_name, []), APPLY, unmatched)
        time.sleep(0.5)

    for photo_dir, (team_name, name_fetcher) in EXTRA_FOLDERS.items():
        if not os.path.isdir(photo_dir):
            continue

        try:
            session = requests.Session()
            slug_to_name = name_fetcher(session)
        except Exception as e:
            print(f"❌ No se pudo regenerar nombres de {photo_dir}: {e}")
            continue

        process_folder(photo_dir, team_name, slug_to_name, rosters.get(team_name, []), APPLY, unmatched)
        time.sleep(0.5)

    print(f"\n{'='*50}")
    print(f"Sin match claro: {len(unmatched)}")
    for team_name, filename, display_name in unmatched:
        print(f"  {team_name}: {filename} ({display_name})")
