from sqlmodel import SQLModel, Field
from typing import Optional, List
import json
from datetime import datetime


# ----------------------------
# Torrent model
# ----------------------------
class Torrent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
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
