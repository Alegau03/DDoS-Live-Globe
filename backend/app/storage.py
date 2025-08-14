# app/storage.py
import os, sqlite3, threading

# Path assoluto (indipendente dalla cwd/--reload)
ROOT = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(ROOT, "data")
DB_PATH = os.path.join(DATA_DIR, "events.db")

_con = None
_lock = threading.Lock()

# Colonne che il codice usa oggi (se mancano, le aggiungiamo)
REQUIRED_COLS = {
    # nome: DDL per ADD COLUMN (solo colonne opzionali qui!)
    "src_asn":      "INTEGER",
    "dst_asn":      "INTEGER",
    "src_lat":      "REAL",
    "src_lon":      "REAL",
    "dst_lat":      "REAL",
    "dst_lon":      "REAL",
    "bps":          "REAL",
    "score":        "REAL",
    "abuse_score":  "INTEGER DEFAULT 0",
    "cf_action":    "TEXT DEFAULT 'allow'",
}

def _migrate_cols(con: sqlite3.Connection):
    # crea tabella se non c'è (schema base compatibile con versioni nuove)
    con.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts INTEGER NOT NULL,
        src_country TEXT, dst_country TEXT,
        vector TEXT,
        pps INTEGER
    )
    """)
    # scopri colonne esistenti
    have = {row[1] for row in con.execute("PRAGMA table_info(events)").fetchall()}
    # aggiungi quelle mancanti
    for col, ddl in REQUIRED_COLS.items():
        if col not in have:
            con.execute(f"ALTER TABLE events ADD COLUMN {col} {ddl};")
    con.commit()

def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    con = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    # performance/locking
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA busy_timeout=5000;")
    _migrate_cols(con)
    global _con
    _con = con
    return con

def get_con():
    global _con
    if _con is None:
        return init_db()
    return _con

def insert_event(ev: dict, score: float):
    """
    Inserisce un evento. Usa ev['bps'] se presente, altrimenti calcola da ev['bytes']*8.
    Campi opzionali gestiti via DEFAULT.
    """
    con = get_con()
    bps = float(ev.get("bps")) if ev.get("bps") is not None else float(ev.get("bytes", 0.0)) * 8.0
    with _lock:
        con.execute(
            "INSERT INTO events (ts, src_country, dst_country, src_asn, dst_asn, "
            "src_lat, src_lon, dst_lat, dst_lon, vector, pps, bps, score, abuse_score, cf_action) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                int(ev["ts"]),
                ev.get("src_country"), ev.get("dst_country"),
                ev.get("src_asn"), ev.get("dst_asn"),
                ev.get("src_lat"), ev.get("src_lon"),
                ev.get("dst_lat"), ev.get("dst_lon"),
                ev.get("vector"),
                int(ev.get("pps", 0)), bps,
                float(score),
                int(ev.get("abuse_score", 0)),
                ev.get("cf_action", "allow"),
            ),
        )
        con.commit()
