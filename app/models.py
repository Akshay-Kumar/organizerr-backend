from sqlmodel import SQLModel, Field
from sqlalchemy import UniqueConstraint
from typing import Optional, List
import json
from datetime import datetime
from sqlalchemy import Index


# ----------------------------
# Torrent model
# ----------------------------
class Torrent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)  # ✅ ADD THIS
    info_hash: Optional[str] = None
    name: Optional[str] = None
    correct_name: Optional[str] = None
    source: Optional[str] = None
    save_path: Optional[str] = None
    media_type: Optional[str] = None
    season: Optional[int] = None
    episode: Optional[int] = None
    episode_title: Optional[str] = None
    tags: Optional[str] = None  # stored as CSV
    custom_metadata: Optional[str] = None  # stored as JSON string
    qb_added: bool = False
    qb_error: Optional[str] = None
    poster: Optional[str] = None
    tmdb_id: Optional[int] = None
    year: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # -----------------------------
    # Helper methods
    # -----------------------------
    def set_tags_list(self, tags_list: List[str]):
        self.tags = ",".join(tags_list)

    def tags_list(self) -> List[str]:
        if not self.tags:
            return []
        return [t.strip() for t in self.tags.split(",") if t.strip()]

    def set_custom_metadata(self, metadata: dict):
        self.custom_metadata = json.dumps(metadata)

    def get_custom_metadata(self) -> dict:
        if not self.custom_metadata:
            return {}
        try:
            return json.loads(self.custom_metadata)
        except Exception:
            return {}


# ----------------------------
# User model
# ----------------------------
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, nullable=False, unique=True)
    email: Optional[str] = Field(default=None, index=True)
    hashed_password: str
    is_active: bool = Field(default=True)
    is_admin: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)



# ----------------------------
# FileOperation model
# ----------------------------
class FileOperation(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("info_hash", "file_hash", "stage"),
        Index("idx_info_file", "info_hash", "file_hash"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    torrent_id: Optional[int] = Field(default=None, foreign_key="torrent.id")
    info_hash: str = None
    file_hash: Optional[str] = None
    operation: Optional[str] = None
    source: Optional[str] = None
    destination: Optional[str] = None
    backup: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    success: Optional[bool] = None
    file_size: Optional[int] = None
    stage: Optional[str] = None

    # current stage progress
    progress: Optional[float] = None  # 0 -> 100

    # initialized | processing | completed | failed
    status: Optional[str] = None

    # timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None

    # live transfer metrics
    speed: Optional[float] = None
    eta: Optional[int] = None

    # optional extra details
    details: Optional[str] = None



# ----------------------------
# ProcessingReport model
# ----------------------------
class ProcessingReport(SQLModel, table=True):
    id: Optional[int] = Field(
        default=None,
        primary_key=True
    )

    torrent_id: Optional[int] = Field(
        default=None,
        foreign_key="torrent.id",
        index=True
    )

    info_hash: Optional[str] = Field(
        default=None,
        index=True
    )

    file_hash: Optional[str] = Field(
        default=None,
        index=True
    )

    media_type: Optional[str] = None

    source_path: Optional[str] = None

    destination_path: Optional[str] = None

    success: bool = False

    processing_time: Optional[float] = None

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        index=True
    )

    report_json: str