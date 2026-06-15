# app/api/torrents.py
from datetime import datetime
from typing import List
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import select
from sqlmodel import Session

from app.crud import (
    get_torrent,
    upsert_file_operation,
    list_file_operations,
    get_file_operations_by_hash,
    create_processing_report
)
from app.models import User
from app.models import FileOperation
from app.qb_helper import get_qb
from app.routers.auth import verify_token
from app.schemas import (
    TorrentUpdate,
    TorrentOut,
    FileOperationCreate,
    FileOperationOut,
    ProcessingReportCreate,
    ProcessingReportOut
)
from app.utils.db import get_session
from app.utils.logger import get_logger
from app.utils.ws import manager

logger = get_logger(__name__)
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


# -----------------------------
# Datetime normalization
# -----------------------------
def serialize_datetimes(data: dict):
    result = {}
    for k, v in data.items():
        if isinstance(v, datetime):
            result[k] = v.isoformat()
        else:
            result[k] = v
    return result

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

@router.get("/torrents/{id}", response_model=TorrentOut)
def get_single_torrent(
    id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    torrent = get_torrent(session, id)

    if not torrent:
        raise HTTPException(status_code=404, detail="Torrent not found")

    return torrent

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

    serialized_op = {}
    serialized_op = serialize_datetimes(op)
    serialized_op["filename"] = Path(
        serialized_op.get("source") or ""
    ).name

    await manager.broadcast({
        "type": "file_ops_update",
        "file_operation": serialized_op
    })

    if data.get("status") == "failed":
        logger.warning(
            f"File operation failed: {data}"
        )

    elif data.get("status") == "skipped":
        logger.info(
            f"File operation skipped: "
            f"{data.get('source')}"
        )

    return response


@router.post(
    "/processing-reports",
    response_model=ProcessingReportOut
)
def create_report(
    payload: ProcessingReportCreate,
    session: Session = Depends(get_session),
):
    data = payload.dict()

    response = create_processing_report(
        session,
        data
    )

    # AUTO-HEAL STUCK STAGES
    if data.get("success"):
        stale_ops = session.exec(
            select(FileOperation).where(
                FileOperation.info_hash == data["info_hash"],
                FileOperation.file_hash == data["file_hash"],
                FileOperation.status == "processing"
                #FileOperation.status.notin_(["completed", "failed"])
            )
        ).all()

        for op in stale_ops:
            op.status = "completed"
            op.progress = 100
            op.success = True

            if not op.completed_at:
                op.completed_at = datetime.utcnow()

            if op.started_at:
                op.duration_seconds = round(
                    (op.completed_at - op.started_at).total_seconds(),
                    2
                )
            session.add(op)

        session.commit()

    logger.info(
        f"Processing report stored: "
        f"{data.get('info_hash')}"
    )

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