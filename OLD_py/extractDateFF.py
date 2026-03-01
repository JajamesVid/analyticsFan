import json
import time
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

INPUT_FILE = "borja-iglesias_html/borjaiglesias_futfantasy.json"
OUTPUT_FILE = "borjaiglesias_futfantasy_futfantasy_con_fecha.json"


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

    session.headers.update({
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "es-ES,es;q=0.9"
    })

    return session


session = crear_sesion()


def extraer_fecha(url):
    try:
        response = session.get(url, timeout=(5, 20))  # connect, read
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


def main():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        partidos = json.load(f)

    for partido in partidos:
        url = partido.get("url_ficha")

        if not url:
            continue

        if "fecha_partido" in partido:
            continue  # cache simple

        print(f"Procesando {url}")

        fecha = extraer_fecha(url)
        partido["fecha_partido"] = fecha

        time.sleep(2)  # 👈 importante

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(partidos, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
