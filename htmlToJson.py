from bs4 import BeautifulSoup
import json

# Ruta del archivo HTML
ruta_html = "antoine-griezmann_html/all_clean.html"

# Abrimos y leemos el contenido del archivo
with open(ruta_html, "r", encoding="utf-8") as f:
    html = f.read()

soup = BeautifulSoup(html, "html.parser")
partidos_json = []

# Recorremos cada partido
for td in soup.find_all("td", class_="name position-relative"):
    try:
        # Equipos y resultado
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

        # Puntuaciones principales
        puntuaciones = {}
        picas_td = td.find_next_sibling("td", class_="picas")
        puntuaciones["picas"] = len(picas_td.find_all("img")) if picas_td else 0

        marca_td = td.find_next_sibling("td", class_="marca")
        puntuaciones["marca"] = len(marca_td.text.strip()) if marca_td else 0

        for clase in ["cope", "sofascore", "relevo", "md", "sportmonks"]:
            td_sib = td.find_next_sibling("td", class_=clase)
            if td_sib:
                try:
                    puntuaciones[clase] = float(td_sib.text.strip().replace("★", "").replace(",", "."))
                except ValueError:
                    puntuaciones[clase] = None
            else:
                puntuaciones[clase] = None

        # Puntuaciones detalladas
        detalladas = {}
        data_td = td.find_next_sibling("td", class_="data points bold d-flex")
        if data_td:
            for span in data_td.find_all("span", class_="racha-box"):
                clases = span.get("class", [])
                # eliminar clases genéricas
                genericas = ["racha-box", "columna_puntos", "point", "mx-auto", "low", "medium", "high", "very-high", "scale2", "scale3", "scale4"]
                sistemas = [c for c in clases if c not in genericas]
                if sistemas:
                    sistema = sistemas[-1]  # la última clase “no genérica”
                    valor_texto = span.get_text(strip=True).replace("\n", "").replace(" ", "").replace(",", ".")
                    try:
                        valor = float(valor_texto)
                    except ValueError:
                        valor = None
                    detalladas[sistema] = valor

        puntuaciones["detalladas"] = detalladas
        partido["puntuaciones"] = puntuaciones
        partidos_json.append(partido)

    except Exception as e:
        print(f"Error procesando un partido: {e}")
        continue

# Guardamos el resultado en JSON
with open("griezmann_futfantasy.json", "w", encoding="utf-8") as f:
    json.dump(partidos_json, f, indent=2, ensure_ascii=False)

print("JSON generado correctamente en 'partidos.json'")
