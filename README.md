# Anki Flashcards for European countries and their main capitals

# step 1

install python dependencies

```bash
pip install geopandas matplotlib pandas deep-translator pycountry
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
python generate.py
```
