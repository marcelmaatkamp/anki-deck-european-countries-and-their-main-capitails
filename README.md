# Anki Flashcards for European countries and their main capitals

<ul>
 <li><a href="https://github.com/marcelmaatkamp/anki-deck-european-countries-and-their-main-capitails/raw/refs/heads/master/decks/en/europese_hoofdsteden_en.apkg">EN</a></li>
</ul>

# step 1

install python dependencies

```bash
pip install geopandas matplotlib pandas genanki gTTS requests pycountry deep-translator Pillow
```

# step 2 

install country vector data

```bash
wget https://www.naturalearthdata.com/http//www.naturalearthdata.com/download/110m/cultural/ne_110m_admin_0_countries.zip
unzip ne_110m_admin_0_countries.zip -d data/
```

# step 3 

generate anki flashcards

```bash
python generate_decks_and_media.py
```
