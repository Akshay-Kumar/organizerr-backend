from sqlmodel import Session, select, desc
from app.models import (
    Torrent,
    FileOperation,
    ProcessingReport,
    User
)
from sqlalchemy import func
from sqlalchemy import or_
from typing import Optional
from datetime import datetime
import json
from app.utils.logger import get_logger

logger = get_logger(__name__)

# file-operation stage order
STAGE_ORDER = {
    "media_info": 1,
    "metadata": 2,
    "copy": 3,
    "artwork": 4,
    "subtitles": 5,
    "validation": 6,
    "plex": 7,
    "emby": 8,
    "library_scan": 9,
}

def create_torrent(
        session: Session,
        current_user: User,
        **data
) -> Torrent:
    # Normalize tags and custom_metadata for DB storage
    tags = data.pop("tags", None)
    custom = data.pop("custom_metadata", None)

    t = Torrent(**data)
    t.user_id = current_user.id # ✅ attach owner
    if tags is not None:
        t.set_tags_list(tags)
    if custom is not None:
        try:
            t.set_custom_metadata(custom)
        except Exception:
            t.custom_metadata = None

    session.add(t)
    session.commit()
    session.refresh(t)
    return t


def get_torrent(session: Session, torrent_id: int) -> Optional[Torrent]:
    return session.get(Torrent, torrent_id)


def find_by_info_hash(session: Session, info_hash: str) -> Optional[Torrent]:
    statement = select(Torrent).where(Torrent.info_hash == info_hash)
    res = session.exec(statement).first()
    return res

def list_torrents(
    session: Session,
    current_user: User,
    page: int = 1,
    page_size: int = 25,
    search: str = None
):
    if not current_user.is_active:
        return [], 0

    if current_user.is_admin:
        statement = select(Torrent)
    else:
        statement = select(Torrent).where(
            Torrent.user_id == current_user.id
        )

    #
    # SEARCH
    #
    if search:
        search = f"%{search}%"
        statement = statement.where(
            or_(
                Torrent.name.ilike(search),
                Torrent.correct_name.ilike(search),
                Torrent.episode_title.ilike(search),
                Torrent.info_hash.ilike(search)
            )
        )

    #
    # TOTAL COUNT
    #
    total = session.exec(
        select(func.count())
        .select_from(statement.subquery())
    ).one()

    #
    # PAGINATION
    #
    offset = (page - 1) * page_size
    items = session.exec(
        statement
        .order_by(desc(Torrent.created_at))
        .offset(offset)
        .limit(page_size)
    ).all()

    return items, total


def get_all_torrents(session: Session):
    """
    Return all torrents in DB (no limit).
    Used by WebSocket to map info_hash -> db_id.
    """
    # statement = select(Torrent)
    # return session.exec(statement).all()
    statement = select(Torrent)
    return session.exec(
        statement.order_by(desc(Torrent.created_at)).limit(100)
    ).all()


def update_torrent(session: Session, torrent_id: int, **patch) -> Optional[Torrent]:
    t = session.get(Torrent, torrent_id)
    if not t:
        return None
    for k, v in patch.items():
        if v is None:
            continue
        if k == "tags":
            t.set_tags_list(v)
            continue
        if k == "custom_metadata":
            try:
                t.set_custom_metadata(v)
            except Exception:
                pass
            continue
        if hasattr(t, k):
            setattr(t, k, v)
    t.updated_at = datetime.utcnow()
    session.add(t)
    session.commit()
    session.refresh(t)
    return t


def set_info_hash_and_mark_added(session: Session, torrent_id: int, info_hash: str):
    t = session.get(Torrent, torrent_id)
    if not t:
        return None
    t.info_hash = info_hash
    t.qb_added = True
    t.updated_at = datetime.utcnow()
    session.add(t)
    session.commit()
    session.refresh(t)
    return t


def set_qb_error(session: Session, torrent_id: int, error: str):
    t = session.get(Torrent, torrent_id)
    if not t:
        return None
    t.qb_error = error
    t.qb_added = False
    t.updated_at = datetime.utcnow()
    session.add(t)
    session.commit()
    session.refresh(t)
    return t


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
        if incoming_status in ["completed", "failed"]:
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


def create_processing_report(
    session: Session,
    data: dict
) -> ProcessingReport:

    torrent = None

    if data.get("info_hash"):
        torrent = find_by_info_hash(
            session,
            data["info_hash"]
        )

    report = ProcessingReport(
        torrent_id=torrent.id if torrent else None,
        info_hash=data.get("info_hash"),
        file_hash=data.get("file_hash"),
        media_type=data.get("media_type"),
        source_path=data.get("source_path"),
        destination_path=data.get("destination_path"),
        success=data.get("success", False),
        processing_time=data.get("processing_time"),
        report_json=json.dumps(
            data.get("report", {}),
            default=str
        )
    )

    session.add(report)
    session.commit()
    session.refresh(report)

    return report


def get_processing_reports(
    session: Session,
    info_hash: str
):
    return session.exec(
        select(ProcessingReport)
        .where(
            ProcessingReport.info_hash == info_hash
        )
        .order_by(
            desc(ProcessingReport.created_at)
        )
    ).all()


def get_processing_report(
    session: Session,
    report_id: int
):
    return session.get(
        ProcessingReport,
        report_id
    )