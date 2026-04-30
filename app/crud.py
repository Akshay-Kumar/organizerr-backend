from sqlmodel import Session, select, desc
from app.models import Torrent, FileOperation, User
from typing import Optional
from datetime import datetime


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


def list_torrents(session: Session, current_user: User, limit: int = 100):
    if not current_user.is_active:
        return []  # or raise error

    if current_user.is_admin:
        statement = select(Torrent)
    else:
        statement = select(Torrent).where(Torrent.user_id == current_user.id)

    statement = statement.order_by(desc(Torrent.created_at)).limit(limit)

    return session.exec(statement).all()


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
    # ✅ ensure timestamp always exists
    if not data.get("timestamp"):
        data["timestamp"] = datetime.utcnow()

    existing = session.exec(
        select(FileOperation).where(FileOperation.info_hash == data["info_hash"])
    ).first()

    if existing:
        for k, v in data.items():
            if hasattr(existing, k) and v is not None:
                setattr(existing, k, v)

        existing.timestamp = data["timestamp"]  # ✅ use provided or fallback
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    obj = FileOperation(**data)
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


def get_file_operation_by_hash(session: Session, info_hash: str):
    return session.exec(
        select(FileOperation).where(FileOperation.info_hash == info_hash)
    ).first()


def list_file_operations(session: Session):
    return session.exec(
        select(FileOperation).order_by(desc(FileOperation.timestamp))
    ).all()