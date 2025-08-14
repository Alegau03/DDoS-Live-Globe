# app/ingest/radar_api.py
import time, random, sys
from typing import List, Tuple, Dict, Any
import httpx
from ..config import settings

BASE = "https://api.cloudflare.com/client/v4/radar"
HDRS = {"Authorization": f"Bearer {settings.RADAR_API_TOKEN}", "Accept": "application/json"}
import httpx
CLIENT = httpx.Client(
    headers=HDRS,
    timeout=20.0,
    limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
)

# Global per /api/source (facoltativo)
LAST_MODE = "unknown"

# Centroidi per il rendering
CENTROIDS = {
  "US": (38.0, -97.0), "CN": (36.0, 104.0), "RU": (61.5, 99.0), "GB": (54.0, -2.0),
  "DE": (51.0, 10.0), "FR": (46.0, 2.0), "IT": (42.8, 12.5), "ES": (40.4, -3.7),
  "NL": (52.2, 5.3), "SE": (62.0, 15.0), "NO": (61.0, 8.0), "PL": (52.0, 19.0),
  "UA": (49.0, 32.0), "TR": (39.0, 35.0), "IR": (32.0, 53.0), "IN": (22.0, 79.0),
  "JP": (36.0, 138.0), "KR": (36.5, 127.9), "TW": (23.7, 121.0), "HK": (22.3, 114.2),
  "SG": (1.35, 103.8), "AU": (-25.0, 133.0), "BR": (-14.0, -52.0), "AR": (-34.0, -64.0),
  "MX": (23.0, -102.0), "CA": (56.0, -106.0), "ZA": (-29.0, 24.0), "EG": (26.5, 30.0),
  "SA": (24.0, 45.0)
}
FALLBACK_CCS = ["US","CN","RU","GB","DE","FR","IT","ES","NL","SE","PL","TR","IN","JP","KR","TW","SG","AU","BR","MX","CA","ZA","EG","SA"]

def _get(path: str, params: dict) -> dict:
    r = CLIENT.get(f"{BASE}/{path}", params=params)
    if r.status_code != 200:
        try:
            j = r.json()
        except Exception:
            j = {"errors": r.text[:200]}
        print(f"[RADAR] GET {path} -> {r.status_code} errors={j.get('errors')}", file=sys.stderr)
    r.raise_for_status()
    return r.json()


def _proto_mix(date_range: str) -> List[Tuple[str,float]]:
    res = _get("attacks/layer3/summary/protocol", {"dateRange": date_range, "format": "json"})
    summary = (res.get("result") or {}).get("summary_0") or {}
    pairs = []
    for k in ("udp","tcp","icmp","gre"):
        if k in summary:
            try: pairs.append((k.upper(), float(summary[k])))
            except Exception: pass
    s = sum(v for _,v in pairs) or 1.0
    return [(p, v/s) for p,v in pairs] or [("UDP", 0.5), ("TCP", 0.5)]

def _first_list_in_result(res: dict) -> List[dict]:
    result = res.get("result") or {}
    if isinstance(result, list): return result
    if "top_0" in result and isinstance(result["top_0"], list): return result["top_0"]
    for k, v in result.items():
        if isinstance(v, list): return v
    return []

def _extract_cc(item: dict) -> str:
    # prova più chiavi, prendi la prima ISO-2
    for key in ["location","loc","code","alpha2","country","countryCode",
                "locationAlpha2","originCountryAlpha2","targetCountryAlpha2",
                "clientCountry","clientCountryAlpha2"]:
        cc = (item.get(key) or "").strip().upper()
        if len(cc) == 2: return cc
    # nested?
    for side in ("origin","source","target","destination"):
        sub = item.get(side) or {}
        for key in ["location","loc","code","alpha2","country","countryCode",
                    "locationAlpha2","originCountryAlpha2","targetCountryAlpha2",
                    "clientCountry","clientCountryAlpha2"]:
            cc = (sub.get(key) or "").strip().upper()
            if len(cc) == 2: return cc
    return ""

def _extract_val(item: dict) -> float:
    for key in ["value","percentage","share","count","attacks","requests"]:
        v = item.get(key)
        if v is not None:
            try: return float(v)
            except Exception: pass
    return 0.0

def _parse_top_locations(res: dict) -> List[Tuple[str, float]]:
    items = _first_list_in_result(res)
    out = []
    for it in items:
        cc = _extract_cc(it)
        val = _extract_val(it)
        if cc and val > 0:
            out.append((cc, val))
    s = sum(v for _,v in out) or 1.0
    return [(cc, v/s) for cc,v in out]

def _build_pairs(date_range: str, limit: int) -> List[Tuple[str,str,float]]:
    """Usa top origin/target; fallback solo se vuoto."""
    global LAST_MODE
    p = {"dateRange": date_range, "limit": str(limit), "format": "json"}

    origins_res = _get("attacks/layer3/top/locations/origin", p)
    targets_res = _get("attacks/layer3/top/locations/target", p)
    origins = _parse_top_locations(origins_res)
    targets = _parse_top_locations(targets_res)

    print(f"[RADAR] origin={len(origins)} target={len(targets)} range={date_range} limit={limit}", file=sys.stderr)

    if origins and targets:
        pairs = []
        tot = 0.0
        for oc, ow in origins:
            for dc, dw in targets:
                if oc == dc: 
                    continue
                w = ow*dw
                if oc in CENTROIDS and dc in CENTROIDS:
                    pairs.append((oc, dc, w)); tot += w
        if pairs and tot > 0:
            LAST_MODE = "radar_top_locations"
            return [(oc, dc, w/tot) for oc,dc,w in pairs]

    # fallback
    print("[RADAR] Top vuoti → fallback paesi std", file=sys.stderr)
    LAST_MODE = "radar_fallback"
    base = [(cc, 1.0/len(FALLBACK_CCS)) for cc in FALLBACK_CCS if cc in CENTROIDS]
    pairs, tot = [], 0.0
    for oc, ow in base:
        for dc, dw in base:
            if oc == dc: continue
            w = ow*dw; pairs.append((oc,dc,w)); tot += w
    return [(oc,dc,w/(tot or 1.0)) for oc,dc,w in pairs]

def poll_radar_pairs(date_range: str = None, limit: int = None, batch_events: int = 150):
    # Permetti override via .env (facoltativo)
    date_range = date_range or getattr(settings, "RADAR_DATE_RANGE", "1d")
    limit = int(limit or getattr(settings, "RADAR_LIMIT", 20))

    protos = _proto_mix(date_range)  # [(PROTO, weight)]
    while True:
        try:
            pairs = _build_pairs(date_range, limit)
            if not pairs:
                print("[RADAR] Nessuna coppia disponibile (anche dopo fallback) — retry 5s", file=sys.stderr)
                time.sleep(5.0); continue

            # CDF coppie
            cdf, acc = [], 0.0
            for oc, dc, w in pairs:
                acc += w; cdf.append((acc, oc, dc))
            # CDF protocolli
            pcdf, pacc = [], 0.0
            for p, w in protos:
                pacc += w; pcdf.append((pacc, "UDP" if p=="GRE" else p))

            now = int(time.time())
            for _ in range(batch_events):
                # pick coppia
                r = random.random()
                oc, dc = None, None
                for cut, o, d in cdf:
                    if r <= cut:
                        oc, dc = o, d; break
                if not oc or not dc: 
                    continue

                # pick protocollo
                pr = random.random()
                proto = "UDP"
                for cut, p in pcdf:
                    if pr <= cut:
                        proto = p; break

                # intensità fittizia ma coerente
                base_pps = 10**random.uniform(4.2, 5.6)    # ~15k..400k
                weight = next((w for (o,d,w) in pairs if o==oc and d==dc), 0.01)
                pps = int(base_pps * (0.5 + 3.0*weight))
                avg_pkt = random.uniform(64, 650)          # B/pkt
                bytes_total = pps * avg_pkt * random.uniform(0.8, 1.2)

                yield {
                    "ts": now,
                    "src_country": oc, "dst_country": dc,
                    "src_lat": CENTROIDS.get(oc, (0,0))[0], "src_lon": CENTROIDS.get(oc, (0,0))[1],
                    "dst_lat": CENTROIDS.get(dc, (0,0))[0], "dst_lon": CENTROIDS.get(dc, (0,0))[1],
                    "src_asn": None, "dst_asn": None,
                    "src_ip": None, "bytes": float(bytes_total), "pps": int(pps),
                    "cf_action": "block",
                    "vector": "UDP" if proto=="UDP" else ("SYN" if proto=="TCP" else "HTTP2"),
                    "abuse_score": 0
                }
        except Exception as e:
            print(f"[RADAR] errore: {e}", file=sys.stderr)
            time.sleep(2.0)

        time.sleep(8.0)
