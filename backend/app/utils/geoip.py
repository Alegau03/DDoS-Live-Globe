import random

# Centroidi country di base (sufficienti per demo senza DB esterni)
COUNTRY_CENTROIDS = {
    "US": (38.0, -97.0), "CN": (36.0, 104.0), "IT": (41.9, 12.5),
    "DE": (51.0, 10.0), "BR": (-14.0, -52.0), "GB": (54.0, -2.0),
    "FR": (46.0, 2.0), "JP": (36.0, 138.0), "RU": (61.5, 105.3),
    "IN": (22.0, 79.0), "NL": (52.1, 5.3), "ES": (40.4, -3.7)
}

def country_to_latlon(cc: str) -> tuple[float, float]:
    lat, lon = COUNTRY_CENTROIDS.get(cc, (0.0, 0.0))
    return (lat + random.uniform(-2, 2), lon + random.uniform(-2, 2))
