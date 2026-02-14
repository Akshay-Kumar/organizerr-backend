import os
import time
import threading
from typing import Optional, List

from qbittorrentapi import Client
from qbittorrentapi.exceptions import LoginFailed, APIConnectionError
from dotenv import load_dotenv

load_dotenv()

QBT_HOST = os.getenv("QBT_HOST", "http://127.0.0.1:8080")
QBT_USER = os.getenv("QBT_USER", "admin")
QBT_PASS = os.getenv("QBT_PASS", "adminadmin")

# Network safety defaults
QBT_TIMEOUT = float(os.getenv("QBT_TIMEOUT", "5"))          # seconds
QBT_VERIFY_SSL = os.getenv("QBT_VERIFY_SSL", "true").lower() == "true"

# Singleton client + lock
_qb_client: Optional[Client] = None
_qb_lock = threading.Lock()


def _build_client() -> Client:
    """
    Create a qBittorrent client with request timeouts.
    qbittorrentapi uses requests under the hood; REQUESTS_ARGS are forwarded.
    """
    qb = Client(
        host=QBT_HOST,
        username=QBT_USER,
        password=QBT_PASS,
        VERIFY_WEBUI_CERTIFICATE=QBT_VERIFY_SSL,
        REQUESTS_ARGS={"timeout": QBT_TIMEOUT},
    )
    return qb


def get_qb_client(force_relogin: bool = False) -> Client:
    """
    Returns a shared, logged-in qBittorrent client.

    Why: your old code created a new client + login on every call (every poll),
    which can hang qBittorrent under load.

    Thread-safe.
    """
    global _qb_client

    with _qb_lock:
        if _qb_client is None:
            _qb_client = _build_client()

        if force_relogin:
            try:
                _qb_client.auth_log_out()
            except Exception:
                pass

        try:
            if not _qb_client.is_logged_in:
                _qb_client.auth_log_in()
        except (LoginFailed, APIConnectionError):
            # Rebuild client on hard failures
            _qb_client = _build_client()
            _qb_client.auth_log_in()

        return _qb_client


def get_qb() -> Client:
    """Compatibility wrapper used by routes."""
    return get_qb_client()


def add_torrent(
    info_hash: str,
    magnet_or_file: str,
    save_path: Optional[str] = None,
    tags: Optional[List[str]] = None,
    category: Optional[str] = None,
) -> Optional[str]:
    """
    Add a magnet link or .torrent file to qBittorrent and return its info-hash (best effort).
    """
    qb = get_qb_client()
    tags_str = ",".join(tags) if tags else None

    if magnet_or_file.startswith("magnet:"):
        qb.torrents_add(urls=magnet_or_file, save_path=save_path, tags=tags_str, category=category)
        try:
            return magnet_or_file.split("btih:")[1].split("&")[0].lower()
        except IndexError:
            return None

    # Add .torrent file
    with open(magnet_or_file, "rb") as fh:
        qb.torrents_add(torrent_files=fh, save_path=save_path, tags=tags_str, category=category)

    # If we already know the info_hash, avoid fetching ALL torrents repeatedly.
    info_hash = (info_hash or "").lower()
    if not info_hash:
        return None

    for _ in range(10):
        t = find_torrent_by_hash(info_hash)
        if t is not None:
            return getattr(t, "hash", None)
        time.sleep(0.5)

    return None


def list_torrents():
    """Lightweight list call using the shared session (no repeated logins)."""
    qb = get_qb_client()
    return qb.torrents_info()


def find_torrent_by_hash(info_hash: str):
    """
    Much lighter than fetching all torrents then scanning.
    qB API supports filtering by torrent_hashes.
    """
    qb = get_qb_client()
    info_hash = (info_hash or "").lower()
    if not info_hash:
        return None

    try:
        result = qb.torrents_info(torrent_hashes=info_hash)
        return result[0] if result else None
    except Exception:
        return None


def set_torrent_tags(info_hash: str, tags: List[str]):
    qb = get_qb_client()
    info_hash = (info_hash or "").lower()
    if not info_hash:
        return

    tags_str = ",".join(tags) if tags else ""

    if tags:
        for tag in tags:
            try:
                qb.torrents_create_tag(tag)
            except Exception:
                pass
        qb.torrents_add_tags(tags=tags_str, torrent_hashes=info_hash)
    else:
        try:
            qb.torrents_remove_tags(tags="*", torrent_hashes=info_hash)
        except Exception:
            pass
