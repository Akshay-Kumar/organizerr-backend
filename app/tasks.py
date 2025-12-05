import os
import time
from app.qb_helper import list_torrents
from app.crud import find_by_info_hash, set_info_hash_and_mark_added
from sqlmodel import Session
from dotenv import load_dotenv
from pathlib import Path
from typing import Optional

load_dotenv()
QBT_POLL_RETRIES = int(os.getenv("QBT_POLL_RETRIES", "10"))
QBT_POLL_DELAY = float(os.getenv("QBT_POLL_DELAY", "1"))  # seconds


def poll_for_new_torrent_info_hash(session: Session, local_name: str, torrent_id: int) -> Optional[str]:
    """
    Poll qBittorrent for a newly-added torrent by matching the name.
    """
    name_match = Path(local_name).stem.lower()  # normalize

    for _ in range(QBT_POLL_RETRIES):
        try:
            torrents = list_torrents()
            for t in torrents:
                # Normalize qBittorrent name
                t_name = getattr(t, "name", "") or getattr(t, "display_name", "")
                t_name = Path(t_name).stem.lower()
                if t_name == name_match:
                    info_hash = getattr(t, "hash", None)
                    if info_hash:
                        set_info_hash_and_mark_added(session, torrent_id, info_hash)
                        return info_hash
        except Exception:
            pass
        time.sleep(QBT_POLL_DELAY)
    return None

