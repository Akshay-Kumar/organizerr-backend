from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class FileActionRequest(BaseModel):
    action: str
    mode: str = "FULL"

    info_hash: str
    file_hash: str

    payload: Dict[str, Any] = Field(
        default_factory=dict
    )