from datetime import datetime
from typing import Optional

from sqlalchemy import Index
from sqlalchemy import UniqueConstraint
from sqlmodel import SQLModel, Field


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