import shutil
import time

from pathlib import Path

from fastapi import APIRouter
from sqlmodel import Session, text

from app.utils.db import engine
from app.qb_helper import get_qb
from app.utils.ws import manager
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/health", tags=["health"])

START_TIME = time.time()


# ---------------------------------------------------
# LIVE
# ---------------------------------------------------
@router.get("/live")
def health_live():

    return {
        "status": "alive"
    }


# ---------------------------------------------------
# READY
# ---------------------------------------------------
@router.get("/ready")
def health_ready():

    checks = {
        "database": False,
        "qbittorrent": {
            "connected": False,
            "version": None,
        },
        "filesystem": False,
    }

    # -----------------------------
    # Database
    # -----------------------------
    try:

        with Session(engine) as session:
            session.exec(text("SELECT 1"))

        checks["database"] = True

    except Exception:
        logger.exception("Database health check failed")

    # -----------------------------
    # qBittorrent
    # -----------------------------
    try:

        qb = get_qb()

        qb.auth_log_in()

        version = str(qb.app.version)

        checks["qbittorrent"] = {
            "connected": True,
            "version": version,
        }

    except Exception as e:

        logger.exception("qBittorrent health check failed")

        checks["qbittorrent"] = {
            "connected": False,
            "error": str(e),
        }

    # -----------------------------
    # Filesystem
    # -----------------------------
    try:

        test_path = Path("logs/.healthcheck")

        test_path.write_text("ok")

        test_path.unlink(missing_ok=True)

        checks["filesystem"] = True

    except Exception:
        logger.exception("Filesystem health check failed")

    healthy = (
        checks["database"] is True
        and checks["filesystem"] is True
        and checks["qbittorrent"].get("connected") is True
    )

    return {
        "status": "ready" if healthy else "degraded",
        "checks": checks
    }


# ---------------------------------------------------
# FULL
# ---------------------------------------------------
@router.get("/full")
def health_full():

    total, used, free = shutil.disk_usage(Path.cwd())

    uptime_seconds = int(time.time() - START_TIME)

    return {
        "status": "ok",

        "uptime_seconds": uptime_seconds,

        "websocket_clients": len(manager.active),

        "disk": {
            "total_gb": round(total / (1024**3), 2),
            "used_gb": round(used / (1024**3), 2),
            "free_gb": round(free / (1024**3), 2),
        }
    }