import logging
import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from uuid import uuid4
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi import UploadFile, File, Form, BackgroundTasks, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy import text
from sqlmodel import SQLModel, Session
from sqlmodel import select

from app.crud import create_torrent, get_torrent, list_torrents, update_torrent, set_qb_error
from app.models import Torrent  # <- make sure this points to your SQLModel Torrent class
from app.qb_helper import add_torrent, set_torrent_tags
from app.routers import search_media, auth, torrents
from app.schemas import TorrentUpdate, TorrentOut
from app.utils import ws
from app.utils.db import engine, get_session
from app.utils.torrent_utils import get_info_hash_from_file, parse_magnet

# Load environment variables
load_dotenv()
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_MEDIA_TYPES = {"movie", "tv", "episode", "music", "unsorted"}
# FastAPI app
app = FastAPI(title="Torrent Metadata Manager")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search_media.router)
app.include_router(ws.router)
app.include_router(auth.router)
app.include_router(torrents.router)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Middleware to log all requests
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Incoming request: {request.method} {request.url}")
    response = await call_next(request)
    logger.info(f"Response status: {response.status_code}")
    return response


# Health check
@app.get("/ping")
async def ping():
    logger.info("Ping endpoint called")
    return {"message": "pong"}


# Startup: create tables
@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)

    # one-time migration
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA table_info(torrent)")).fetchall()
        columns = [row[1] for row in result]
        if "correct_name" not in columns:
            conn.execute(text("ALTER TABLE torrent ADD COLUMN correct_name TEXT"))
            conn.commit()
            print("Column 'correct_name' added successfully.")

        if False:
            conn.execute(text("DELETE FROM torrent"))
            conn.commit()
            print("All torrent records deleted.")


# --------------------------
# Add torrent endpoint
# --------------------------
@app.post("/torrents", response_model=TorrentOut, status_code=201)
async def add_torrent_endpoint(
        source: str = Form(None),
        name: str = Form(None),
        media_type: str = Form(None),
        season: int = Form(None),
        episode: int = Form(None),
        episode_title: str = Form(None),
        year: int = Form(None),
        poster: str = Form(None),
        tmdb_id: int = Form(None),
        tags: str = Form(""),
        custom_metadata: str = Form("{}"),
        file: UploadFile = File(None),
        background_tasks: BackgroundTasks = None,
        session: Session = Depends(get_session),
):
    # --- Handle file upload or source ---
    if file:
        target = UPLOAD_DIR / file.filename
        with open(target, "wb") as f:
            shutil.copyfileobj(file.file, f)
        source_val = str(target)
        name_val = Path(file.filename).stem

        # Extract info-hash directly from file
        info_hash_val = get_info_hash_from_file(source_val)
    elif source:
        source_val = source
        # --- Magnet link handling ---
        if source.startswith("magnet:?"):
            info_hash_val, name_from_magnet, trackers = parse_magnet(source)

            # If name not provided, fallback to magnet name
            name_val = name or name_from_magnet or "Unknown"
    else:
        raise HTTPException(status_code=400, detail="No torrent provided")

    # --- Convert tags and custom metadata ---
    tags_list = [t.strip() for t in tags.split(",") if t.strip()]
    try:
        custom_metadata_dict = json.loads(custom_metadata)
        if not isinstance(custom_metadata_dict, dict):
            custom_metadata_dict = {}
    except Exception:
        custom_metadata_dict = {}

    # --- Check for existing record ---
    rec = session.exec(select(Torrent).where(Torrent.source == source_val)).first()
    if rec:
        # Update existing
        rec.name = name_val or rec.name
        rec.correct_name = name or rec.correct_name
        rec.media_type = media_type or rec.media_type
        rec.season = season or rec.season
        rec.episode = episode or rec.episode
        rec.episode_title = episode_title or rec.episode_title
        rec.year = year or rec.year
        rec.poster = poster or rec.poster
        rec.tmdb_id = tmdb_id or rec.tmdb_id
        rec.set_tags_list(tags_list)
        rec.set_custom_metadata(custom_metadata_dict)
        if info_hash_val:
            rec.info_hash = info_hash_val
            rec.qb_added = True
        rec.updated_at = datetime.utcnow()
        session.add(rec)
        session.commit()
        session.refresh(rec)
    else:
        # Create new
        rec = create_torrent(
            session,
            info_hash=info_hash_val,
            name=name_val,
            correct_name=name,
            source=source_val,
            save_path=None,
            media_type=media_type,
            season=season,
            episode=episode,
            episode_title=episode_title,
            year=year,
            poster=poster,
            tmdb_id=tmdb_id,
            tags=tags_list,
            custom_metadata=custom_metadata_dict,
            qb_added=True if info_hash_val else False,
        )

    # --- Background task to add to qBittorrent ---
    def _add_to_qb(info_hash: str, local_rec_id: int, source_path: str, tags):
        try:
            add_torrent(info_hash, source_path, save_path=None, tags=tags)
        except Exception as e:
            set_qb_error(Session(engine), local_rec_id, str(e))

    background_tasks.add_task(_add_to_qb, info_hash_val, rec.id, source_val, tags_list)

    # --- Return immediately ---
    return {
        "id": rec.id,
        "info_hash": rec.info_hash,
        "name": rec.name,
        "correct_name": rec.correct_name,
        "source": rec.source,
        "save_path": rec.save_path,
        "media_type": rec.media_type,
        "season": rec.season,
        "episode": rec.episode,
        "episode_title": rec.episode_title,
        "year": rec.year,
        "poster": rec.poster,
        "tmdb_id": rec.tmdb_id,
        "tags": rec.tags_list(),
        "custom_metadata": rec.get_custom_metadata(),
        "qb_added": rec.qb_added,
        "qb_error": rec.qb_error
    }


@app.post("/torrents/batch", response_model=list[TorrentOut], status_code=201)
async def add_torrents_batch(
    files: Optional[List[UploadFile]] = File(None),
    metadata: str = Form("[]"),  # JSON string: array of metadata objects
    background_tasks: BackgroundTasks = None,
    session: Session = Depends(get_session),
):
    """
    Batch endpoint to upload multiple .torrent files and/or magnets.
    Frontend should send:
      - files: multiple file fields (same order as metadata entries that correspond to files)
      - metadata: JSON string of array of objects, each object may contain:
          {
            "source": "magnet:?xt=urn:btih:...",   # optional
            "name": "Correct name",
            "media_type": "movie|tv|episode|music|unsorted",
            "season": 1,
            "episode": 2,
            "episode_title": "Title",
            "year": 2020,
            "poster": "https://...",
            "tmdb_id": 12345,
            "tags": "tag1,tag2",
            "custom_metadata": {...}
          }
    """
    # Parse metadata JSON
    try:
        meta_list = json.loads(metadata or "[]")
        if not isinstance(meta_list, list):
            raise ValueError("metadata must be a JSON array")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid metadata JSON: {e}")

    files = files or []
    results = []
    new_records = []

    def _add_to_qb(info_hash: str, local_rec_id: int, source_path: str, tags):
        try:
            add_torrent(info_hash, source_path, save_path=None, tags=tags)
        except Exception as e:
            set_qb_error(Session(engine), local_rec_id, str(e))

    total = max(len(files), len(meta_list))

    for i in range(total):
        file = files[i] if i < len(files) else None
        meta = meta_list[i] if i < len(meta_list) else {}

        # handle integer conversion
        season_val = meta.get("season")
        episode_val = meta.get("episode")
        year_val = meta.get("year")

        # Normalize metadata fields
        source = meta.get("source")
        name_override = meta.get("name")
        media_type = meta.get("media_type")
        season = int(season_val) if season_val not in (None, "") else None
        episode = int(episode_val) if episode_val not in (None, "") else None
        episode_title = meta.get("episode_title")
        year = int(year_val) if year_val not in (None, "") else None
        poster = meta.get("poster")
        tmdb_id = meta.get("tmdb_id")
        tags = meta.get("tags", "") or ""
        custom_metadata = meta.get("custom_metadata", {}) or {}

        # --- Validate media_type ---
        if media_type and media_type not in ALLOWED_MEDIA_TYPES:
            results.append({
                "index": i,
                "status": "error",
                "detail": f"Invalid media_type '{media_type}'. Allowed: {', '.join(ALLOWED_MEDIA_TYPES)}"
            })
            continue

        # Convert tags/custom_metadata formats
        tags_list = tags if isinstance(tags, list) else [t.strip() for t in str(tags).split(",") if t.strip()]
        if isinstance(custom_metadata, str):
            try:
                custom_metadata_dict = json.loads(custom_metadata)
                if not isinstance(custom_metadata_dict, dict):
                    custom_metadata_dict = {}
            except Exception:
                custom_metadata_dict = {}
        elif isinstance(custom_metadata, dict):
            custom_metadata_dict = custom_metadata
        else:
            custom_metadata_dict = {}

        try:
            # Determine source_val, name_val, info_hash
            info_hash_val = None
            name_val = None
            source_val = None

            if file:
                # Save uploaded file with uuid prefix to avoid collisions
                target = UPLOAD_DIR / f"{uuid4()}_{file.filename}"
                with open(target, "wb") as f:
                    shutil.copyfileobj(file.file, f)
                source_val = str(target)
                name_val = Path(file.filename).stem
                try:
                    info_hash_val = get_info_hash_from_file(source_val)
                except Exception:
                    info_hash_val = None

            elif source and isinstance(source, str):
                source_val = source
                if source.startswith("magnet:?"):
                    info_hash_val, name_from_magnet, trackers = parse_magnet(source)
                    name_val = name_override or name_from_magnet or "Unknown"
                else:
                    name_val = name_override or Path(source).stem
            else:
                results.append({
                    "index": i,
                    "status": "error",
                    "detail": "No file or source provided for this entry"
                })
                continue

            if name_override:
                name_val = name_override

            # Check existing record
            rec = session.exec(select(Torrent).where(Torrent.source == source_val)).first()
            if rec:
                # Update existing
                rec.name = name_val or rec.name
                rec.correct_name = name_override or rec.correct_name
                rec.media_type = media_type or rec.media_type
                rec.season = season or rec.season
                rec.episode = episode or rec.episode
                rec.episode_title = episode_title or rec.episode_title
                rec.year = year or rec.year
                rec.poster = poster or rec.poster
                rec.tmdb_id = tmdb_id or rec.tmdb_id
                rec.set_tags_list(tags_list)
                rec.set_custom_metadata(custom_metadata_dict)
                if info_hash_val:
                    rec.info_hash = info_hash_val
                    rec.qb_added = True
                rec.updated_at = datetime.utcnow()
                new_records.append(rec)
            else:
                rec = create_torrent(
                    session,
                    info_hash=info_hash_val,
                    name=name_val,
                    correct_name=name_override,
                    source=source_val,
                    save_path=None,
                    media_type=media_type,
                    season=season,
                    episode=episode,
                    episode_title=episode_title,
                    year=year,
                    poster=poster,
                    tmdb_id=tmdb_id,
                    tags=tags_list,
                    custom_metadata=custom_metadata_dict,
                    qb_added=True if info_hash_val else False,
                )
                new_records.append(rec)

            if background_tasks is not None and info_hash_val:
                background_tasks.add_task(_add_to_qb, info_hash_val, rec.id, source_val, tags_list)

            results.append({
                "id": rec.id,
                "info_hash": rec.info_hash,
                "name": rec.name,
                "correct_name": rec.correct_name,
                "source": rec.source,
                "save_path": rec.save_path,
                "media_type": rec.media_type,
                "season": rec.season,
                "episode": rec.episode,
                "episode_title": rec.episode_title,
                "year": rec.year,
                "poster": rec.poster,
                "tmdb_id": rec.tmdb_id,
                "tags": rec.tags_list(),
                "custom_metadata": rec.get_custom_metadata(),
                "qb_added": rec.qb_added,
                "qb_error": rec.qb_error
            })

        except Exception as e:
            logger.exception("Failed to process batch item %s", i)
            results.append({
                "index": i,
                "status": "error",
                "detail": str(e)
            })

    # --- Bulk commit for performance ---
    try:
        session.add_all(new_records)
        session.commit()
    except Exception as e:
        session.rollback()
        logger.exception("Bulk commit failed")
        raise HTTPException(status_code=500, detail="Failed to save all torrents")
    return results

# --------------------------
# Get all torrents
# --------------------------
@app.get("/torrents", response_model=list[TorrentOut])
def get_all_torrents(session: Session = Depends(get_session)):
    items = list_torrents(session)
    out = []
    for t in items:
        out.append({
            "id": t.id,
            "info_hash": t.info_hash,
            "name": t.name,
            "correct_name": t.correct_name,
            "source": t.source,
            "save_path": t.save_path,
            "media_type": t.media_type,
            "season": t.season,
            "episode": t.episode,
            "episode_title": t.episode_title,
            "year": t.year,
            "poster": t.poster,
            "tmdb_id": t.tmdb_id,
            "tags": t.tags_list(),
            "custom_metadata": t.get_custom_metadata(),
            "qb_added": t.qb_added,
            "qb_error": t.qb_error
        })
    return out


@app.get("/torrents/by_info_hash/{info_hash}", response_model=TorrentOut)
def get_torrent_by_info_hash(info_hash: str, session: Session = Depends(get_session)):
    t = session.exec(
        select(Torrent).where(Torrent.info_hash == info_hash)
    ).first()

    if not t:
        raise HTTPException(404, "Torrent not found")

    return {
        "id": t.id,
        "info_hash": t.info_hash,
        "name": t.name,
        "correct_name": t.correct_name,
        "source": t.source,
        "save_path": t.save_path,
        "media_type": t.media_type,
        "season": t.season,
        "episode": t.episode,
        "episode_title": t.episode_title,
        "year": t.year,
        "poster": t.poster,
        "tmdb_id": t.tmdb_id,
        "tags": t.tags_list(),
        "custom_metadata": t.get_custom_metadata(),
        "qb_added": t.qb_added,
        "qb_error": t.qb_error
    }


# --------------------------
# Update torrent
# --------------------------
@app.patch("/torrents/{torrent_id}", response_model=TorrentOut)
def patch_torrent(torrent_id: int, payload: TorrentUpdate, session: Session = Depends(get_session)):
    t = get_torrent(session, torrent_id)
    if not t:
        raise HTTPException(404, "Not found")
    data = payload.dict(exclude_unset=True)
    updated = update_torrent(session, torrent_id, **data)

    # Sync tags to qBittorrent if info_hash exists
    if updated and updated.info_hash and payload.tags is not None:
        try:
            set_torrent_tags(updated.info_hash, payload.tags)
        except Exception:
            pass

    return {
        "id": updated.id,
        "info_hash": updated.info_hash,
        "name": updated.name,
        "correct_name": updated.correct_name,
        "source": updated.source,
        "save_path": updated.save_path,
        "media_type": updated.media_type,
        "season": updated.season,
        "episode": updated.episode,
        "episode_title": updated.episode_title,
        "year": updated.year,
        "poster": updated.poster,
        "tmdb_id": updated.tmdb_id,
        "tags": updated.tags_list(),
        "custom_metadata": updated.get_custom_metadata(),
        "qb_added": updated.qb_added,
        "qb_error": updated.qb_error
    }
