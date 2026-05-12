from sqlmodel import Session, select, desc
from app.models import Torrent, FileOperation, User
from typing import Optional
from datetime import datetime
from app.utils.logger import get_logger

logger = get_logger(__name__)

# file-operation stage priorities
STAGE_PRIORITY = {
    "media_info": 1,
    "metadata": 2,
    "copy": 3,
    "artwork": 4,
    "subtitles": 5,
    "validation": 6,
    "plex": 7,
    "emby": 8,
    "library_scan": 9,
    "completed": 999,
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
            page_size: int = 25
    ):
    if not current_user.is_active:
        return [], 0

    if current_user.is_admin:
        statement = select(Torrent)
        count_statement = select(Torrent)
    else:
        statement = select(Torrent).where(
            Torrent.user_id == current_user.id
        )

        count_statement = select(Torrent).where(
            Torrent.user_id == current_user.id
        )

    total = len(session.exec(count_statement).all())

    offset = (page - 1) * page_size

    statement = (
        statement
        .order_by(desc(Torrent.created_at))
        .offset(offset)
        .limit(page_size)
    )

    items = session.exec(statement).all()

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


def upsert_file_operation(session: Session, data: dict) -> FileOperation:
    if not data.get("timestamp"):
        data["timestamp"] = datetime.utcnow()

    # ✅ ALWAYS resolve torrent_id
    if data.get("info_hash"):
        torrent = find_by_info_hash(session, data["info_hash"])
        if torrent:
            data["torrent_id"] = torrent.id

    file_hash = data.get("file_hash")
    if file_hash:
        existing = get_file_operation_by_info_and_file_hash(
            session,
            data["info_hash"],
            file_hash
        )
    else:
        existing = None

    if existing:
        incoming_stage = data.get("stage")
        stage_changed = (
                incoming_stage
                and incoming_stage != existing.stage
        )

        for k, v in data.items():
            if not hasattr(existing, k):
                continue

            if v is None:
                continue

            # -----------------------------------
            # Stage changed
            # -----------------------------------
            if stage_changed:
                setattr(existing, k, v)
                continue

            # -----------------------------------
            # Same stage logic
            # -----------------------------------
            if k == "progress":
                existing.progress = v
            elif k == "status":
                existing.status = v
            else:
                setattr(existing, k, v)

        existing.updated_at = datetime.utcnow()
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    obj = FileOperation(**data)
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


def get_file_operations_by_hash(session: Session, info_hash: str):
    return session.exec(
        select(FileOperation).where(
            FileOperation.info_hash == info_hash).order_by(desc(FileOperation.timestamp))
    ).all()

def get_file_operation_by_info_and_file_hash(
    session: Session,
    info_hash: str,
    file_hash: str
):
    return session.exec(
        select(FileOperation).where(
            (FileOperation.info_hash == info_hash) &
            (FileOperation.file_hash == file_hash)
        )
    ).first()

def list_file_operations(session):
    return session.exec(
        select(FileOperation)
        .order_by(desc(FileOperation.timestamp))
    ).all()