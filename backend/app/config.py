# backend/app/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Sorgenti dati
    USE_MOCK_INGEST: bool = False
    USE_RADAR_INGEST: bool = False

    # Cloudflare per-zona (serve un dominio; puoi lasciarli vuoti)
    CLOUDFLARE_API_TOKEN: str = ""
    CLOUDFLARE_ZONE_TAG: str = ""

    # Cloudflare Radar (senza dominio)
    RADAR_API_TOKEN: str = ""

    # AbuseIPDB (opzionale)
    ABUSEIPDB_KEY: str = ""
    ABUSEIPDB_TTL_SEC: int = 3600

    # Privacy (per hash IP a riposo)
    HASH_IP_SALT: str = ""

    # Pydantic Settings config: carica .env
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # ignora variabili extra nel .env
    )

settings = Settings()
