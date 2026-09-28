import json
from datetime import datetime
from sqlmodel import Session, select
from app.models import MediaTask
from app.utils.logger import get_logger
from sqlalchemy import func
from app.schemas import MediaTaskCreate

logger = get_logger(__name__)

def create_media_task(
    session: Session,
    task_data,
    created_by: int = None
):
    task = MediaTask(
        action=task_data.action.upper(),
        mode=task_data.mode,
        priority=task_data.priority,
        info_hash=task_data.info_hash,
        file_hash=task_data.file_hash,
        payload_json=json.dumps(
            task_data.payload
        ),
        created_by=created_by
    )

    session.add(task)
    session.commit()
    session.refresh(task)

    return task


def get_media_task(
    session: Session,
    task_uuid: str
):
    return session.exec(
        select(MediaTask)
        .where(
            MediaTask.task_uuid == task_uuid
        )
    ).first()


def get_media_tasks(
    session: Session,
    status: str = None,
    action: str = None,
    page: int = 1,
    page_size: int = 50
):
    query = select(
        MediaTask
    )

    if status:
        query = query.where(
            MediaTask.status == status.upper()
        )

    if action:
        query = query.where(
            MediaTask.action == action.upper()
        )

    total_query = query

    query = (
        query
        .order_by(
            MediaTask.created_at.desc()
        )
        .offset(
            (page - 1) * page_size
        )
        .limit(
            page_size
        )
    )

    db_tasks = session.exec(
        query
    ).all()

    tasks = []

    for task in db_tasks:
        item = task.model_dump()
        item["file_name"] = task.file_name
        item["source_folder"] = task.source_folder
        tasks.append(item)

    total = session.exec(
        select(
            func.count()
        ).select_from(
            total_query.subquery()
        )
    ).one()

    return {
        "items": tasks,
        "total": total,
        "page": page,
        "page_size": page_size
    }


def update_media_task_status(
    session: Session,
    task_uuid: str,
    status: str,
    progress: float = None,
    stage: str = None,
    message: str = None,
    worker_id: str = None,
    error_message: str = None
):
    task = get_media_task(
        session,
        task_uuid
    )

    if not task:
        return None

    task.status = status

    if progress is not None:
        task.progress = progress

    if stage is not None:
        task.current_stage = stage

    if message is not None:
        task.current_message = message

    if worker_id is not None:
        task.worker_id = worker_id

    if error_message is not None:
        task.error_message = error_message

    if status == "RUNNING" and not task.started_at:
        task.started_at = datetime.utcnow()

    if status in [
        "COMPLETED",
        "FAILED",
        "CANCELLED"
    ]:
        task.completed_at = datetime.utcnow()

    session.add(task)
    session.commit()
    session.refresh(task)

    return task

def get_next_pending_media_task(
    session: Session
):
    return session.exec(
        select(MediaTask)
        .where(
            MediaTask.status == "PENDING"
        )
        .order_by(
            MediaTask.priority.desc(),
            MediaTask.created_at.asc()
        )
    ).first()

def get_media_task_stats(
    session: Session
):
    return {
        "pending": session.exec(
            select(func.count())
            .where(
                MediaTask.status == "PENDING"
            )
        ).one(),

        "running": session.exec(
            select(func.count())
            .where(
                MediaTask.status == "RUNNING"
            )
        ).one(),

        "completed": session.exec(
            select(func.count())
            .where(
                MediaTask.status == "COMPLETED"
            )
        ).one(),

        "failed": session.exec(
            select(func.count())
            .where(
                MediaTask.status == "FAILED"
            )
        ).one(),

        "total": session.exec(
            select(func.count())
            .select_from(MediaTask)
        ).one()
    }

def delete_completed_tasks(
    session: Session
):
    tasks = session.exec(
        select(MediaTask)
        .where(
            MediaTask.status == "COMPLETED"
        )
    ).all()

    deleted_count = len(tasks)

    for task in tasks:
        session.delete(task)

    session.commit()

    return deleted_count


def delete_failed_tasks(
    session: Session
):
    tasks = session.exec(
        select(MediaTask)
        .where(
            MediaTask.status == "FAILED"
        )
    ).all()

    deleted_count = len(tasks)

    for task in tasks:
        session.delete(task)

    session.commit()

    return deleted_count


