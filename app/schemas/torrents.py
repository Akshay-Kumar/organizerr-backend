from typing import List
from typing import Optional, Dict

from pydantic import BaseModel


# ----------------------------
# Torrent schemas
# ----------------------------
class TorrentCreate(BaseModel):
    source: str
    name: Optional[str] = None
    save_path: Optional[str] = None
    media_type: Optional[str] = None
    season: Optional[int] = None
    episode: Optional[int] = None
    episode_title: Optional[str] = None
    year: Optional[int] = None
    poster: Optional[str] = None
    tmdb_id: Optional[int] = None
    tags: Optional[List[str]] = None
    custom_metadata: Optional[Dict] = None


class TorrentUpdate(BaseModel):
    name: Optional[str] = None
    save_path: Optional[str] = None
    media_type: Optional[str] = None
    season: Optional[int] = None
    episode: Optional[int] = None
    episode_title: Optional[str] = None
    year: Optional[int] = None
    poster: Optional[str] = None
    tmdb_id: Optional[int] = None
    tags: Optional[List[str]] = None
    custom_metadata: Optional[Dict] = None


class TorrentOut(BaseModel):
    id: int
    info_hash: Optional[str]
    name: Optional[str]
    correct_name: Optional[str]
    display_name: Optional[str] = None
    source: Optional[str]
    save_path: Optional[str]
    media_type: Optional[str]
    season: Optional[int]
    episode: Optional[int]
    episode_title: Optional[str]
    year: Optional[int]
    poster: Optional[str]
    tmdb_id: Optional[int]
    tags: Optional[List[str]]
    custom_metadata: Optional[Dict]
    qb_added: bool
    qb_error: Optional[str]

    model_config = {
        "from_attributes": True
    }