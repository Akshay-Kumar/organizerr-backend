from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field


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