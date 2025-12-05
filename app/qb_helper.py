import os
import time
from pathlib import Path
from typing import Optional, List
from qbittorrentapi import Client
from dotenv import load_dotenv
from qbittorrentapi.exceptions import LoginFailed

load_dotenv()
QBT_HOST = os.getenv("QBT_HOST", "http://127.0.0.1:8080")
QBT_USER = os.getenv("QBT_USER", "admin")
QBT_PASS = os.getenv("QBT_PASS", "adminadmin")


def get_qb_client() -> Client:
    qb = Client(host=QBT_HOST, username=QBT_USER, password=QBT_PASS)
    qb.auth_log_in()
    return qb


def add_torrent(info_hash: str, magnet_or_file: str, save_path: Optional[str] = None, tags: Optional[List[str]] = None,
                category: Optional[str] = None) -> Optional[str]:
    """
    Add a magnet link or .torrent file to qBittorrent and return its info-hash.
    """
    qb = get_qb_client()
    tags_str = ",".join(tags) if tags else None

    if magnet_or_file.startswith("magnet:"):
        # Add magnet link
        qb.torrents_add(urls=magnet_or_file, save_path=save_path, tags=tags_str, category=category)
        # Extract info-hash from magnet URI
        try:
            return magnet_or_file.split("btih:")[1].split("&")[0].lower()
        except IndexError:
            return None
    else:
        # Add .torrent file
        with open(magnet_or_file, "rb") as fh:
            qb.torrents_add(torrent_files=fh, save_path=save_path, tags=tags_str, category=category)

        # Poll qBittorrent quickly for the newly-added torrent by exact filename match
        for _ in range(10):
            torrents = qb.torrents_info(sort='added_on', reverse=True)
            for t in torrents:
                t_hash = getattr(t, "hash", "") or None
                if info_hash == t_hash:
                    return t_hash
            time.sleep(0.5)

        # Fallback
        return None


def list_torrents():
    qb = get_qb_client()
    return qb.torrents_info()


def find_torrent_by_hash(info_hash: str):
    qb = get_qb_client()
    torrents = qb.torrents_info()
    for t in torrents:
        if getattr(t, "hash", None) == info_hash:
            return t
    return None


def set_torrent_tags(info_hash: str, tags: List[str]):
    qb = get_qb_client()
    tags_str = ",".join(tags) if tags else ""
    # Create tags if needed, then add
    if tags:
        for tag in tags:
            try:
                qb.torrents_create_tag(tag)
            except Exception:
                pass
        qb.torrents_add_tags(tags=tags_str, torrent_hashes=info_hash)
    else:
        # Remove all tags
        try:
            qb.torrents_remove_tags(tags="*", torrent_hashes=info_hash)
        except Exception:
            pass


# app/qb_helper.py
def get_qb() -> Client:
    """
    Returns a logged-in qBittorrent client.
    This is a convenience wrapper for backend routes.
    """
    return get_qb_client()
