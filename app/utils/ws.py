from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
import asyncio
import time
from typing import List, Optional
from sqlmodel import Session

from app.qb_helper import list_torrents
from app.crud import get_all_torrents
from app.utils.db import engine
from app.routers.auth import verify_token

router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self.active: List[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self.active.append(websocket)

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            if websocket in self.active:
                self.active.remove(websocket)

    async def broadcast(self, message: dict):
        async with self._lock:
            conns = list(self.active)

        dead = []
        for ws in conns:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)

        for ws in dead:
            await self.disconnect(ws)

    async def has_clients(self) -> bool:
        async with self._lock:
            return len(self.active) > 0


manager = ConnectionManager()

# ---------- CONFIG ----------
POLL_INTERVAL = 10          # reduce load (try 10–15 if qB is weak)
QB_TIMEOUT = 5              # prevents hanging inside qB calls
MAX_BACKOFF = 60            # max backoff on qB errors
DB_REFRESH_EVERY = 30       # cache DB list
PING_INTERVAL = 15          # websocket keepalive
# ---------------------------

_last_snapshot: Optional[list] = None
_fail_count = 0

_poll_lock = asyncio.Lock()
_broadcaster_task: Optional[asyncio.Task] = None
_stop_event = asyncio.Event()

_cached_db_list = None
_last_db_fetch = 0.0


def _compute_backoff(fail_count: int) -> int:
    return min(MAX_BACKOFF, fail_count * 5)


async def _safe_list_torrents():
    # list_torrents is likely sync; run in a thread + timeout
    return await asyncio.wait_for(asyncio.to_thread(list_torrents), timeout=QB_TIMEOUT)


async def torrent_broadcaster():
    global _last_snapshot, _fail_count, _cached_db_list, _last_db_fetch

    next_run = time.monotonic()

    while not _stop_event.is_set():
        # Fixed interval scheduling (avoids drift)
        now = time.monotonic()
        if now < next_run:
            await asyncio.sleep(next_run - now)
        next_run += POLL_INTERVAL

        # Don’t poll at all if nobody is connected
        if not await manager.has_clients():
            _last_snapshot = None
            continue

        # Prevent overlapping polls
        if _poll_lock.locked():
            continue

        async with _poll_lock:
            try:
                # DB cached
                if (_cached_db_list is None) or (time.monotonic() - _last_db_fetch >= DB_REFRESH_EVERY):
                    with Session(engine) as session:
                        _cached_db_list = get_all_torrents(session)
                    _last_db_fetch = time.monotonic()

                db_list = _cached_db_list

                # qB poll with timeout + backoff
                try:
                    q_list = await _safe_list_torrents()
                    _fail_count = 0
                except Exception as e:
                    _fail_count += 1
                    backoff_time = _compute_backoff(_fail_count)
                    print("[WARN] qBittorrent error:", repr(e))
                    print(f"[BACKOFF] Sleeping {backoff_time}s...")
                    next_run = time.monotonic() + backoff_time
                    continue

                live_map = {getattr(t, "hash", "").lower(): t for t in q_list}

                snapshot = []
                for t in db_list:
                    info_hash = (t.info_hash or "").lower()
                    live = live_map.get(info_hash)

                    if live:
                        snapshot.append({
                            "id": t.id,
                            "hash": info_hash,
                            "name": t.correct_name or t.name,
                            "progress": int(live.progress * 100),
                            "state": live.state,
                            "dlspeed": live.dlspeed,
                            "upspeed": live.upspeed,
                            "eta": live.eta,
                            "poster": t.poster,
                        })
                    else:
                        snapshot.append({
                            "id": t.id,
                            "hash": info_hash,
                            "name": t.correct_name or t.name,
                            "progress": 0,
                            "state": "missing",
                            "dlspeed": 0,
                            "upspeed": 0,
                            "eta": None,
                            "poster": t.poster,
                        })

                snapshot.sort(key=lambda x: x["id"], reverse=True)

                if snapshot != _last_snapshot:
                    await manager.broadcast({"type": "torrents_snapshot", "torrents": snapshot})
                    _last_snapshot = snapshot

            except Exception as e:
                print("[ERROR] Broadcaster crashed:", repr(e))


@router.on_event("startup")
async def ws_start_broadcaster():
    global _broadcaster_task
    if _broadcaster_task is None or _broadcaster_task.done():
        _stop_event.clear()
        _broadcaster_task = asyncio.create_task(torrent_broadcaster())


@router.on_event("shutdown")
async def ws_stop_broadcaster():
    global _broadcaster_task
    _stop_event.set()
    if _broadcaster_task and not _broadcaster_task.done():
        _broadcaster_task.cancel()
        try:
            await _broadcaster_task
        except Exception:
            pass


@router.websocket("/ws/torrents")
async def ws_torrents(websocket: WebSocket, token: str):
    user = verify_token(token)
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect(websocket)

    try:
        while True:
            await asyncio.sleep(PING_INTERVAL)
            await websocket.send_json({"type": "ping"})
    except (WebSocketDisconnect, Exception):
        await manager.disconnect(websocket)
