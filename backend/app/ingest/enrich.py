import time
from collections import deque, defaultdict
from typing import Deque, Dict, Iterator, Tuple, Optional

from ..config import settings
from ..utils.geoip import country_to_latlon

# Import "soft": importiamo i moduli solo se servono.
def _choose_source() -> Iterator[dict]:
    """Seleziona la sorgente eventi:
    - Radar se USE_RADAR_INGEST=true e c'è il token
    - Cloudflare GraphQL se non mock e sono presenti token+zone
    - Altrimenti Mock
    """
    use_radar = bool(getattr(settings, "USE_RADAR_INGEST", False)) and bool(getattr(settings, "RADAR_API_TOKEN", ""))
    use_mock = bool(getattr(settings, "USE_MOCK_INGEST", False))
    cf_token = getattr(settings, "CLOUDFLARE_API_TOKEN", "") or ""
    cf_zone  = getattr(settings, "CLOUDFLARE_ZONE_TAG", "") or ""

    if use_radar:
        from .radar_api import poll_radar_pairs
        return poll_radar_pairs()  # già in forma "arricchita" (ha lat/lon/pps/bps)
    if (not use_mock) and cf_token and cf_zone:
        from .cloudflare_graphql import poll_firewall_events
        return poll_firewall_events(zone_tag=cf_zone, api_token=cf_token, window_sec=60, poll_every=3.0)
    # fallback
    from .cloudflare_mock import generate_events
    return generate_events()


# ---- Stima PPS/BPS su finestra scorrevole -----------------------------------

WINDOW_SEC = 3  # larghezza finestra per stima tassi

class RateEstimator:
    """Stima pps/bps contando eventi nella finestra scorrevole.
    Usa la chiave IP se disponibile, altrimenti (src_country, dst_country).
    """
    def __init__(self):
        self.events_by_key: Dict[Tuple, Deque[float]] = defaultdict(deque)

    def _key(self, ev: dict) -> Tuple:
        ip = ev.get("src_ip")
        if ip:
            return ("ip", ip)
        # Radar/non-IP → fallback per coppia paese
        return ("cc", ev.get("src_country"), ev.get("dst_country"))

    def update(self, ev: dict, now: float) -> Tuple[int, float]:
        dq = self.events_by_key[self._key(ev)]
        dq.append(now)
        # drop vecchi
        while dq and (now - dq[0] > WINDOW_SEC):
            dq.popleft()
        pps = int(len(dq) / max(1e-6, WINDOW_SEC))
        # stima bps: byte/evento ~ 800B come default, scalabile
        avg_bytes = float(ev.get("bytes", 800.0))
        bps = float(pps * avg_bytes * 8.0)
        return pps, bps


# ---- AbuseIPDB (safe: ritorna 0 senza chiave o senza IP) ---------------------

def _abuse_score(ip: Optional[str]) -> int:
    if not ip:
        return 0
    try:
        from .abuseipdb import lookup_abuse_score
    except Exception:
        return 0
    return int(lookup_abuse_score(ip))


# ---- Normalizzazione evento → formato unico per il resto del backend ---------

def _normalize_from_radar(ev: dict) -> dict:
    """Gli eventi Radar hanno già: src/dst country + lat/lon + pps/bps (fittizi ma coerenti)."""
    return {
        "ts": int(ev["ts"]),
        "src_ip": None,
        "dst_ip": None,
        "bytes": float(ev.get("bytes", 0.0)),
        "pps": int(ev.get("pps", 0)),
        "cf_action": ev.get("cf_action", "block"),
        "vector": ev.get("vector", "UDP"),

        "src_country": ev["src_country"],
        "src_asn": ev.get("src_asn"),
        "src_lat": float(ev["src_lat"]),
        "src_lon": float(ev["src_lon"]),

        "dst_country": ev["dst_country"],
        "dst_asn": ev.get("dst_asn"),
        "dst_lat": float(ev["dst_lat"]),
        "dst_lon": float(ev["dst_lon"]),

        "abuse_score": 0  # Radar non ha IP ⇒ niente reputation
    }

def _normalize_from_cf_or_mock(ev: dict, estimator: RateEstimator, now: float) -> dict:
    """Cloudflare GraphQL o Mock:
    - Se presenti client_country/asn li usiamo; altrimenti centroidi/dummy ASN
    - Stima pps/bps su finestra
    - Geo destinazione: per la demo usiamo IT (puoi cambiarlo a piacere)
    """
    src_cc = ev.get("client_country")
    if not src_cc:
        # mock → possiamo derivare da ev.get("src_country") o default US
        src_cc = ev.get("src_country") or "US"

    src_asn = ev.get("client_asn")
    if src_asn is None:
        src_asn = ev.get("src_asn")

    # coordinate centroidi
    src_lat, src_lon = country_to_latlon(src_cc)

    # destinazione "demo" (puoi configurare)
    dst_cc = ev.get("dst_country") or "IT"
    dst_lat, dst_lon = country_to_latlon(dst_cc)

    # stima tassi
    pps_est, bps_est = estimator.update({
        "src_ip": ev.get("src_ip"),
        "src_country": src_cc,
        "dst_country": dst_cc,
        "bytes": float(ev.get("bytes", 800.0))
    }, now)

    # prendi action/vector se presenti
    action = ev.get("cf_action", "allow")
    vector = ev.get("vector", "SYN")

    abuse = _abuse_score(ev.get("src_ip"))

    return {
        "ts": int(ev.get("ts", time.time())),
        "src_ip": ev.get("src_ip"),
        "dst_ip": ev.get("dst_ip", "0.0.0.0"),
        "bytes": max(float(ev.get("bytes", 0.0)), bps_est/8.0),  # coerenza con bps stimato
        "pps": max(int(ev.get("pps", 0)), pps_est),
        "cf_action": action,
        "vector": vector,

        "src_country": src_cc,
        "src_asn": src_asn,
        "src_lat": src_lat,
        "src_lon": src_lon,

        "dst_country": dst_cc,
        "dst_asn": ev.get("dst_asn"),
        "dst_lat": dst_lat,
        "dst_lon": dst_lon,

        "abuse_score": abuse
    }


# ---- Stream pubblico per il resto dell'app -----------------------------------

def stream_enriched() -> Iterator[dict]:
    """
    Iteratore che produce eventi normalizzati per il backend:
    campi garantiti:
      ts, src_ip, dst_ip, bytes, pps, cf_action, vector,
      src_country, src_asn, src_lat, src_lon,
      dst_country, dst_asn, dst_lat, dst_lon,
      abuse_score
    """
    src_iter = _choose_source()
    estimator = RateEstimator()

    for raw in src_iter:
        # Se la sorgente fornisce già lat/lon (Radar), normalizza "pass-through"
        if "src_lat" in raw and "dst_lat" in raw:
            yield _normalize_from_radar(raw)
            continue

        # Cloudflare/Mock → arricchisci
        now = time.time()
        yield _normalize_from_cf_or_mock(raw, estimator, now)
