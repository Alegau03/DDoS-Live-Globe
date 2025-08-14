# 🌍 DDoS Live Globe — Real‑time Attack Visualization + On‑the‑fly ML Scoring

![Made with](https://img.shields.io/badge/Made%20with-FastAPI%20%7C%20Vite%20%7C%20Three.js-2ea44f?logo=fastapi\&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python)
![Node](https://img.shields.io/badge/Node-18%2B%20%7C%2020%2B%20%7C%2024%2B-43853d?logo=node.js\&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-black)

**DDoS Live Globe** è una web‑app che mostra un **globo 3D** con flussi di attacco (archi animati) in tempo reale e un **punteggio di rischio** calcolato da un modello ML. Funziona con tre modalità di sorgente dati:

* **Mock (default)** → per sviluppo istantaneo
* **Cloudflare Radar** (📡 *non serve un dominio*) → dati **reali e aggregati** L3 (origin/destination + mix protocolli)
* **Cloudflare per‑zona (GraphQL Firewall Events)** → dati **osservati sulla tua zona** (richiede dominio su Cloudflare)

> **Attribution**: quando usi Cloudflare Radar, cita la fonte in app/README (es. “Data source: Cloudflare Radar”).

---

## 🗂️ Indice

* [✨ Demo: cosa vedrai](#-demo-cosa-vedrai)
* [🧭 Architettura](#-architettura)
* [🧩 Stack](#-stack)
* [📂 Struttura del progetto](#-struttura-del-progetto)
* [⚙️ Setup rapido](#️-setup-rapido)

  * [Backend](#backend)
  * [Frontend](#frontend)
* [🖥️ Frontend — Globe & UI (pulsanti e menù)](#️-frontend--globe--ui-pulsanti-e-menù)
* [🔌 Backend — API & WebSocket](#-backend--api--websocket)
* [🧠 Modello ML — come funziona](#-modello-ml--come-funziona)

  * [📈 Metriche modello (ultimo run)](#-metriche-modello-ultimo-run)
  * [🔁 Retraining: ogni quanto e come](#-retraining-ogni-quanto-e-come)
* [🧪 Troubleshooting](#-troubleshooting)
* [🔐 Privacy & Sicurezza](#-privacy--sicurezza)
* [🏷️ Crediti](#️-crediti)
* [🛣️ Roadmap](#️-roadmap)
* [📜 License](#-license)

---

## ✨ Demo: cosa vedrai

* Globo realistico (Blue Marble, atmosfera, nuvole) con **auto‑rotate**
* **Archi animati** origine → destinazione, altezza/colore legati a **bps** e **score**
* KPI live: Eventi/s, Gbps medio, Max score
* Pannello filtri: **paesi**, **vettori**, **soglia score**, **schema colore**
* Tabelle **Top Sorgenti** e **Top Vettori** (ultimi N eventi)

---

## 🧭 Architettura

Data Sources → Ingest → Producer → Broadcaster(WS) → Frontend
                     ↘ Scorer(ML) → model.pkl
                     ↘ SQLite (events.db)

Data sources:
  • Cloudflare Radar (L3 aggregati: origin/target + mix protocolli)
  • Cloudflare per‑zona (GraphQL Firewall Events)
  • Mock generator (sviluppo)

**Flow:** Sorgente dati → *Enrich* → **Scorer (ML)** → EventOut → **WebSocket** → Frontend (arcs/points). Gli eventi vengono anche **salvati** in SQLite per il **retraining** periodico.

---

## 🧩 Stack

* **Frontend:** Vite, React, `react-globe.gl` (Three.js), Tailwind
* **Backend:** FastAPI, Uvicorn (WebSocket), HTTPX
* **ML:** scikit‑learn (GradientBoosting + CalibratedClassifier), joblib
* **Storage:** SQLite (IP hashati per privacy)

---

## 📂 Struttura del progetto

```
ddos-globe/
├─ frontend/
│  ├─ src/
│  │  ├─ components/GlobeView.jsx
│  │  ├─ components/ControlPanel.jsx
│  │  ├─ components/TopTables.jsx
│  │  ├─ lib/ws.js
│  │  ├─ App.jsx / main.jsx / styles.css
│  ├─ index.html, tailwind.config.js, postcss.config.js, .env.local
├─ backend/
│  ├─ app/
│  │  ├─ ingest/
│  │  │  ├─ enrich.py
│  │  │  ├─ radar_api.py (per Radar)
│  │  │  ├─ cloudflare_graphql.py (opzionale)
│  │  │  └─ cloudflare_mock.py
│  │  ├─ ml/
│  │  │  ├─ features.py
│  │  │  ├─ model.py
│  │  │  └─ train_real.py
│  │  ├─ utils/geoip.py
│  │  ├─ storage.py
│  │  ├─ schemas.py
│  │  ├─ config.py
│  │  └─ main.py
│  ├─ data/events.db (auto)
│  ├─ .env
│  └─ requirements.txt
```

---

## ⚙️ Setup rapido

### Backend

```bash
cd backend
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows
# .venv\Scripts\activate

pip install --upgrade pip
pip install -r requirements.txt
# WebSocket/performances consigliati
pip install "uvicorn[standard]" websockets wsproto uvloop httptools httpx pydantic-settings
```

`backend/.env` — **Scegli UNA sorgente**

```env
# A) MOCK (sviluppo immediato)
USE_MOCK_INGEST=true
USE_RADAR_INGEST=false

# B) RADAR (reale, non serve dominio)
# USE_MOCK_INGEST=false
# USE_RADAR_INGEST=true
# RADAR_API_TOKEN=cf_radar_XXXXXXXXXXXXXXXX
# RADAR_DATE_RANGE=1d      # opzionale (1d/7d/30d)
# RADAR_LIMIT=20           # opzionale

# C) CLOUDFLARE PER-ZONA (reale, richiede dominio/Zone ID)
# USE_MOCK_INGEST=false
# USE_RADAR_INGEST=false
# CLOUDFLARE_API_TOKEN=cf_...
# CLOUDFLARE_ZONE_TAG=...

# AbuseIPDB (opzionale; usato solo quando abbiamo IP per-sorgente)
ABUSEIPDB_KEY=
ABUSEIPDB_TTL_SEC=3600

# Privacy
HASH_IP_SALT=metti_una_stringa_lunga_casuale
```

Avvio backend:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --ws websockets
# Health: http://127.0.0.1:8000/api/health
```

### Frontend

```bash
cd frontend
npm i

# Punto il WS del backend
echo "VITE_WS_URL=ws://localhost:8000/ws/events" > .env.local

npm run dev
# http://localhost:5173
```

---

## 🖥️ Frontend — Globe & UI (pulsanti e menù)

**Componenti chiave**

* **GlobeView** → rendering del globo (texture realistiche, luci, auto‑rotate)
* **ControlPanel** → pannello comandi (filtri e azioni)
* **TopTables** → riepilogo (Top Paesi sorgente, Top Vettori)
* **Stream manager** → connessione WS + fallback automatico al mock se il WS tace per \~3s

**Pannello KPI (in alto a sinistra)**

* **Eventi/s** → eventi ricevuti nell’ultimo secondo
* **Media Gbps** → media dei bit/s (in Gbps) su coda breve
* **Max score** → punteggio massimo visto di recente (0–100%)

**Control Panel (in alto a destra)**

* **Pausa/Riprendi** → ferma/riprende l’aggiornamento (gli eventi continuano ad arrivare)
* **Clear** → svuota la coda visiva (archi/punti)
* **Soglia score minima** (slider 0–1) → mostra solo `score ≥ soglia`

  * 0.0–0.2 → vista ampia (molti archi)
  * 0.6–0.9 → focus su eventi più severi
* **Vettori** (SYN / UDP / HTTP2) → on/off per includere/escludere famiglie/protocolli
* **Filtro Paesi sorgente** (ISO‑2, es. `CN,US,IT`) → vuoto = tutti
* **Colorazione archi**

  * **Per severità (score)** → rosso (>0.85), arancio (0.65–0.85), azzurro (<0.65)
  * **Per vettore** → UDP giallo/arancio, SYN blu, HTTP2 viola

**Tabelle (in basso a sinistra)**

* **Top Paesi sorgente** → conteggi, **Avg Score** e **\~Gbps** stimato
* **Top Vettori** → suddivisione per SYN/UDP/HTTP2 con le stesse metriche

**Logica di rendering**

* Un **arco** per evento (origine→destinazione) + un **punto** sul target (dimensione ∝ `pps`)
* **Altitudine arco** ∝ `log10(bps)` + `score` → archi alti = più impatto visivo
* **Tooltip/label**: `SRC → DST • VECTOR • Gbps • score%`

**Fallback**

* Se il WS non invia entro \~3s, il frontend usa il **mock** per non restare vuoto. In console: `fallback a mock`.

---

## 🔌 Backend — API & WebSocket

**Endpoint principali**

* `GET /api/health` → stato server

  ```json
  { "status":"ok", "events":1230, "uptime_sec":283, "clients":1 }
  ```
* `GET /api/source` → sorgente corrente (se abilitato)

  ```json
  { "mode":"radar_top_locations" }  // oppure "radar_fallback" / "mock" / "cloudflare"
  ```
* `GET /api/db/stats` → righe nel DB (opzionale, se abilitato)

  ```json
  { "db_path":".../backend/data/events.db", "rows":15450 }
  ```
* `WS /ws/events` → stream eventi in tempo reale (JSON line‑by‑line)

**Schema evento (EventOut)**

```json
{
  "ts": 1723620000,
  "src": { "country":"CN", "asn": null, "lat":36.0, "lon":104.0 },
  "dst": { "country":"IT", "asn": null, "lat":42.8, "lon":12.5 },
  "vector": "UDP",         // SYN | UDP | HTTP2
  "pps": 120000,
  "bps": 1.8e9,
  "score": 0.73             // 0..1
}
```

> Con **Radar**: non ci sono IP; le coordinate sono i **centroidi** del Paese. Il **mix protocolli** è reale; le coppie OC→DC vengono dai **top origin/target** (o fallback se l’API restituisce liste vuote).

---

## 🧠 Modello ML — come funziona

* **Architettura:** `GradientBoostingClassifier` calibrato (`CalibratedClassifierCV` isotonic)
* **Feature** (vedi `app/ml/features.py`):

  * `log_pps`, `log_bps`, `bps/pps`
  * `abuse_score` (0 con Radar; >0 se usi IP/AbuseIPDB)
  * one‑hot **cf\_action** (`allow/challenge/block`)
  * one‑hot **vector** (`SYN/UDP/HTTP2`)
* **Cold‑start:** se manca `model.pkl`, il backend addestra un **modello sintetico** bilanciato.
* **Scoring online:** ogni evento → feature → `predict_proba` → `score` ∈ \[0,1]; l’evento + score va anche in SQLite.

### 📈 Metriche modello (ultimo run)

*Training del **14 Aug 2025** (split 80/20 su dati reali memorizzati, `--days 3`) — report sul test set:*

| Classe           | Precision | Recall |    F1 | Support |
| ---------------- | --------: | -----: | ----: | ------: |
| 0 (neg)          |     0.951 |  0.930 | 0.940 |    2457 |
| 1 (pos)          |     0.844 |  0.889 | 0.866 |    1053 |
| **Accuracy**     | **0.917** |        |       |    3510 |
| **Macro avg**    |     0.898 |  0.909 | 0.903 |    3510 |
| **Weighted avg** |     0.919 |  0.917 | 0.918 |    3510 |

> Suggerimento soglia UI: **0.6–0.7** per ridurre falsi positivi mantenendo buona sensibilità.

### 🔁 Retraining: ogni quanto e come

* **Quando:**

  * **settimanale** in ambienti dinamici (es. `--days 7`),
  * **mensile** se il traffico è stabile.
  * In alternativa, ogni **N eventi** (es. ogni 50–100k righe nuove), oppure quando noti drift (score medi che cambiano).
* **Come:**

  ```bash
  # verifica volume dati
  sqlite3 backend/data/events.db 'SELECT COUNT(*) FROM events;'

  # addestra (esempi)
  cd backend
  source .venv/bin/activate
  python -m app.ml.train_real --days 3 --min-rows 5000
  # oppure
  python -m app.ml.train_real --days 7 --min-rows 8000

  # riavvio backend per caricare il nuovo modello
  uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --ws websockets
  ```
* **Lock DB:** se serve, abilita WAL:

  ```bash
  sqlite3 backend/data/events.db "PRAGMA journal_mode=WAL;"
  ```

---

## 🧪 Troubleshooting

* **WS non si connette / 404 / Unsupported upgrade**

  * Installa: `pip install "uvicorn[standard]" websockets wsproto uvloop httptools`
  * Avvia con: `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --ws websockets`
  * Frontend: `VITE_WS_URL=ws://localhost:8000/ws/events`

* **`/api/health` ok ma niente archi**

  * Abbassa lo **slider score** (0.0–0.2) e abilita tutti i **vettori**
  * Se il WS tace, il FE va in **mock** (controlla la console)

* **Pydantic v2 (`BaseSettings` moved)**

  * Usa `pydantic-settings`: `from pydantic_settings import BaseSettings`

* **Radar top vuoti**

  * Prova `RADAR_DATE_RANGE=1d/7d/30d` e `RADAR_LIMIT=20/50`
  * Il backend cade su **fallback** (con mix protocolli **reale**) e continua a funzionare

---

## 🔐 Privacy & Sicurezza

* IP (quando presenti) **hashati** con salt (`HASH_IP_SALT`) prima del salvataggio
* Mappa con **centroidi** di Paese per ridurre rischio di re‑identificazione
* Non committare le chiavi `.env`

---

## 🏷️ Crediti

* **Dati Radar**: Cloudflare Radar — attribuzione consigliata (“Data source: Cloudflare Radar”).
* **Globe**: `react-globe.gl` / `three-globe` + texture Blue Marble.

---

## 🛣️ Roadmap

* Endpoint `/api/model/info` (timestamp/percorso del modello)
* Replay ultimi 10 minuti da SQLite
* Heatmap densità per Paese/ASN
* Esportazione screenshot/clip delle animazioni
* SHAP per spiegazioni locali dello score

---

## 📜 License

MIT — fai fork, modifica e **mostrami** la tua versione! ✨
