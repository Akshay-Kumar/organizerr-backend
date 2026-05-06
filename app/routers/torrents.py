# app/api/torrents.py
from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session
from typing import List

from app.models import Torrent, User
from app.schemas import TorrentUpdate, TorrentOut
from app.utils.db import get_session
from app.routers.auth import verify_token
from app.qb_helper import get_qb  # qBittorrent helper
from app.crud import get_torrent, get_file_operation_by_info_and_file_hash
import json
import os
import logging
from pathlib import Path
from app.schemas import TorrentUpdate, TorrentOut, FileOperationCreate, FileOperationUpdate, FileOperationOut
from app.crud import upsert_file_operation, list_file_operations, get_file_operations_by_hash
from app.utils.ws import manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["torrents"])

# -----------------------------
# Auth / Current user dependency
# -----------------------------
def get_current_user(
    token: dict = Depends(verify_token),
    session: Session = Depends(get_session),
) -> User:
    if not token or "user_id" not in token:
        raise HTTPException(status_code=401, detail="Invalid or missing token")
    user = session.get(User, token["user_id"])
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


@router.patch("/torrents/{id}", response_model=TorrentOut)
def update_torrent(
    id: int,
    t_in: TorrentUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    t = get_torrent(session, id)
    if not t:
        raise HTTPException(status_code=404, detail="Torrent not found")

    for field, value in t_in.dict(exclude_unset=True).items():
        if field == "tags" and value is not None:
            t.set_tags_list(value)
        elif field == "custom_metadata" and value is not None:
            t.set_custom_metadata(value)
        else:
            setattr(t, field, value)

    session.add(t)
    session.commit()
    session.refresh(t)
    return t


# -----------------------------
# Stop / Resume / Delete
# -----------------------------
@router.post("/torrents/{id}/stop")
def stop_torrent(
    id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    t = get_torrent(session, id)
    if not t or not t.info_hash:
        raise HTTPException(status_code=404, detail="Torrent not found")

    qb = get_qb()
    info_hash = (t.info_hash or "").strip().lower()

    try:
        qb.torrents.pause(info_hash)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"qBittorrent error: {e}")

    return {"ok": True}


@router.post("/torrents/{id}/resume")
def resume_torrent(
    id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    t = get_torrent(session, id)
    if not t or not t.info_hash:
        raise HTTPException(status_code=404, detail="Torrent not found")

    qb = get_qb()
    info_hash = (t.info_hash or "").strip().lower()

    try:
        qb.torrents.resume(info_hash)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"qBittorrent error: {e}")

    return {"ok": True}


@router.delete("/torrents/{id}")
def delete_torrent(
    id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    t = get_torrent(session, id)
    if not t or not t.info_hash:
        raise HTTPException(status_code=404, detail="Torrent not found")

    qb = get_qb()
    info_hash = (t.info_hash or "").strip().lower()

    try:
        qb.torrents.delete(info_hash, delete_files=True)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"qBittorrent error: {e}")

    session.delete(t)
    session.commit()
    return {"ok": True}

@router.post("/file-operations", response_model=FileOperationOut)
async def create_or_update_file_operation(
    payload: FileOperationCreate,
    session: Session = Depends(get_session),
):
    data = payload.dict(exclude_unset=True)

    if not data.get("info_hash"):
        raise HTTPException(status_code=400, detail="info_hash is required")

    if not data.get("file_hash"):
        raise HTTPException(status_code=400, detail="file_hash is required")

    data["info_hash"] = data["info_hash"].strip().lower()
    data["file_hash"] = data["file_hash"].strip().lower()

    response = upsert_file_operation(session, data)
    logger.debug(f"File operation received: {data.get('info_hash')} -> {data.get('destination')}")

    op = response.dict()

    # 🔥 ENSURE torrent_id exists
    if not data.get("torrent_id"):
        logger.warning("Missing torrent_id in file operation")

    await manager.broadcast({
        "type": "file_ops_update",
        "file_operation": {
            **op,
            "filename": (op.get("source") or "").split("/")[-1]
        }
    })

    # 🔥 SEND SNAPSHOT (OPTIONAL BUT POWERFUL)
    ops = list_file_operations(session)

    await manager.broadcast({
        "type": "file_ops_snapshot",
        "file_operations": [op.dict() for op in ops]
    })

    if data.get("status") == "failed":
        logger.warning(f"File operation failed: {data}")

    return response


@router.get("/file-operations", response_model=List[FileOperationOut])
def get_all_operations(
    session: Session = Depends(get_session),
):
    return list_file_operations(session)


@router.get("/file-operations/{info_hash}", response_model=List[FileOperationOut])
def get_operations_by_hash(
    info_hash: str,
    session: Session = Depends(get_session),
):
    op = get_file_operations_by_hash(session, info_hash)

    if not op:
        raise HTTPException(status_code=404, detail="Not found")

    return op