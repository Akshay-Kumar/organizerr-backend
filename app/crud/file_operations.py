from datetime import datetime
from sqlmodel import Session, select
from app.crud import find_by_info_hash
from app.models import (
    FileOperation
)
from app.utils.logger import get_logger

logger = get_logger(__name__)

def upsert_file_operation(
    session: Session,
    data: dict
) -> FileOperation:

    if not data.get("timestamp"):
        data["timestamp"] = datetime.utcnow()

    # resolve torrent_id
    if data.get("info_hash"):
        torrent = find_by_info_hash(
            session,
            data["info_hash"]
        )

        if torrent:
            data["torrent_id"] = torrent.id
            data["user_id"] = torrent.user_id

    file_hash = data.get("file_hash")
    stage = data.get("stage")

    logger.info(
        f"UPSERT: "
        f"file_hash={file_hash}, "
        f"stage={stage}, "
        f"status={data.get('status')}"
    )

    if stage and not data.get("operation"):
        data["operation"] = stage

    existing = None

    if file_hash and stage:
        existing = get_file_operation_by_stage(
            session,
            data["info_hash"],
            file_hash,
            stage
        )

    # -----------------------------------
    # UPDATE EXISTING STAGE ROW
    # -----------------------------------

    if existing:
        incoming_status = data.get("status")

        # -----------------------------------
        # Stage start
        # -----------------------------------
        if incoming_status == "processing":
            if not existing.started_at:
                existing.started_at = datetime.utcnow()

            existing.completed_at = None
            existing.duration_seconds = None

        # -----------------------------------
        # Stage completed / failed
        # -----------------------------------
        if incoming_status in ["completed", "failed", "skipped"]:
            existing.completed_at = datetime.utcnow()

            if existing.started_at:
                existing.duration_seconds = round(
                    (
                            existing.completed_at
                            - existing.started_at
                    ).total_seconds(),
                    2
                )

        # -----------------------------------
        # Update live state
        # -----------------------------------
        for k, v in data.items():
            if not hasattr(existing, k):
                continue

            if v is None:
                continue

            # prevent progress regression
            if k == "progress":
                existing.progress = v
                continue

            setattr(existing, k, v)

        existing.updated_at = datetime.utcnow()
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    # -----------------------------------
    # CREATE NEW STAGE ROW
    # -----------------------------------
    # initialize stage timing
    if data.get("status") == "processing":
        data["started_at"] = datetime.utcnow()
    obj = FileOperation(**data)
    session.add(obj)
    session.commit()
    session.refresh(obj)

    return obj


def get_file_operations_by_hash(session: Session, info_hash: str):
    return session.exec(
        select(FileOperation).where(
            FileOperation.info_hash == info_hash).order_by(
                FileOperation.file_hash,
                FileOperation.timestamp
            )
    ).all()

def get_file_operation_by_stage(
    session: Session,
    info_hash: str,
    file_hash: str,
    stage: str
):
    return session.exec(
        select(FileOperation).where(
            (FileOperation.info_hash == info_hash) &
            (FileOperation.file_hash == file_hash) &
            (FileOperation.stage == stage)
        )
    ).first()

def list_file_operations(session):
    return session.exec(
        select(FileOperation)
        .order_by(
            FileOperation.file_hash,
            FileOperation.timestamp
        )
    ).all()


def delete_file_operations(
        session,
        info_hash,
        file_hash
):
    ops = session.exec(
        select(FileOperation)
        .where(
            FileOperation.info_hash == info_hash,
            FileOperation.file_hash == file_hash
        )
    ).all()

    for op in ops:
        session.delete(op)

    session.commit()


def get_file_operation(
        session,
        info_hash,
        file_hash
):
    return session.exec(
        select(FileOperation)
        .where(
            FileOperation.info_hash == info_hash,
            FileOperation.file_hash == file_hash
        )
    ).all()