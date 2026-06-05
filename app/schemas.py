from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime
from typing import List

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


# ----------------------------
# FileOperation schemas
# ----------------------------
class FileOperationCreate(BaseModel):
    torrent_id: Optional[int] = None
    operation: Optional[str] = None
    source: Optional[str] = None
    destination: Optional[str] = None
    backup: Optional[str] = None
    timestamp: Optional[datetime] = None
    success: Optional[bool] = None
    file_size: Optional[int] = None
    file_hash: Optional[str] = None
    info_hash: str  # ✅ now REQUIRED
    stage: Optional[str] = None
    progress: Optional[float] = None
    status: Optional[str] = None

    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None

    speed: Optional[float] = None
    eta: Optional[int] = None
    details: Optional[str] = None

    updated_at: Optional[datetime] = None


class FileOperationUpdate(BaseModel):
    source: Optional[str] = None
    destination: Optional[str] = None
    backup: Optional[str] = None
    timestamp: Optional[datetime] = None
    success: Optional[bool] = None
    file_size: Optional[int] = None
    file_hash: Optional[str] = None
    updated_at: Optional[datetime] = None


class FileOperationOut(BaseModel):
    torrent_id: Optional[int] = None
    operation: Optional[str] = None
    source: Optional[str] = None
    destination: Optional[str] = None
    backup: Optional[str] = None
    timestamp: Optional[datetime] = None
    success: Optional[bool] = None
    file_size: Optional[int] = None
    file_hash: Optional[str] = None
    info_hash: str  # ✅ now REQUIRED
    stage: Optional[str] = None
    progress: Optional[float] = None
    status: Optional[str] = None

    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None

    speed: Optional[float] = None
    eta: Optional[int] = None
    details: Optional[str] = None

    updated_at: Optional[datetime] = None

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


class ProcessingReportCreate(BaseModel):
    info_hash: str
    file_hash: Optional[str] = None
    media_type: Optional[str] = None
    source_path: Optional[str] = None
    destination_path: Optional[str] = None
    success: bool = False
    processing_time: Optional[float] = None
    report: Dict[str, Any]


class ProcessingReportOut(BaseModel):
    id: int
    torrent_id: Optional[int] = None
    info_hash: Optional[str] = None
    file_hash: Optional[str] = None
    media_type: Optional[str] = None
    success: bool
    processing_time: Optional[float] = None
    created_at: datetime
    report_json: str
