"""
generate_decks_and_media.py
- Vereisten:
  pip install geopandas matplotlib pandas genanki gTTS requests pycountry deep-translator Pillow
- Download natural earth shapefile en plaats in data/
  (ne_110m_admin_0_countries.shp en bijbehorende bestanden)
- Run:
  python generate_decks_and_media.py
"""

import geopandas as gpd
import matplotlib.pyplot as plt
from pathlib import Path
import pandas as pd
import genanki
from gtts import gTTS
import requests
import pycountry
from deep_translator import GoogleTranslator
import json
import time
from PIL import Image

# ---------- CONFIG ----------
DATA_SHP = Path("data/ne_110m_admin_0_countries.shp")
OUTPUT_BASE = Path("decks")
LANGS = ["nl", "en", "fr", "de", "es"]  # uit te breiden
# Kaarten DPI / grootte
FIGSIZE = (6, 6)
DPI = 200
# padding factor voor automatische zoom rondom land
PAD_FACTOR = 0.5
# Flag CDN URL (lowercase ISO2)
FLAG_URL = "https://flagcdn.com/w320/{code}.png"
# Mapping voor uitzonderlijke landen waar pycountry.lookup faalt of andere naam nodig is
PYCOUNTRY_NAME_FIX = {
    "Kosovo": "XK",  # flagcdn uses 'xk' sometimes; pycountry has no Kosovo in some installs
    "Vatican": "va",
    "North Macedonia": "mk",
    "Czechia": "cz",
    "Moldova": "md",
    "Russia": "ru",
    "United Kingdom": "gb",
    # NaturalEarth uses "Bosnia and Herz." — pycountry lookup might still work but add mapping if needed
}

# Default hoofdsteden in Engels keyed by the Natural Earth NAME field
HOOFDSTEDEN_EN = {
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

# gTTS language fallback mapping: map our LANGS to gtts languages
GTTS_LANG_MAP = {
    "nl": "nl",
    "en": "en",
    "fr": "fr",
    "de": "de",
    "es": "es"
}

# ---------- HELPERS ----------
def safe_country_alpha2(name):
    # probeer pycountry te gebruiken, val terug op mapping
    try:
        # pycountry.lookup kan soms fail bij truncated names; try direct lookup or search
        try:
            c = pycountry.countries.lookup(name)
            return c.alpha_2.lower()
        except Exception:
            # try to use mapping or fuzzy
            if name in PYCOUNTRY_NAME_FIX:
                code = PYCOUNTRY_NAME_FIX[name]
                return code.lower()
            # try searching by common_name/official_name
            for c in pycountry.countries:
                if hasattr(c, "common_name") and c.common_name and name.lower() in c.common_name.lower():
                    return c.alpha_2.lower()
                if hasattr(c, "official_name") and c.official_name and name.lower() in c.official_name.lower():
                    return c.alpha_2.lower()
    except Exception:
        pass
    return None

def download_flag_by_country(name, dest_path):
    code = safe_country_alpha2(name)
    if not code:
        # fallback: try very basic conversions
        alt = {
            "Bosnia and Herz.": "ba",
            "Kosovo": "xk",
            "Vatican": "va",
            "North Macedonia": "mk",
            "Czechia": "cz",
            "Moldova": "md",
            "United Kingdom": "gb",
        }.get(name)
        if alt:
            code = alt
    if not code:
        print(f"⚠️ Kan geen ISO2-code vinden voor {name} — geen vlag.")
        return False
    url = FLAG_URL.format(code=code)
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            dest_path.write_bytes(r.content)
            # normalize image (some flags have transparent background)
            try:
                img = Image.open(dest_path)
                img = img.convert("RGBA")
                bg = Image.new("RGB", img.size, (255,255,255))
                bg.paste(img, mask=img.split()[3] if img.mode=='RGBA' else None)
                bg.save(dest_path, format="PNG")
            except Exception:
                pass
            return True
        else:
            print(f"⚠️ Flag not found for {name} at {url} (status {r.status_code})")
            return False
    except Exception as e:
        print(f"⚠️ Error downloading flag for {name}: {e}")
        return False

def text_to_speech(text, lang, dest_path):
    # gTTS expects language code like 'nl', 'fr'
    g_lang = GTTS_LANG_MAP.get(lang, 'en')
    try:
        tts = gTTS(text=text, lang=g_lang)
        tts.save(str(dest_path))
        return True
    except Exception as e:
        print(f"⚠️ gTTS failed for '{text}' ({lang}): {e}")
        return False

# ---------- MAIN ----------
def main():
    print("🔁 Start genereren decks + media")
    if not DATA_SHP.exists():
        raise SystemExit(f"Plaats de natural earth shapefile op {DATA_SHP} (ne_110m_admin_0_countries.shp)")

    world = gpd.read_file(DATA_SHP)
    europe = world[world['CONTINENT'] == 'Europe'].copy()

    # Clean index
    europe.reset_index(drop=True, inplace=True)

    # maak output structuren per taal
    for lang in LANGS:
        out_dir = OUTPUT_BASE / lang
        maps_dir = out_dir / "maps"
        flags_dir = out_dir / "flags"
        audio_dir = out_dir / "audio"
        for d in (out_dir, maps_dir, flags_dir, audio_dir):
            d.mkdir(parents=True, exist_ok=True)

    # 1) genereer kaarten & download flags (EN keys)
    print("🗺️ Genereren van kaartjes en vlaggen (EN basisnamen)...")
    for _, row in europe.iterrows():
        en_name = row["NAME"]
        if en_name not in HOOFDSTEDEN_EN:
            # skip onbekend land (of voeg toe aan HOOFDSTEDEN_EN)
            continue
        # *** kaart genereren ***
        for lang in LANGS:
            out_map = OUTPUT_BASE / lang / "maps" / f"{en_name}.png"
            if out_map.exists():
                continue  # skip als al gegenereerd
            fig, ax = plt.subplots(figsize=FIGSIZE)
            # background europa
            europe.plot(ax=ax, color='lightgrey', edgecolor='white', linewidth=0.5)
            europe[europe["NAME"] == en_name].plot(ax=ax, color='red', edgecolor='black', linewidth=0.6)
            # auto zoom op land met marge
            minx, miny, maxx, maxy = row.geometry.bounds
            pad_x = (maxx - minx) * PAD_FACTOR if (maxx - minx) > 0 else 1.0
            pad_y = (maxy - miny) * PAD_FACTOR if (maxy - miny) > 0 else 1.0
            ax.set_xlim(minx - pad_x, maxx + pad_x)
            ax.set_ylim(miny - pad_y, maxy + pad_y)
            ax.set_facecolor("lightblue")
            plt.axis('off')
            plt.title(en_name, fontsize=12)
            fig.savefig(out_map, bbox_inches='tight', dpi=DPI)
            plt.close(fig)

        # download vlag (een keer)
        flag_path = OUTPUT_BASE / LANGS[0] / "flags" / f"{en_name}.png"
        # save flag to the first lang dir then copy later across langs
        if not flag_path.exists():
            success = download_flag_by_country(en_name, flag_path)
            if not success:
                # create a blank placeholder
                Image.new("RGB", (320, 200), (220, 220, 220)).save(flag_path)

        # copy flag to other lang folders
        for lang in LANGS[1:]:
            dest = OUTPUT_BASE / lang / "flags" / f"{en_name}.png"
            if not dest.exists():
                dest.write_bytes(flag_path.read_bytes())

    # 2) Per taal: vertalingen, audio, anki .apkg en quiz JSON
    print("🔉 Genereren van audio, vertalingen en Anki .apkg per taal...")
    for lang in LANGS:
        print(f"➡️ Taal: {lang}")
        out_dir = OUTPUT_BASE / lang
        maps_dir = out_dir / "maps"
        flags_dir = out_dir / "flags"
        audio_dir = out_dir / "audio"

        # translator
        translator = GoogleTranslator(source='en', target=lang)

        # maak genanki model + deck
        model_id = 1607392319000 + abs(hash(lang)) % 1000000
        deck_id = 2050000000 + abs(hash(lang)) % 1000000
        model = genanki.Model(
            model_id,
            f"EuropaModel_{lang}",
            fields=[{"name": "Land"}, {"name": "Hoofdstad"}, {"name": "Map"}, {"name": "Flag"}, {"name": "Audio"}],
            templates=[
                {
                    "name": "Card1",
                    "qfmt": "<div style='font-size:22px'><b>{{Land}}</b></div><div>{{Map}}</div><div>{{Flag}}</div>",
                    "afmt": "{{FrontSide}}<hr id='answer'><div style='font-size:20px'><b>Hoofdstad:</b> {{Hoofdstad}}</div><div>{{Audio}}</div>",
                }
            ],
            css=""".card { font-family: Arial; text-align: center; } img { max-width: 360px; }"""
        )
        deck = genanki.Deck(deck_id, f"Europese hoofdsteden ({lang})")

        # media files list
        all_media = []

        quiz_items = []

        for en_name, en_cap in HOOFDSTEDEN_EN.items():
            if en_name not in europe["NAME"].values:
                continue
            # vertaal land en hoofdstad
            try:
                land_trans = translator.translate(en_name)
            except Exception:
                land_trans = en_name
            try:
                cap_trans = translator.translate(en_cap)
            except Exception:
                cap_trans = en_cap

            # audio: uitspraak van de hoofdstad (of land, maar we choose hoofdstad)
            audio_filename = f"{en_name}_{lang}.mp3"
            audio_path = audio_dir / audio_filename
            if not audio_path.exists():
                ok = text_to_speech(cap_trans, lang, audio_path)
                if not ok:
                    # fallback: try english
                    text_to_speech(en_cap, "en", audio_path)
            all_media.append(str(audio_path))

            # images: map + flag
            map_path = maps_dir / f"{en_name}.png"
            flag_path = flags_dir / f"{en_name}.png"
            if map_path.exists():
                all_media.append(str(map_path))
            if flag_path.exists():
                all_media.append(str(flag_path))

            # maak note voor genanki (Afbeeldingen via img src met bestandsnaam)
            map_tag = f"<img src=\"{map_path.name}\">" if map_path.exists() else ""
            flag_tag = f"<img src=\"{flag_path.name}\">" if flag_path.exists() else ""
            audio_tag = f"[sound:{audio_path.name}]" if audio_path.exists() else ""

            note = genanki.Note(
                model=model,
                fields=[land_trans, cap_trans, map_tag, flag_tag, audio_tag]
            )
            deck.add_note(note)

            # quiz item
            quiz_items.append({
                "country_en": en_name,
                "country": land_trans,
                "capital": cap_trans,
                "map": f"maps/{map_path.name}" if map_path.exists() else None,
                "flag": f"flags/{flag_path.name}" if flag_path.exists() else None,
                "audio": f"audio/{audio_path.name}" if audio_path.exists() else None,
            })

        # write apkg
        package = genanki.Package(deck)
        # media dedupe
        media_files = list(dict.fromkeys(all_media))
        package.media_files = media_files
        apkg_path = out_dir / f"europese_hoofdsteden_{lang}.apkg"
        package.write_to_file(str(apkg_path))
        print(f"   ✅ apkg geschreven: {apkg_path}")

        # write quiz json
        json_path = out_dir / f"quiz_data_{lang}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(quiz_items, f, ensure_ascii=False, indent=2)
        print(f"   ✅ json geschreven: {json_path}")

        # sleep kort om rate limit issues te beperken (translation / TTS)
        time.sleep(1.2)

    print("🎉 Gereed. Alle talen gegenereerd.")

if __name__ == "__main__":
    main()


