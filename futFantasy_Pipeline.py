import os
import sys
import json
import time
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# =========================
# CONFIG
# =========================

SEASONS = ["22-23", "23-24", "24-25", "25-26"]

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "es-ES,es;q=0.9"
}


# =========================
# UTILIDADES
# =========================

def format_player_slug(player_name: str) -> str:
    return player_name.lower().replace(" ", "-")


def crear_sesion():
    session = requests.Session()

    retries = Retry(
        total=5,
        backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )

    adapter = HTTPAdapter(max_retries=retries)

    session.mount("http://", adapter)
    session.mount("https://", adapter)

    session.headers.update(HEADERS)

    return session


# =========================
# 1️⃣ Descargar HTMLs
# =========================

def descargar_htmls(session, player_slug):
    htmls = []

    for season in SEASONS:
        url = f"https://www.futbolfantasy.com/jugadores/{player_slug}/laliga-{season}"
        print(f"🌐 Descargando {url}")

        try:
            response = session.get(url, timeout=15)

            if response.status_code == 200:
                htmls.append(response.text)
                print(f"✅ OK {season}")
            else:
                print(f"⚠️ Error {response.status_code} en {season}")

        except Exception as e:
            print(f"❌ Error descargando {season}: {e}")

    return htmls


# =========================
# 2️⃣ Parsear partidos
# =========================

def parsear_partidos(htmls):
    partidos = []

    for raw_html in htmls:

        raw_html = raw_html.replace("\n", " ").replace("\r", " ").strip()
        soup = BeautifulSoup(raw_html, "html.parser")

        for td in soup.find_all("td", class_="name position-relative"):
            try:
                div = td.find("div", class_="link")
                imgs = div.find_all("img", class_="img")
                spans = div.find_all("span", class_="d-none d-md-inline-block")
                resultado = div.find("strong", class_="score").text.strip()

                partido = {
                    "local": {
                        "nombre": imgs[0]["alt"],
                        "abreviatura": spans[0].text.strip(),
                        "escudo": imgs[0]["src"]
                    },
                    "visitante": {
                        "nombre": imgs[1]["alt"],
                        "abreviatura": spans[1].text.strip(),
                        "escudo": imgs[1]["src"]
                    },
                    "resultado": resultado,
                    "url_ficha": None
                }

                desglose_tr = td.find_next("tr", class_="desglose")
                if desglose_tr:
                    link = desglose_tr.find("a", class_="link")
                    if link:
                        partido["url_ficha"] = link["href"]

                puntuaciones = {}

                picas_td = td.find_next_sibling("td", class_="picas")
                puntuaciones["picas"] = len(picas_td.find_all("img")) if picas_td else 0

                marca_td = td.find_next_sibling("td", class_="marca")
                puntuaciones["marca"] = len(marca_td.text.strip()) if marca_td else 0

                for clase in ["cope", "sofascore", "relevo", "md", "sportmonks"]:
                    td_sib = td.find_next_sibling("td", class_=clase)
                    if td_sib:
                        try:
                            puntuaciones[clase] = float(
                                td_sib.text.strip()
                                .replace("★", "")
                                .replace(",", ".")
                            )
                        except ValueError:
                            puntuaciones[clase] = None
                    else:
                        puntuaciones[clase] = None

                detalladas = {}
                data_td = td.find_next_sibling("td", class_="data points bold d-flex")

                if data_td:
                    for span in data_td.find_all("span", class_="racha-box"):
                        clases = span.get("class", [])

                        genericas = [
                            "racha-box", "columna_puntos", "point", "mx-auto",
                            "low", "medium", "high", "very-high",
                            "scale2", "scale3", "scale4"
                        ]

                        sistemas = [c for c in clases if c not in genericas]

                        if sistemas:
                            sistema = sistemas[-1]
                            valor_texto = (
                                span.get_text(strip=True)
                                .replace(",", ".")
                            )
                            try:
                                valor = float(valor_texto)
                            except ValueError:
                                valor = None

                            detalladas[sistema] = valor

                puntuaciones["detalladas"] = detalladas
                partido["puntuaciones"] = puntuaciones

                partidos.append(partido)

            except Exception as e:
                print(f"Error procesando partido: {e}")
                continue

    return partidos


# =========================
# 3️⃣ Añadir fecha
# =========================

def extraer_fecha(session, url):
    try:
        response = session.get(url, timeout=(5, 20))
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        header = soup.select_one("header.encabezado-partido")

        if not header:
            return None

        fechas = header.select("div.fecha")

        if len(fechas) >= 2:
            return fechas[1].get_text(strip=True)

        return None

    except Exception as e:
        print(f"Error procesando {url}: {e}")
        return None


def enriquecer_con_fecha(session, partidos):
    for partido in partidos:
        url = partido.get("url_ficha")

        if not url:
            continue

        print(f"📅 Procesando {url}")
        partido["fecha_partido"] = extraer_fecha(session, url)

        time.sleep(2)  # evitar bloqueo

    return partidos


# =========================
# MAIN PIPELINE
# =========================

def normalize_name(name: str) -> str:
    return name.lower().replace(" ", "_")


def main(player_name):

    player_slug = format_player_slug(player_name)
    player_folder_name = normalize_name(player_name)

    session = crear_sesion()

    htmls = descargar_htmls(session, player_slug)

    partidos = parsear_partidos(htmls)

    partidos = enriquecer_con_fecha(session, partidos)

    # 📁 Ruta consistente con el script de SofaScore
    base_folder = "player_stats"
    player_folder = os.path.join(base_folder, player_folder_name)

    os.makedirs(player_folder, exist_ok=True)

    output_file = os.path.join(player_folder, "futfantasy.json")

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(partidos, f, ensure_ascii=False, indent=2)

    print(f"\n✅ JSON final generado en: {output_file}")


if __name__ == "__main__":

    if len(sys.argv) < 2:
        print("Uso: python futfantasy_pipeline.py 'Nombre Jugador'")
        sys.exit(1)

    main(sys.argv[1])