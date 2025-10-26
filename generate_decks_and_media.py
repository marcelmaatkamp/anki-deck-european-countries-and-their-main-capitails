#!/usr/bin/env python3
"""
generate_full_decks.py
- Maakt per taal:
  - maps/, flags/, audio/
  - quiz_data_{lang}.json
  - europese_hoofdsteden_{lang}.apkg

Voordat je start:
- Zorg dat natural earth shapefile in data/ staat:
  ne_110m_admin_0_countries.shp (met .dbf/.shx/etc.)
- Installeer requirements:
  pip install geopandas matplotlib pandas genanki gTTS requests pycountry deep-translator Pillow
"""

from pathlib import Path
import geopandas as gpd
import matplotlib.pyplot as plt
from deep_translator import GoogleTranslator
from gtts import gTTS
import requests
import pycountry
import json
import time
from PIL import Image
import genanki
import pandas as pd

# ----------------- CONFIG -----------------
DATA_SHP = Path("data/ne_110m_admin_0_countries.shp")
OUTPUT = Path("decks")

LANGS = ["nl", "en", "fr", "de", "es"]  # uitbreidbaar
# LANGS = ["nl"]  # uitbreidbaa
FIGSIZE = (6, 6)
DPI = 200
PAD_FACTOR = 2.5
FLAG_URL = "https://flagcdn.com/w320/{code}.png"
# fallback mapping voor enkele landen
FALLBACK_ISO = {
    "Kosovo": "xk",
    "Vatican": "va",
    "North Macedonia": "mk",
    "Czechia": "cz",
    "Moldova": "md",
    "United Kingdom": "gb",
    "Bosnia and Herz.": "ba",
}

# Engelse hoofdsteden keyed op Natural Earth NAME
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

GTTS_LANG_MAP = {"nl": "nl", "en": "en", "fr": "fr", "de": "de", "es": "es"}

# ----------------- HELPERS -----------------
def safe_alpha2(name):
    try:
        c = pycountry.countries.lookup(name)
        return c.alpha_2.lower()
    except Exception:
        if name in FALLBACK_ISO:
            return FALLBACK_ISO[name]
        # search by common_name/official_name
        for c in pycountry.countries:
            if hasattr(c, "common_name") and c.common_name and name.lower() in c.common_name.lower():
                return c.alpha_2.lower()
            if hasattr(c, "official_name") and c.official_name and name.lower() in c.official_name.lower():
                return c.alpha_2.lower()
    return None

def download_flag(name, dest: Path):
    code = safe_alpha2(name)
    if not code:
        print(f"⚠️ Geen ISO-code voor {name}, fallback mogelijk nodig")
        return False
    url = FLAG_URL.format(code=code)
    try:
        r = requests.get(url, timeout=20)
        if r.status_code == 200:
            dest.write_bytes(r.content)
            # normalize to remove alpha channel if present
            try:
                img = Image.open(dest)
                if img.mode == "RGBA":
                    bg = Image.new("RGB", img.size, (255,255,255))
                    bg.paste(img, mask=img.split()[3])
                    bg.save(dest, format="PNG")
            except:
                pass
            return True
        else:
            print(f"⚠️ Flag {name} niet gevonden ({r.status_code})")
            return False
    except Exception as e:
        print(f"⚠️ Error download flag {name}: {e}")
        return False

def text_to_speech(text, lang, dest: Path):
    g_lang = GTTS_LANG_MAP.get(lang, "en")
    try:
        tts = gTTS(text=text, lang=g_lang)
        tts.save(str(dest))
        return True
    except Exception as e:
        print(f"⚠️ gTTS faalde voor '{text}' ({lang}): {e}")
        return False

# ----------------- MAIN -----------------
def main():
    if not DATA_SHP.exists():
        raise SystemExit(f"Plaats de Natural Earth shapefile in {DATA_SHP}")

    # load vector data
    world = gpd.read_file(DATA_SHP)
    europe = world[world["CONTINENT"] == "Europe"].copy()
    europe.reset_index(drop=True, inplace=True)

    # prepare output folders
    for lang in LANGS:
        (OUTPUT / lang / "maps").mkdir(parents=True, exist_ok=True)
        (OUTPUT / lang / "flags").mkdir(parents=True, exist_ok=True)
        (OUTPUT / lang / "audio").mkdir(parents=True, exist_ok=True)
        (OUTPUT / lang / "media").mkdir(parents=True, exist_ok=True)  # unified media for genanki

    # 1) generate maps once per language (maps are same visually; stored per lang for easy packaging)
    print("🗺️ Genereren kaarten & vlaggen...")
    for _, row in europe.iterrows():
        en_name = row["NAME"]
        if en_name not in HOOFDSTEDEN_EN:
            continue

        # generate maps per language folder
        for lang in LANGS:
            map_path = OUTPUT / lang / "maps" / f"{en_name}_map.png"
            if not map_path.exists():
                fig, ax = plt.subplots(figsize=FIGSIZE)
                europe.plot(ax=ax, color="lightgrey", edgecolor="white", linewidth=0.5)
                europe[europe["NAME"] == en_name].plot(ax=ax, color="red", edgecolor="black", linewidth=0.6)
                minx, miny, maxx, maxy = row.geometry.bounds
                pad_x = (maxx - minx) * PAD_FACTOR if (maxx - minx) > 0 else 1.0
                pad_y = (maxy - miny) * PAD_FACTOR if (maxy - miny) > 0 else 1.0
                ax.set_xlim(minx - pad_x, maxx + pad_x)
                ax.set_ylim(miny - pad_y, maxy + pad_y)
                ax.set_facecolor("lightblue")
                plt.axis("off")
                #plt.title(en_name, fontsize=12)
                fig.savefig(map_path, bbox_inches="tight", dpi=DPI)
                plt.close(fig)

        # download flag once, copy to all languages
        primary_flag = OUTPUT / LANGS[0] / "flags" / f"{en_name}_flag.png"
        if not primary_flag.exists():
            ok = download_flag(en_name, primary_flag)
            if not ok:
                # placeholder
                Image.new("RGB", (320, 200), (220,220,220)).save(primary_flag)
        # copy to others if missing
        for lang in LANGS[1:]:
            dest = OUTPUT / lang / "flags" / f"{en_name}_flag.png"
            if not dest.exists():
                dest.write_bytes(primary_flag.read_bytes())

    # 2) per language: translate, tts, copy media into media/ and create apkg + json
    print("🔉 Genereren vertalingen, audio en Anki decks per taal...")
    for lang in LANGS:
        print(f"➡️ Taal: {lang}")
        out_dir = OUTPUT / lang
        maps_dir = out_dir / "maps"
        flags_dir = out_dir / "flags"
        audio_dir = out_dir / "audio"
        media_dir = out_dir / "media"

        translator = GoogleTranslator(source='en', target=lang)

        # genanki model + deck
        model_id = 1607392319000 + abs(hash(lang)) % 1000000
        deck_id = 2050000000 + abs(hash(lang)) % 1000000
        model = genanki.Model(
            model_id,
            f"EuropaModel_{lang}",
            fields=[
                {"name": "Land"},
                {"name": "Hoofdstad"},
                {"name": "Map"},
                {"name": "Flag"},
                {"name": "Audio"},
            ],
            templates=[{
                "name": "Kaart",
                "qfmt": "<div style='font-size:22px'><div>{{Map}}{{Flag}}</div>",
                "afmt": "{{FrontSide}}<hr id='answer'><div style='font-size:20px'>{{Land}}<br />{{Hoofdstad}}</div><div>{{Audio}}</div>"
            }],
            css=".card { font-family: Arial; text-align: center; } img { max-width: 360px; }"
        )
        deck = genanki.Deck(deck_id, f"Europese hoofdsteden ({lang})")

        all_media = []
        quiz_items = []

        for en_name, en_cap in HOOFDSTEDEN_EN.items():
            if en_name not in europe["NAME"].values:
                continue

            # translate names (safe fallback to english on error)
            try:
                land_trans = translator.translate(en_name)
            except Exception:
                land_trans = en_name
            try:
                cap_trans = translator.translate(en_cap)
            except Exception:
                cap_trans = en_cap

            # audio filename
            audio_filename = f"{en_name}_{lang}.mp3"
            audio_path = audio_dir / audio_filename
            
            # audio content
            audio_content = f"{land_trans}: {cap_trans}"
            
            if not audio_path.exists():
                ok = text_to_speech(audio_content, lang, audio_path)
                if not ok:
                    text_to_speech(en_cap, "en", audio_path)
                    
            # copy audio into media_dir
            media_audio = media_dir / audio_filename
            if not media_audio.exists():
                media_audio.write_bytes(audio_path.read_bytes())
            all_media.append(str(media_audio))

            # copy map + flag into media_dir with unified names
            map_src = maps_dir / f"{en_name}_map.png"
            flag_src = flags_dir / f"{en_name}_flag.png"
            map_media = media_dir / f"{en_name}_map.png"
            flag_media = media_dir / f"{en_name}_flag.png"
            if map_src.exists() and not map_media.exists():
                map_media.write_bytes(map_src.read_bytes())
            if flag_src.exists() and not flag_media.exists():
                flag_media.write_bytes(flag_src.read_bytes())
            if map_media.exists():
                all_media.append(str(map_media))
            if flag_media.exists():
                all_media.append(str(flag_media))

            # create genanki note: use filenames only (Anki will use media list)
            map_tag = f"<img src=\"{map_media.name}\" width=\"512\" height=\"512\" />" if map_media.exists() else ""
            flag_tag = f"<img src=\"{flag_media.name}\" width=\"512\" height=\"512\" />" if flag_media.exists() else ""
            audio_tag = f"[sound:{media_audio.name}]" if media_audio.exists() else ""

            note = genanki.Note(
                model=model,
                fields=[land_trans, cap_trans, map_tag, flag_tag, audio_tag]
            )
            deck.add_note(note)

            # quiz item JSON (paths relative to /decks/{lang}/)
            quiz_items.append({
                "country_en": en_name,
                "country": land_trans,
                "capital": cap_trans,
                "map": f"maps/{map_media.name}" if map_media.exists() else None,
                "flag": f"flags/{flag_media.name}" if flag_media.exists() else None,
                "audio": f"audio/{audio_filename}" if media_audio.exists() else None
            })

        # write apkg
        package = genanki.Package(deck)
        # dedupe media
        media_files = list(dict.fromkeys(all_media))
        package.media_files = media_files
        apkg_path = out_dir / f"europese_hoofdsteden_{lang}.apkg"
        package.write_to_file(str(apkg_path))
        print(f"   ✅ apkg geschreven: {apkg_path}")

        # write quiz json (used by mobile app)
        json_path = out_dir / f"quiz_data_{lang}.json"
        with json_path.open("w", encoding="utf-8") as f:
            json.dump(quiz_items, f, ensure_ascii=False, indent=2)
        print(f"   ✅ json geschreven: {json_path}")

        # korte pauze
        time.sleep(0.8)

    print("🎉 Klaar! Alle talen gegenereerd in", OUTPUT)

if __name__ == "__main__":
    main()

