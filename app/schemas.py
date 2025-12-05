from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict


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
    tags: Optional[List[str]] = []
    custom_metadata: Optional[Dict] = {}


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


# ----------------------------
# User schemas
# ----------------------------
class UserCreateIn(BaseModel):
    username: str
    email: Optional[EmailStr] = None
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    email: Optional[EmailStr] = None
    is_active: bool
    is_admin: bool

    model_config = {
        "from_attributes": True
    }


class TokenOut(BaseModel):
    access_token: str
    token_type: str
