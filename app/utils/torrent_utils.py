import bencodepy
import hashlib
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlparse, unquote


def get_info_hash_from_file(torrent_path: str) -> Optional[str]:
    """
    Extract SHA1 info-hash directly from a .torrent file.
    """
    try:
        data = bencodepy.decode(Path(torrent_path).read_bytes())
        info = data[b'info']
        bencoded_info = bencodepy.encode(info)
        return hashlib.sha1(bencoded_info).hexdigest().lower()
    except Exception as e:
        print(f"Failed to extract info-hash: {e}")
        return None


def parse_magnet(magnet_url: str):
    # Remove "magnet:?"
    query = magnet_url.replace("magnet:?", "")

    params = parse_qs(query)

    # info hash (required field)
    info_hash = params.get("xt", [None])[0]
    if info_hash and info_hash.startswith("urn:btih:"):
        info_hash = info_hash.replace("urn:btih:", "").lower().strip()

    # display name
    name = params.get("dn", [None])[0]
    if name:
        name = unquote(name)

    # trackers (optional)
    trackers = params.get("tr", [])

    return info_hash, name, trackers
