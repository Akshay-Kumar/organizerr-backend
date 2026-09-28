from sqlmodel import Session, select, desc
from app.models import (
    Torrent,
    User
)
from sqlalchemy import func
from sqlalchemy import or_
from typing import Optional
from datetime import datetime
from app.utils.logger import get_logger

logger = get_logger(__name__)

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