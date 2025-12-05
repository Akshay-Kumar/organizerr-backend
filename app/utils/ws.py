from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
import asyncio
from typing import List
from sqlmodel import Session

from app.qb_helper import list_torrents
from app.crud import get_all_torrents
from app.utils.db import engine
from app.routers.auth import verify_token

router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self.active: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active:
            self.active.remove(websocket)

    async def broadcast(self, message: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(message)
            except:
                dead.append(ws)

        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()

# ---------- BROADCASTER CONFIG ----------
POLL_INTERVAL = 3          # qBittorrent is polled every 3 sec
MAX_BACKOFF = 30           # max 30 sec backoff on qB errors
# ----------------------------------------

last_snapshot = None
fail_count = 0


async def torrent_broadcaster():
    """
    Optimized broadcaster:
    - Polls qBittorrent every 3 sec
    - Broadcasts ONLY when data actually changes
    - Circuit breaker protects qB from overload
    - Prevents reconnect storms
    """

    global last_snapshot, fail_count

    while True:
        try:
            # ---- Load DB torrents ----
            with Session(engine) as session:
                db_list = get_all_torrents(session)

            # ---- Try loading qB live torrents ----
            try:
                q_list = list_torrents()
                fail_count = 0
            except Exception as e:
                print("[WARN] qBittorrent error:", e)
                fail_count += 1

                # Backoff to reduce qB load
                backoff_time = min(MAX_BACKOFF, fail_count * 5)
                print(f"[BACKOFF] Waiting {backoff_time}s before retrying...")
                await asyncio.sleep(backoff_time)
                continue

            live_map = {getattr(t, "hash", "").lower(): t for t in q_list}

            # ---- Build snapshot ----
            snapshot = []
            for t in db_list:
                info_hash = (t.info_hash or "").lower()
                live = live_map.get(info_hash)

                if live:
                    enriched = {
                        "id": t.id,
                        "hash": info_hash,
                        "name": t.correct_name or t.name,
                        "progress": int(live.progress * 100),
                        "state": live.state,
                        "dlspeed": live.dlspeed,
                        "upspeed": live.upspeed,
                        "eta": live.eta,
                        "poster": t.poster,
                    }
                else:
                    enriched = {
                        "id": t.id,
                        "hash": info_hash,
                        "name": t.correct_name or t.name,
                        "progress": 0,
                        "state": "missing",
                        "dlspeed": 0,
                        "upspeed": 0,
                        "eta": None,
                        "poster": t.poster,
                    }

                snapshot.append(enriched)

            # Sort descending by ID (most recent first)
            snapshot.sort(key=lambda x: x["id"], reverse=True)

            # ---- Broadcast ONLY if changed ----
            if snapshot != last_snapshot:
                print("[WS] Broadcasting update...")
                await manager.broadcast({
                    "type": "torrents_snapshot",
                    "torrents": snapshot,
                })
                last_snapshot = snapshot
            else:
                print("[WS] No changes, skipping broadcast")

        except Exception as e:
            print("[ERROR] Broadcaster crashed:", e)

        await asyncio.sleep(POLL_INTERVAL)


@router.on_event("startup")
async def ws_start_broadcaster():
    asyncio.create_task(torrent_broadcaster())


# ------------------- WEBSOCKET ENDPOINT -------------------
@router.websocket("/ws/torrents")
async def ws_torrents(websocket: WebSocket, token: str):
    user = verify_token(token)
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect(websocket)

    try:
        while True:
            # Keep alive ping every 15 sec
            await asyncio.sleep(15)
            try:
                await websocket.send_json({"type": "ping"})
            except:
                break
    except WebSocketDisconnect:
        manager.disconnect(websocket)
