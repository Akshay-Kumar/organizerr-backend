from datetime import datetime
from typing import Optional, Dict, Any

from pydantic import BaseModel


# ----------------------------
# User schemas
# ----------------------------

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