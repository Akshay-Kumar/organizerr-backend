import json
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    HTTPException
)
from sqlmodel import Session

from app.constants.task_action import TaskAction
from app.crud import (
    create_media_task,
    get_processing_report_by_hash,
    update_media_task_status
)
from app.models import User
from app.routers.auth import (
    verify_token
)
from app.schemas import (
    FileActionRequest
)
from app.schemas import (
    MediaTaskCreate
)
from app.utils.db import (
    get_session
)
from app.utils.logger import (
    get_logger
)

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/files",
    tags=["File Actions"]
)

def get_current_user(
    token: dict = Depends(
        verify_token
    ),
    session: Session = Depends(
        get_session
    ),
) -> User:

    if not token or "user_id" not in token:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing token"
        )

    user = session.get(
        User,
        token["user_id"]
    )

    if not user:
        raise HTTPException(
            status_code=401,
            detail="User not found"
        )

    return user



@router.post("/action")
def file_action(
    request: FileActionRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    logger.info(
        f"File action requested: "
        f"user={current_user.id}, "
        f"action={request.action}, "
        f"mode={request.mode}, "
        f"info_hash={request.info_hash}, "
        f"file_hash={request.file_hash}"
    )

    if request.action.upper() != TaskAction.REPROCESS:
        raise HTTPException(
            status_code=400,
            detail="Unsupported action"
        )

    report = get_processing_report_by_hash(
        session,
        request.info_hash,
        request.file_hash
    )

    if not report:
        raise HTTPException(
            status_code=404,
            detail="Processing report not found"
        )

    try:
        report_json = json.loads(
            report.report_json
        )
    except Exception as e:
        logger.exception(
            "Unable to parse processing report"
        )

        raise HTTPException(
            status_code=500,
            detail=f"Unable to parse report JSON: {e}"
        )

    original_path = Path(
        report_json.get(
            "original_path",
            ""
        )
    )

    if not original_path.exists():
        raise HTTPException(
            status_code=400,
            detail="Source file no longer exists."
        )

    task_request = MediaTaskCreate(
        action=request.action.upper(),
        mode=request.mode,
        info_hash=request.info_hash,
        file_hash=request.file_hash,
        payload={
            "source_path": str(original_path),
            "report_id": report.id,
            "requested_by": current_user.id
        }
    )

    task = create_media_task(
        session,
        task_request,
        created_by=current_user.id
    )

    logger.info(
        f"Created MediaTask "
        f"{task.task_uuid}"
    )

    task = update_media_task_status(
        session,
        task.task_uuid,
        status="PENDING",
        stage="QUEUED",
        message="Task queued for execution."
    )

    return {
        "success": True,
        "message": (
            "Reprocess task created."
        ),

        "task_uuid": (
            task.task_uuid
        ),

        "task_status": (
            task.status
        )
    }