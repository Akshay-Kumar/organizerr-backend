import asyncio
import hashlib
import json
import time
from typing import List, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from sqlmodel import Session
from starlette.websockets import WebSocketState
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK

from app.crud import get_all_torrents
from app.qb_helper import list_torrents
from app.routers.auth import verify_token
from app.utils.db import engine
from app.utils.logger import get_logger
from app.utils.torrent_helpers import build_display_name
from app.crud import get_file_operations_by_hash

router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self.active: List[tuple[WebSocket, dict]] = []
        self._lock = asyncio.Lock()
        self.logger = get_logger(__name__)

    async def connect(self, websocket: WebSocket, user: dict):
        user_id = user.get("user_id") if isinstance(user, dict) else user.id
        self.logger.info(f"[WS] Connected user {user_id}, total: {len(self.active)}")
        await websocket.accept()
        async with self._lock:
            self.active.append((websocket, user))

    async def disconnect(self, websocket: WebSocket):
        self.logger.info(f"[WS] Disconnected, total: {len(self.active)}")
        async with self._lock:
            self.active = [(ws, u) for ws, u in self.active if ws != websocket]

    async def broadcast(self, message: dict):
        async with self._lock:
            conns = list(self.active)

        dead = []

        for ws, user in conns:
            try:
                if ws.client_state != WebSocketState.CONNECTED:
                    dead.append(ws)
                    continue

                msg_type = message.get("type")

                # -------------------------
                # TORRENTS SNAPSHOT
                # -------------------------
                if msg_type == "torrents_snapshot":
                    user_id = user.get("user_id")
                    is_admin = user.get("is_admin", False)

                    filtered = [
                        t for t in message["torrents"]
                        if t.get("user_id") == user_id or is_admin
                    ]

                    await ws.send_json({
                        "type": "torrents_snapshot",
                        "torrents": filtered
                    })

                # -------------------------
                # FILE OPS UPDATE (NEW)
                # -------------------------
                elif msg_type == "file_ops_update":
                    op = message.get("file_operation", {})

                    user_id = user.get("user_id")
                    is_admin = user.get("is_admin", False)

                    torrent_id = op.get("torrent_id")

                    if is_admin:
                        await ws.send_json(message)


                    elif torrent_id:
                        if op.get("user_id") == user_id:
                            await ws.send_json(message)

                # -------------------------
                # DEFAULT (ping, etc.)
                # -------------------------
                else:
                    await ws.send_json(message)

            except (ConnectionClosedError, ConnectionClosedOK, RuntimeError):
                dead.append(ws)

            except Exception as e:
                self.logger.exception(f"[WS ERROR] {repr(e)}")
                dead.append(ws)

        if dead:
            async with self._lock:
                self.active = [(ws, u) for ws, u in self.active if ws not in dead]

    async def has_clients(self) -> bool:
        async with self._lock:
            return len(self.active) > 0


manager = ConnectionManager()

# ---------- CONFIG ----------
POLL_INTERVAL = 2           # reduce load (try 10–15 if qB is weak)
QB_TIMEOUT = 5              # prevents hanging inside qB calls
MAX_BACKOFF = 60            # max backoff on qB errors
DB_REFRESH_EVERY = 2        # cache DB list
PING_INTERVAL = 15          # websocket keepalive
# ---------------------------
logger = get_logger(__name__)
_last_snapshot_hash: Optional[str] = None
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

def hash_snapshot(data):
    return hashlib.md5(
        json.dumps(data, sort_keys=True, default=str).encode()
    ).hexdigest()


def normalize_snapshot(snap):
    return sorted([
        {
            "id": t.get("id"),
            "user_id": t.get("user_id"),
            "hash": t.get("hash"),
            "progress": t.get("progress"),
            "state": t.get("state"),
            "dlspeed": t.get("dlspeed"),
            "upspeed": t.get("upspeed"),
            "eta": t.get("eta"),
            "file_ops_hash": hashlib.md5(
                json.dumps(
                    t.get("fileOperations", []),
                    sort_keys=True,
                    default=str
                ).encode()
            ).hexdigest(),
        }
        for t in snap
    ], key=lambda x: x["id"] or 0)

async def torrent_broadcaster():
    global _last_snapshot_hash, _fail_count, _cached_db_list, _last_db_fetch
    next_run = time.monotonic()

    while not _stop_event.is_set():
        # ---------------------------------
        # Fixed interval scheduling
        # ---------------------------------
        now = time.monotonic()

        if now < next_run:
            await asyncio.sleep(next_run - now)

        next_run += POLL_INTERVAL

        # ---------------------------------
        # Skip polling if no clients
        # ---------------------------------
        if not await manager.has_clients():
            _last_snapshot_hash = None
            next_run = time.monotonic() + POLL_INTERVAL
            continue

        # ---------------------------------
        # Prevent overlapping polls
        # ---------------------------------
        if _poll_lock.locked():
            continue

        async with _poll_lock:
            try:
                # ---------------------------------
                # qBittorrent poll
                # ---------------------------------
                try:
                    q_list = await _safe_list_torrents()
                    _fail_count = 0

                except Exception as e:
                    _fail_count += 1
                    backoff_time = _compute_backoff(
                        _fail_count
                    )

                    logger.warning(
                        f"[WARN] qBittorrent error: "
                        f"{repr(e)}"
                    )

                    logger.info(
                        f"[BACKOFF] Sleeping "
                        f"{backoff_time}s..."
                    )

                    next_run = (
                        time.monotonic()
                        + backoff_time
                    )

                    continue

                # ---------------------------------
                # Build live torrent map
                # ---------------------------------
                live_map = {
                    getattr(t, "hash", "").lower(): t
                    for t in q_list
                }

                snapshot = []

                # ---------------------------------
                # DB session
                # ---------------------------------
                with Session(engine) as session:
                    # -----------------------------
                    # Cached torrent list
                    # -----------------------------
                    if (
                        _cached_db_list is None
                        or (
                            time.monotonic()
                            - _last_db_fetch
                            >= DB_REFRESH_EVERY
                        )
                    ):

                        _cached_db_list = (
                            get_all_torrents(session)
                        )

                        _last_db_fetch = (
                            time.monotonic()
                        )

                    db_list = _cached_db_list or []

                    # -----------------------------
                    # Build snapshot
                    # -----------------------------
                    for t in db_list:

                        info_hash = (
                            t.info_hash or ""
                        ).lower()

                        live = live_map.get(
                            info_hash
                        )

                        # -------------------------
                        # File operations
                        # -------------------------
                        ops = (
                            get_file_operations_by_hash(
                                session,
                                info_hash
                            )
                        )

                        serialized_ops = [
                            {
                                **op.dict(),

                                "timestamp":
                                    op.timestamp.isoformat()
                                    if op.timestamp
                                    else None,

                                "updated_at":
                                    op.updated_at.isoformat()
                                    if op.updated_at
                                    else None,

                                "started_at":
                                    op.started_at.isoformat()
                                    if op.started_at
                                    else None,

                                "completed_at":
                                    op.completed_at.isoformat()
                                    if op.completed_at
                                    else None,
                            }
                            for op in ops
                        ]

                        snapshot_item = {
                            "id": t.id,
                            "user_id": t.user_id,
                            "hash": info_hash,
                            "name": t.correct_name or t.name,
                            "display_name": build_display_name(t),
                            "poster": t.poster,
                            "fileOperations":   serialized_ops,
                        }

                        # -------------------------
                        # Live torrent exists
                        # -------------------------
                        if live:
                            snapshot_item.update({
                                "progress":
                                    int(
                                        live.progress
                                        * 100
                                    ),

                                "state":
                                    live.state,

                                "dlspeed":
                                    live.dlspeed,

                                "upspeed":
                                    live.upspeed,

                                "eta":
                                    live.eta,
                            })

                        # -------------------------
                        # Torrent missing
                        # -------------------------
                        else:

                            snapshot_item.update({
                                "progress": 0,
                                "state": "missing",
                                "dlspeed": 0,
                                "upspeed": 0,
                                "eta": None,
                            })

                        snapshot.append(
                            snapshot_item
                        )

                # ---------------------------------
                # Sort newest first
                # ---------------------------------
                snapshot.sort(
                    key=lambda x: x["id"],
                    reverse=True
                )

                # ---------------------------------
                # Snapshot diff detection
                # ---------------------------------
                normalized = normalize_snapshot(
                    snapshot
                )

                new_hash = hash_snapshot(
                    normalized
                )

                # ---------------------------------
                # Broadcast only if changed
                # ---------------------------------
                if new_hash != _last_snapshot_hash:

                    await manager.broadcast({
                        "type":
                            "torrents_snapshot",

                        "torrents":
                            snapshot
                    })

                    _last_snapshot_hash = (
                        new_hash
                    )

            except Exception:

                logger.exception(
                    "[ERROR] Broadcaster crashed"
                )
                await asyncio.sleep(2)


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

    await manager.connect(websocket, user)
    await websocket.send_json({
        "type": "connected"
    })

    # send initial snapshot at start
    try:
        with Session(engine) as session:
            db_list = get_all_torrents(session)
            q_list = await _safe_list_torrents()
            live_map = {
                getattr(t, "hash", "").lower(): t
                for t in q_list
            }

            snapshot = []
            user_id = user.get("user_id")
            is_admin = user.get("is_admin", False)

            for t in db_list:
                if not (t.user_id == user_id or is_admin):
                    continue

                info_hash = (t.info_hash or "").lower()
                live = live_map.get(info_hash)

                ops = get_file_operations_by_hash(
                    session,
                    info_hash
                )

                serialized_ops = [
                    {
                        **op.dict(),

                        "timestamp":
                            op.timestamp.isoformat()
                            if op.timestamp
                            else None,

                        "updated_at":
                            op.updated_at.isoformat()
                            if op.updated_at
                            else None,

                        "started_at":
                            op.started_at.isoformat()
                            if op.started_at
                            else None,

                        "completed_at":
                            op.completed_at.isoformat()
                            if op.completed_at
                            else None,
                    }
                    for op in ops
                ]

                snapshot.append({
                    "id": t.id,
                    "user_id": t.user_id,
                    "hash": info_hash,
                    "name": t.correct_name or t.name,
                    "display_name": build_display_name(t),
                    "progress": int(live.progress * 100) if live else 0,
                    "state": live.state if live else "missing",
                    "dlspeed": live.dlspeed if live else 0,
                    "upspeed": live.upspeed if live else 0,
                    "eta": live.eta if live else None,
                    "poster": t.poster,
                    "fileOperations": serialized_ops,
                })

            snapshot.sort(key=lambda x: x["id"], reverse=True)

        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.send_json({
                "type": "torrents_snapshot",
                "torrents": snapshot
            })

    except Exception as e:
        logger.warning(f"[WS INIT SNAPSHOT ERROR] {repr(e)}")

    try:
        while True:
            await asyncio.sleep(PING_INTERVAL)
            if websocket.client_state != WebSocketState.CONNECTED:
                break

            await websocket.send_json({"type": "ping"})
    except (WebSocketDisconnect, Exception):
        await manager.disconnect(websocket)
