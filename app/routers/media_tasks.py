from fastapi import APIRouter, Depends
from sqlmodel import Session
from fastapi import HTTPException
from typing import Optional
from fastapi import Query
from app.schemas.media_tasks import (
    MediaTaskCreate
)

from app.utils.db import (
    get_session
)

from app.crud.media_tasks import (
    create_media_task,
    get_media_task,
    get_media_tasks
)
from app.crud import (
    get_media_task_stats
)

from app.crud import (
    delete_completed_tasks,
    delete_failed_tasks
)

router = APIRouter(
    prefix="/api/tasks",
    tags=["Tasks"]
)


@router.post("", summary="Developer endpoint for manual task creation")
def create_task(
    request: MediaTaskCreate,
    session: Session = Depends(
        get_session
    )
):
    """
    Internal endpoint.

    Business workflows should create tasks through
    their respective APIs rather than directly.
    """
    task = create_media_task(
        session,
        request
    )

    return task


@router.get("")
def list_tasks(
    status: Optional[str] = None,
    action: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    session: Session = Depends(
        get_session
    )
):
    return get_media_tasks(
        session,
        status=status,
        action=action,
        page=page,
        page_size=page_size
    )


@router.get("/stats")
def task_stats(
    session: Session = Depends(
        get_session
    )
):
    return get_media_task_stats(
        session
    )

@router.delete("/completed")
def cleanup_completed_tasks(
    session: Session = Depends(
        get_session
    )
):
    deleted_count = delete_completed_tasks(
        session
    )

    return {
        "success": True,
        "deleted_count": deleted_count
    }


@router.delete("/failed")
def cleanup_failed_tasks(
    session: Session = Depends(
        get_session
    )
):
    deleted_count = delete_failed_tasks(
        session
    )

    return {
        "success": True,
        "deleted_count": deleted_count
    }

@router.get("/{task_uuid}")
def get_task(
    task_uuid: str,
    session: Session = Depends(
        get_session
    )
):
    task = get_media_task(
        session,
        task_uuid
    )

    if not task:
        raise HTTPException(
            status_code=404,
            detail="Task not found"
        )

    return task

@router.post("/{task_uuid}/retry")
def retry_task(
    task_uuid: str,
    session: Session = Depends(
        get_session
    )
):
    task = get_media_task(
        session,
        task_uuid
    )

    if not task:
        raise HTTPException(
            status_code=404,
            detail="Task not found"
        )

    if task.status == "RUNNING":
        raise HTTPException(
            status_code=400,
            detail=(
                "Task is already "
                "running."
            )
        )

    task.status = "PENDING"
    task.progress = 0
    task.current_stage = None
    task.current_message = None
    task.error_message = None
    task.started_at = None
    task.completed_at = None

    session.add(task)
    session.commit()
    session.refresh(task)

    return {
        "success": True,
        "message": (
            "Task queued "
            "for retry."
        ),
        "task_uuid": task.task_uuid
    }

@router.delete("/{task_uuid}")
def delete_task(
    task_uuid: str,
    session: Session = Depends(
        get_session
    )
):
    task = get_media_task(
        session,
        task_uuid
    )

    if not task:
        raise HTTPException(
            status_code=404,
            detail="Task not found"
        )

    if task.status == "RUNNING":
        raise HTTPException(
            status_code=400,
            detail=(
                "Cannot delete "
                "running task."
            )
        )

    session.delete(task)
    session.commit()

    return {
        "success": True,
        "message": "Task deleted."
    }

