import os
import joblib
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.metrics import f1_score
from .features import make_features

MODEL_PATH = os.path.join(os.path.dirname(__file__), "model_store", "model.pkl")

class Scorer:
    def __init__(self):
        self.model = None
        if os.path.exists(MODEL_PATH):
            self.model = joblib.load(MODEL_PATH)
        else:
            self.model = self._train_and_save()

    def _train_and_save(self):
        X, y = self._make_synth_balanced(n=10000, seed=42)
        # split stratificato per garantire entrambe le classi in train/test
        Xtr, Xte, ytr, yte = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        base = GradientBoostingClassifier(random_state=42)
        # CV stratificata e shufflata per la calibrazione (evita fold monoclasse)
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        clf = CalibratedClassifierCV(base, method="isotonic", cv=cv)
        clf.fit(Xtr, ytr)

        ypred = clf.predict(Xte)
        f1 = f1_score(yte, ypred)
        print(f"[ML] Trained synthetic model (balanced). F1={f1:.3f} | class dist train={np.bincount(ytr).tolist()}")

        os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
        joblib.dump(clf, MODEL_PATH)
        return clf

    def _make_synth_balanced(self, n=10000, seed=0):
        """
        Genera dati sintetici, calcola uno 'score' continuo e poi
        imposta la soglia al 70° percentile per ottenere ~30% positivi.
        In fallback usa la mediana per garantire due classi.
        """
        rng = np.random.default_rng(seed)
        feats_list, scores = [], []

        for _ in range(n):
            # distribuzioni realistiche (coda lunga)
            pps = float(np.exp(rng.uniform(10, 14)))                # ~2e4 .. 1.2e6
            bps = float(pps * rng.integers(60, 260))                # scala con pps
            abuse = int(np.clip(rng.normal(45, 25), 0, 100))
            action = rng.choice(["allow","challenge","block"], p=[0.6,0.25,0.15])
            vector = rng.choice(["SYN","UDP","HTTP2"], p=[0.5,0.3,0.2])

            ev = {
                "pps": int(pps),
                "bytes": bps / 8.0,
                "abuse_score": abuse,
                "cf_action": action,
                "vector": vector
            }
            feats = make_features(ev)
            feats_list.append(feats)

            # score “proxy”: combinazione di intensità + reputation + azione CF + vettore
            s = (np.log(pps + 1) + np.log(bps + 1)) + (abuse / 20.0)
            s += 2.5 if action == "block" else (1.2 if action == "challenge" else 0.0)
            s += 0.8 if vector == "UDP" else (0.5 if vector == "HTTP2" else 0.2)
            scores.append(s)

        X = np.array(feats_list, dtype=float)
        scores = np.array(scores, dtype=float)

        # soglia al 70° percentile → circa 30% positivi
        thr = float(np.percentile(scores, 70.0))
        y = (scores >= thr).astype(int)

        # guardrail: se ancora sbilanciato/monoclasse, usa mediana
        if len(np.unique(y)) < 2 or min(np.bincount(y)) < 50:
            thr = float(np.median(scores))
            y = (scores >= thr).astype(int)

        return X, y

    def score_event(self, ev: dict) -> float:
        feats = np.array([make_features(ev)], dtype=float)
        proba = float(self.model.predict_proba(feats)[0, 1])
        return max(0.0, min(1.0, proba))

scorer_singleton = None

def get_scorer():
    global scorer_singleton
    if scorer_singleton is None:
        scorer_singleton = Scorer()
    return scorer_singleton
