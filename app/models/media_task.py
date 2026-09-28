from pathlib import Path
from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field
import uuid
from sqlalchemy import Index
from sqlalchemy import Column, Text, String
import json

class MediaTask(SQLModel, table=True):
    __tablename__ = "media_tasks"

    __table_args__ = (
        Index(
            "idx_media_task_status_priority",
            "status",
            "priority"
        ),
    )

    @property
    def payload(self):
        try:
            return json.loads(
                self.payload_json or "{}"
            )
        except Exception:
            return {}

    @property
    def file_name(self):
        try:
            payload = json.loads(
                self.payload_json or "{}"
            )

            source_path = payload.get(
                "source_path"
            )

            if source_path:
                return Path(
                    source_path
                ).name

        except Exception:
            pass

        return None

    @property
    def source_folder(self):
        try:
            payload = json.loads(
                self.payload_json or "{}"
            )

            source_path = payload.get(
                "source_path"
            )

            if source_path:
                return str(
                    Path(
                        source_path
                    ).parent
                )

        except Exception:
            pass

        return None

    @payload.setter
    def payload(self, value):
        self.payload_json = json.dumps(value or {})

    id: Optional[int] = Field(
        default=None,
        primary_key=True
    )

    task_uuid: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        index=True,
        unique=True
    )

    action: str = Field(
        index=True
    )

    mode: str = Field(
        default="FULL"
    )

    status: str = Field(
        default="PENDING",
        index=True
    )

    priority: int = Field(
        default=5
    )

    info_hash: Optional[str] = Field(
        default=None,
        index=True
    )

    file_hash: Optional[str] = Field(
        default=None,
        index=True
    )

    payload_json: Optional[str] = Field(
        default="{}",
        sa_column=Column(
            Text
        )
    )

    progress: float = Field(
        default=0
    )

    current_stage: Optional[str] = Field(
        default=None,
        sa_column=Column(String(50))
    )

    current_message: Optional[str] = Field(
        default=None,
        sa_column=Column(Text)
    )

    retry_count: int = Field(
        default=0
    )

    max_retries: int = Field(
        default=3
    )

    worker_id: Optional[str] = Field(
        default=None,
        sa_column=Column(String(100))
    )

    created_by: Optional[int] = Field(
        default=None,
        foreign_key="user.id"
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow
    )

    scheduled_at: Optional[datetime] = None

    started_at: Optional[datetime] = None

    completed_at: Optional[datetime] = None

    last_heartbeat: Optional[datetime] = None

    error_message: Optional[str] = Field(
        default=None,
        sa_column=Column(
            Text
        )
    )