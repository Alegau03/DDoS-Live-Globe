# app/main.py
import asyncio
import time
import os
import sqlite3
from typing import Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .ingest.enrich import stream_enriched
from .ml.model import get_scorer
from .schemas import EventOut, Endpoint
from .storage import init_db, insert_event, DB_PATH
from .ingest import radar_api  # per /api/source e chiusura httpx.Client

# ------------------------- App & CORS -------------------------

app = FastAPI(title="DDoS Live Backend", version="0.5.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------- Stato & code -------------------------

clients: Set[WebSocket] = set()
broadcast_queue: asyncio.Queue[str] = asyncio.Queue()
_stats = {"events": 0, "bytes": 0.0, "start": time.time()}

PERSIST_Q: asyncio.Queue | None = None
DB_WRITER_TASK: asyncio.Task | None = None
PRODUCER_TASK: asyncio.Task | None = None
BROADCASTER_TASK: asyncio.Task | None = None


# ------------------------- Writer asincrono su SQLite -------------------------

async def db_writer():
    """Consuma (ev, score) da PERSIST_Q ed esegue insert su SQLite in threadpool."""
    assert PERSIST_Q is not None, "PERSIST_Q non inizializzata"
    loop = asyncio.get_running_loop()
    while True:
        ev, score = await PERSIST_Q.get()
        try:
            await loop.run_in_executor(None, insert_event, ev, score)
        except Exception as e:
            # Log minimale: non vogliamo mai bloccare il loop su errori sqlite
            print(f"[DB] insert_err: {e}")
        finally:
            PERSIST_Q.task_done()


# ------------------------- API -------------------------

@app.get("/api/health")
def health():
    uptime = time.time() - _stats["start"]
    return {
        "status": "ok",
        "events": _stats["events"],
        "uptime_sec": int(uptime),
        "clients": len(clients),
    }


@app.get("/api/source")
def source():
    mode = getattr(radar_api, "LAST_MODE", "unknown")
    return {"mode": mode}


@app.get("/api/db/stats")
def db_stats():
    rows = 0
    if os.path.exists(DB_PATH):
        with sqlite3.connect(DB_PATH, timeout=5) as con:
            rows = con.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    return {"db_path": DB_PATH, "rows": int(rows)}


# ------------------------- WebSocket -------------------------

@app.websocket("/ws/events")
async def ws_events(ws: WebSocket):
    await ws.accept()
    clients.add(ws)
    try:
        # Mantieni viva la connessione; non riceviamo nulla dal client
        while True:
            await asyncio.sleep(3600)
    except WebSocketDisconnect:
        pass
    finally:
        clients.discard(ws)


# ------------------------- Broadcaster -------------------------

async def broadcaster():
    """Legge messaggi JSON da broadcast_queue e li invia a tutti i WS."""
    while True:
        msg = await broadcast_queue.get()
        dead = set()
        for c in clients:
            try:
                await c.send_text(msg)
            except Exception:
                dead.add(c)
        for d in dead:
            clients.discard(d)


# ------------------------- Producer -------------------------

async def producer():
    """Legge eventi dalla sorgente (enrich), calcola score, persiste e broadcasta."""
    scorer = get_scorer()

    async def put(ev: dict):
        # punteggio
        score = scorer.score_event(ev)

        # metriche
        _stats["events"] += 1
        _stats["bytes"] += ev.get("bytes", 0.0)

        # persist (GDPR-safe: IP non presenti con Radar; quando presenti, hashati nello storage)
        assert PERSIST_Q is not None
        await PERSIST_Q.put((ev, score))

        # costruisci EventOut per il FE
        bps = float(ev.get("bps")) if ev.get("bps") is not None else float(ev.get("bytes", 0.0)) * 8.0
        out = EventOut(
            ts=ev["ts"],
            src=Endpoint(
                country=ev["src_country"],
                lat=ev["src_lat"], lon=ev["src_lon"],
                asn=ev.get("src_asn"),
            ),
            dst=Endpoint(
                country=ev["dst_country"],
                lat=ev["dst_lat"], lon=ev["dst_lon"],
                asn=ev.get("dst_asn"),
            ),
            vector=ev["vector"],
            pps=int(ev.get("pps", 0)),
            bps=bps,
            score=float(score),
        )
        await broadcast_queue.put(out.model_dump_json())

    # Esegui lo stream di eventi in un thread dedicato e rientra nel loop con call_soon_threadsafe
    loop = asyncio.get_running_loop()

    def gen():
        for e in stream_enriched():
            loop.call_soon_threadsafe(asyncio.create_task, put(e))
            time.sleep(0)  # cedi il time-slice, non necessario ma innocuo

    await asyncio.to_thread(gen)


# ------------------------- Lifecycle -------------------------

@app.on_event("startup")
async def on_start():
    global PERSIST_Q, DB_WRITER_TASK, PRODUCER_TASK, BROADCASTER_TASK

    # DB pronto (crea cartella/data + WAL)
    init_db()

    # code & task
    PERSIST_Q = asyncio.Queue(maxsize=10_000)
    DB_WRITER_TASK = asyncio.create_task(db_writer())

    # Warm-up modello (carica il model.pkl o sintetico)
    get_scorer()

    # avvia broadcaster e producer
    BROADCASTER_TASK = asyncio.create_task(broadcaster())
    PRODUCER_TASK = asyncio.create_task(producer())


@app.on_event("shutdown")
async def on_stop():
    # cancella task in ordine: producer → broadcaster → writer
    for t in (PRODUCER_TASK, BROADCASTER_TASK, DB_WRITER_TASK):
        if t:
            t.cancel()
            try:
                await t
            except Exception:
                pass
    # chiudi client HTTP Radar (evita fd leak)
    try:
        radar_api.CLIENT.close()
    except Exception:
        pass
