from typing import Optional, Dict, Any
from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator

class MediaTaskCreate(BaseModel):
    action: str
    payload: Dict[str, Any]
    mode: str = "FULL"
    priority: int = 5
    info_hash: Optional[str]
    file_hash: Optional[str]

    @field_validator("payload")
    @classmethod
    def validate_payload(
            cls,
            value
    ):
        if not value:
            raise ValueError(
                "payload cannot be empty"
            )

        return value


class MediaTaskResponse(BaseModel):
    task_uuid: str
    status: str
    progress: float