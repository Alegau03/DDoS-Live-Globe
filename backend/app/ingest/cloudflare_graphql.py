# app/ingest/cloudflare_graphql.py
import time, datetime, httpx
from typing import Iterator, Set, Tuple
from ..config import settings

GRAPHQL_ENDPOINT = "https://api.cloudflare.com/client/v4/graphql"

QUERY = """
query ListFirewallEvents($zoneTag: String!, $filter: FirewallEventsAdaptiveFilter_InputObject) {
  viewer {
    zones(filter: { zoneTag: $zoneTag }) {
      firewallEventsAdaptive(
        filter: $filter
        limit: 100
        orderBy: [datetime_DESC]
      ) {
        action
        clientAsn
        clientCountryName
        clientIP
        datetime
        source
      }
    }
  }
}
"""

def map_country_name_to_cc(name: str) -> str:
    m = {
        "United States":"US","China":"CN","Italy":"IT","Germany":"DE","Brazil":"BR",
        "United Kingdom":"GB","France":"FR","Japan":"JP","India":"IN","Russia":"RU",
        "Netherlands":"NL","Spain":"ES","Canada":"CA","Australia":"AU","Turkey":"TR"
    }
    return m.get(name, "US")

def source_to_vector(src: str) -> str:
    s = (src or "").lower()
    if "waf" in s or "http" in s or "l7" in s: return "HTTP2"
    if "ratelimit" in s: return "HTTP"
    return "SYN"  # fallback

def poll_firewall_events(zone_tag: str, api_token: str, window_sec: int = 60, poll_every: float = 3.0) -> Iterator[dict]:
    """
    Poll “ultimi N secondi” con dedup (clientIP, datetime, action).
    Nota: Firewall Events è a livello HTTP/L7, quindi stimiamo PPS/BPS a valle.
    """
    seen: Set[Tuple[str,str,str]] = set()
    headers = {"Authorization": f"Bearer {api_token}", "Accept":"application/json", "Content-Type":"application/json"}
    with httpx.Client(timeout=20.0) as client:
        while True:
            now = datetime.datetime.utcnow()
            start = now - datetime.timedelta(seconds=window_sec)
            variables = {
                "zoneTag": zone_tag,
                "filter": {
                    "datetime_geq": start.replace(microsecond=0).isoformat()+"Z",
                    "datetime_leq": now.replace(microsecond=0).isoformat()+"Z"
                }
            }
            try:
                resp = client.post(GRAPHQL_ENDPOINT, json={"query": QUERY, "variables": variables}, headers=headers)
                resp.raise_for_status()
                zones = resp.json().get("data", {}).get("viewer", {}).get("zones", [])
                events = zones[0]["firewallEventsAdaptive"] if zones else []
                for e in reversed(events):  # dal più vecchio al più nuovo
                    cip = e.get("clientIP")
                    dt = e.get("datetime")
                    act = e.get("action") or "allow"
                    if not cip or not dt:
                        continue
                    key = (cip, dt, act)
                    if key in seen:
                        continue
                    seen.add(key)

                    country_name = e.get("clientCountryName") or "United States"
                    cc = map_country_name_to_cc(country_name)
                    asn = int(e.get("clientAsn")) if e.get("clientAsn") is not None else None
                    vector = source_to_vector(e.get("source") or "")

                    # Valori di base (pps/bps stimati dopo via RateEstimator)
                    yield {
                        "ts": int(datetime.datetime.fromisoformat(dt.replace("Z","+00:00")).timestamp()),
                        "src_ip": cip,
                        "dst_ip": "0.0.0.0",
                        "bytes": 1500.0,  # placeholder: ~frame medio; verrà scalato dopo
                        "pps": 1,
                        "cf_action": act,
                        "vector": vector,
                        "client_country": cc,
                        "client_asn": asn
                    }
            except Exception:
                # non bloccare lo stream; riprova al prossimo poll
                pass
            time.sleep(poll_every)
