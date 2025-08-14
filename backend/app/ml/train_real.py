# app/ml/train_real.py
import os
import time
import sqlite3
import argparse
import numpy as np
import joblib

from sklearn.ensemble import GradientBoostingClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.metrics import classification_report

from .features import make_features
from ..storage import DB_PATH  # Usa lo stesso DB del backend!

MODEL_PATH = os.path.join(os.path.dirname(__file__), "model_store", "model.pkl")


def _get_event_columns(con) -> set:
    """Ritorna l'insieme dei nomi colonna della tabella events."""
    cols = set()
    for cid, name, ctype, notnull, dflt, pk in con.execute("PRAGMA table_info(events)").fetchall():
        cols.add(name)
    return cols


def load_events(days: int):
    """
    Carica eventi dagli ultimi `days` giorni.
    Se alcune colonne non esistono (es. abuse_score, cf_action) usa default sicuri.
    Ritorna (rows, selected_cols) dove rows è una lista di tuple nello stesso ordine di selected_cols.
    """
    if not os.path.exists(DB_PATH):
        raise SystemExit(f"[ERR] DB non trovato: {DB_PATH}")

    since_ts = int(time.time()) - days * 86400

    with sqlite3.connect(DB_PATH, timeout=30) as con:
        # Migliora la convivenza con il backend in scrittura
        try:
            con.execute("PRAGMA journal_mode=WAL;")
        except Exception:
            pass

        available = _get_event_columns(con)

        # Colonne minime che il backend salva sicuramente
        base_cols = ["ts", "vector", "pps", "bps", "score"]
        # Colonne opzionali (se esistono le includiamo)
        opt_cols = [c for c in ("abuse_score", "cf_action") if c in available]

        selected_cols = base_cols + opt_cols
        sql = f"SELECT {', '.join(selected_cols)} FROM events WHERE ts >= ? ORDER BY ts ASC"
        rows = con.execute(sql, (since_ts,)).fetchall()

    return rows, selected_cols


def label_and_features(rows, cols):
    """
    Crea X (feature) e y (etichette) con una weak-supervision euristica:
    - intensità (log pps + log bps)
    - abuse_score (se presente)
    - azione CF (block/challenge)
    - vettore (UDP/HTTP2/altro)
    - score del modello precedente (se presente)
    La soglia è il 70° percentile del proxy → ~30% positivi.
    """
    # Indici colonna
    idx = {name: i for i, name in enumerate(cols)}

    X = []
    risks = []
    has_abuse = "abuse_score" in idx
    has_action = "cf_action" in idx
    has_prev_score = "score" in idx

    for row in rows:
        pps = float(row[idx["pps"]])
        bps = float(row[idx["bps"]])
        vector = (row[idx["vector"]] or "SYN")
        abuse = int(row[idx["abuse_score"]]) if has_abuse else 0
        action = (row[idx["cf_action"]] or "allow") if has_action else "allow"
        prev_score = float(row[idx["score"]]) if has_prev_score else 0.0

        # Features per il modello
        ev = {
            "pps": int(pps),
            "bps": float(bps),
            "abuse_score": abuse,
            "cf_action": action,
            "vector": vector
        }
        X.append(make_features(ev))

        # Proxy risk per weak labels
        proxy = 0.0
        proxy += np.log(pps + 1.0) + np.log(bps + 1.0)             # intensità
        proxy += (abuse / 20.0)                                     # reputazione
        proxy += 2.5 if action == "block" else (1.2 if action == "challenge" else 0.0)
        proxy += 0.8 if vector == "UDP" else (0.5 if vector == "HTTP2" else 0.2)
        proxy += prev_score * 2.0                                   # conoscenza pregressa
        risks.append(proxy)

    X = np.asarray(X, dtype=float)
    risks = np.asarray(risks, dtype=float)

    if len(risks) == 0:
        raise SystemExit("[ERR] Nessun dato disponibile per creare le etichette.")

    thr = float(np.percentile(risks, 70.0))  # ~30% positivi
    y = (risks >= thr).astype(int)

    return X, y


def main(days: int, min_rows: int):
    rows, cols = load_events(days)
    n_rows = len(rows)
    if n_rows < min_rows:
        print(f"[WARN] Troppi pochi eventi ({n_rows}) negli ultimi {days} giorni; "
              f"aggiungi dati o abbassa --min-rows.")
        return 1

    X, y = label_and_features(rows, cols)

    # Deve esserci varietà nelle etichette
    if len(np.unique(y)) < 2:
        print("[WARN] Label monoclasse: estendi la finestra (--days) o rivedi l'euristica.")
        return 1

    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    base = GradientBoostingClassifier(random_state=42)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    clf = CalibratedClassifierCV(base, method="isotonic", cv=cv)
    clf.fit(Xtr, ytr)

    ypred = clf.predict(Xte)
    print(classification_report(yte, ypred, digits=3))

    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    joblib.dump(clf, MODEL_PATH)
    print(f"[OK] Nuovo modello salvato in: {MODEL_PATH}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=3, help="quanti giorni di dati usare (default 3)")
    ap.add_argument("--min-rows", type=int, default=5000, help="minimo eventi per addestrare (default 5000)")
    args = ap.parse_args()
    raise SystemExit(main(args.days, args.min_rows))
    