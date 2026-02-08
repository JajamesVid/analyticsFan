from bs4 import BeautifulSoup

# Archivo de entrada
input_file = "puntus_vinijr2226/25_26.html"
# Archivo de salida
output_file = "puntus_vinijr2226/25_26_clean.html"

with open(input_file, "r", encoding="utf-8") as f:
    raw_html = f.read()

# Limpiamos saltos de línea y espacios innecesarios
raw_html = raw_html.replace("\n", " ").replace("\r", " ").strip()

# Parseamos con BeautifulSoup
soup = BeautifulSoup(raw_html, "html.parser")

# Opcional: indentación bonita
pretty_html = soup.prettify()

# Guardamos HTML limpio
with open(output_file, "w", encoding="utf-8") as f:
    f.write(pretty_html)

print(f"HTML pre-procesado guardado en {output_file}")
