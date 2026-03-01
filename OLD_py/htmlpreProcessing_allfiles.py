from bs4 import BeautifulSoup
import os

# Carpeta con los HTML
input_folder = "borja-iglesias_html"

# Archivo final
output_file = "borja-iglesias_html/all_clean.html"

combined_html = ""

# Ordenar archivos para mantener orden temporal
html_files = sorted([
    f for f in os.listdir(input_folder)
    if f.endswith(".html")
])

for filename in html_files:

    input_path = os.path.join(input_folder, filename)

    print(f"Procesando {filename}")

    with open(input_path, "r", encoding="utf-8") as f:
        raw_html = f.read()

    # --- TU LIMPIEZA (NO MODIFICADA) ---
    raw_html = raw_html.replace("\n", " ").replace("\r", " ").strip()

    soup = BeautifulSoup(raw_html, "html.parser")
    pretty_html = soup.prettify()
    # -----------------------------------

    combined_html += f"\n<!-- START {filename} -->\n"
    combined_html += pretty_html
    combined_html += f"\n<!-- END {filename} -->\n"


# Guardar HTML combinado
with open(output_file, "w", encoding="utf-8") as f:
    f.write(combined_html)

print(f"✅ HTML combinado guardado en {output_file}")
