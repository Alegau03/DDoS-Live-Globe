import time, httpx
from ..config import settings

ABUSE_URL = "https://api.abuseipdb.com/api/v2/check"

class AbuseCache:
    def __init__(self, ttl_sec: int = 3600):
        self.ttl = ttl_sec
        self.store: dict[str, tuple[float,int]] = {}

    def get(self, ip: str) -> int | None:
        item = self.store.get(ip)
        if not item: return None
        exp, val = item
        if time.time() > exp:
            self.store.pop(ip, None)
            return None
        return val

    def put(self, ip: str, val: int):
        self.store[ip] = (time.time()+self.ttl, val)

_cache = AbuseCache(ttl_sec=settings.ABUSEIPDB_TTL_SEC)

def lookup_abuse_score(ip: str) -> int:
    # Se non c'è chiave → 0 (fallback)
    if not settings.ABUSEIPDB_KEY:
        return 0
    cached = _cache.get(ip)
    if cached is not None:
        return cached
    headers = {"Key": settings.ABUSEIPDB_KEY, "Accept": "application/json"}
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(ABUSE_URL, headers=headers, params={"ipAddress": ip, "maxAgeInDays": 90})
            if resp.status_code == 429:
                # rate limit → non loggare e ritorna cache/fallback
                return cached if cached is not None else 0
            resp.raise_for_status()
            data = resp.json().get("data", {})
            score = int(data.get("abuseConfidenceScore", 0))
            _cache.put(ip, score)
            return score
    except Exception:
        return cached if cached is not None else 0
