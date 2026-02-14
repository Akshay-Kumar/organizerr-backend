# app/api/torrents.py
from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session
from typing import List

from app.models import Torrent, User
from app.schemas import TorrentUpdate, TorrentOut
from app.utils.db import get_session
from app.routers.auth import verify_token
from app.qb_helper import get_qb  # qBittorrent helper
from app.crud import get_torrent

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
