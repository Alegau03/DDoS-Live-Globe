from pydantic import BaseModel

class Endpoint(BaseModel):
    country: str
    lat: float
    lon: float
    asn: int | None = None
    ip: str | None = None
    service: str | None = None

class EventOut(BaseModel):
    ts: int
    src: Endpoint
    dst: Endpoint
    vector: str
    pps: int
    bps: float
    score: float
