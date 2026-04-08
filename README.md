# 𐤎 Stribog

**AI entitet koji uči od tebe. Imenovan po slovenskom bogu vetrova.**

Stribog je "beba AI" — ne zna ništa dok ga ne naučiš. Sve što mu kažeš, pamti zauvek u SQLite bazi. Koristi Claude API za rezonovanje, ali znanje crpi isključivo iz onoga što si ga ti naučio.

## Kako radi

1. **Učiš ga** — kažeš "zapamti da je nebo plavo" → on to čuva u memoriji
2. **Pitaš ga** — kažeš "koje boje je nebo?" → on pretražuje memoriju + rezonuje
3. **Ispravljaš ga** — kažeš "ne, nije tako" → on pamti ispravku
4. **Daješ feedback** — 👍 ili 👎 na svaki odgovor → oblikuje ponašanje

## Pokretanje lokalno

```bash
# 1. Kloniraj repo
git clone https://github.com/Zevs2310/stribog.git
cd stribog

# 2. Instaliraj dependencies
pip install -r requirements.txt

# 3. Postavi API ključ
export ANTHROPIC_API_KEY="sk-ant-..."

# 4. Pokreni
python app.py

# 5. Otvori http://localhost:5000
```

## Deploy na Render.com

1. Push na GitHub
2. Na Render.com → New Web Service → poveži repo
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn app:app --bind 0.0.0.0:$PORT`
5. Dodaj Environment Variable: `ANTHROPIC_API_KEY`

## Struktura

```
stribog/
├── app.py              # Flask backend — mozak, memorija, API
├── templates/
│   └── index.html      # Chat UI
├── requirements.txt
├── stribog_memory.db   # SQLite baza (kreira se automatski)
└── README.md
```

## Sledeći koraci

- [ ] ServiceNow REST API integracija
- [ ] GitHub API integracija  
- [ ] Glasovna komunikacija
- [ ] Vizuelna memorija (slike)
- [ ] Personality evolution system

## Ime

**Stribog** (Стрибог) — slovenski bog vetrova i vazdušnih strujanja. 
Svi vetrovi smatrani su njegovim unucima. Zamišljan kao mudri starac 
koji skuplja i rasejava znanje na krilima vetra.
