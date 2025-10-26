import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from deep_translator import GoogleTranslator

# === CONFIG ===
languages = ["nl", "en", "fr", "de", "es"]  # talen
output_dir = Path("anki_europa")
maps_dir = output_dir / "maps"
maps_dir.mkdir(parents=True, exist_ok=True)

# === GEOGRAFIE LADEN ===
world = gpd.read_file("data/ne_110m_admin_0_countries.shp")
europe = world[world['CONTINENT'] == 'Europe']

# === HOOFDSTEDEN ===
hoofdsteden = {
    "Albania": "Tirana", "Andorra": "Andorra la Vella", "Austria": "Vienna", "Belarus": "Minsk",
    "Belgium": "Brussels", "Bosnia and Herz.": "Sarajevo", "Bulgaria": "Sofia", "Croatia": "Zagreb",
    "Czechia": "Prague", "Denmark": "Copenhagen", "Estonia": "Tallinn", "Finland": "Helsinki",
    "France": "Paris", "Germany": "Berlin", "Greece": "Athens", "Hungary": "Budapest",
    "Iceland": "Reykjavik", "Ireland": "Dublin", "Italy": "Rome", "Kosovo": "Pristina",
    "Latvia": "Riga", "Liechtenstein": "Vaduz", "Lithuania": "Vilnius", "Luxembourg": "Luxembourg",
    "Malta": "Valletta", "Moldova": "Chisinau", "Monaco": "Monaco", "Montenegro": "Podgorica",
    "Netherlands": "Amsterdam", "North Macedonia": "Skopje", "Norway": "Oslo", "Poland": "Warsaw",
    "Portugal": "Lisbon", "Romania": "Bucharest", "San Marino": "San Marino", "Serbia": "Belgrade",
    "Slovakia": "Bratislava", "Slovenia": "Ljubljana", "Spain": "Madrid", "Sweden": "Stockholm",
    "Switzerland": "Bern", "Ukraine": "Kyiv", "United Kingdom": "London", "Vatican": "Vatican City"
}

# === KAARTEN MAKEN ===
for _, row in europe.iterrows():
    name = row["NAME"]
    if name not in hoofdsteden:
        continue

    fig, ax = plt.subplots(figsize=(6, 6))
    europe.plot(ax=ax, color='lightgrey', edgecolor='white')
    europe[europe["NAME"] == name].plot(ax=ax, color='red', edgecolor='black')
    ax.set_xlim(-25, 45)
    ax.set_ylim(33, 72)
    plt.axis('off')
    plt.title(name)
    plt.savefig(maps_dir / f"{name}.png", bbox_inches='tight', dpi=200)
    plt.close(fig)

# === VERTALINGEN + CSV PER TAAL ===
data = []
for lang in languages:
    translator = GoogleTranslator(source='en', target=lang)
    for name, capital in hoofdsteden.items():
        if name not in europe["NAME"].values:
            continue
        land_trans = translator.translate(name)
        hoofdstad_trans = translator.translate(capital)
        vraag = f"Wat is de hoofdstad van {land_trans}?"
        antwoord = hoofdstad_trans + f'<br><img src="{name}.png">'
        data.append({"front": vraag, "back": antwoord, "taal": lang})

    df = pd.DataFrame(data)
    df_lang = df[df["taal"] == lang]
    df_lang[["front", "back"]].to_csv(output_dir / f"anki_europa_{lang}.csv", index=False)

print(f"✅ Alles klaar! CSV's en kaarten staan in: {output_dir.resolve()}")

