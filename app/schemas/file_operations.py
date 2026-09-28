from datetime import datetime
from typing import Optional

from pydantic import BaseModel


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
    eta: Optional[float] = None
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
    eta: Optional[float] = None
    details: Optional[str] = None

    updated_at: Optional[datetime] = None

    model_config = {
        "from_attributes": True
    }