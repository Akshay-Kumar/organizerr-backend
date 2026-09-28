import time
import threading
import socket
import uuid
from datetime import datetime
from sqlmodel import Session

from app.constants.task_action import TaskAction
from app.utils.db import engine
from app.models import MediaTask
from app.crud import (
    get_next_pending_media_task,
    update_media_task_status
)
from app.services.reprocess_service import (
    ReprocessService
)

from app.utils.logger import get_logger

logger = get_logger(__name__)


class MediaTaskExecutor:

    def __init__(self):
        self.running = False
        self.thread = None
        self.worker_id = (
            f"{socket.gethostname()}-"
            f"{uuid.uuid4().hex[:8]}"
        )

    def start(self):
        if self.running:
            return

        self.running = True

        self.thread = threading.Thread(
            target=self.run_loop,
            daemon=True
        )

        self.thread.start()

        logger.info(
            "MediaTaskExecutor started."
        )

    def stop(self):
        self.running = False

    def run_loop(self):

        while self.running:

            try:
                self.process_next_task()

            except Exception:
                logger.exception(
                    "Executor loop failure"
                )

            time.sleep(5)

    def process_next_task(self):
        # NOTE:
        # Single-worker implementation.
        # Task claiming must become atomic
        # before introducing multiple workers.
        with Session(engine) as session:
            task = get_next_pending_media_task(
                session
            )

            if not task:
                logger.debug(
                    "No pending tasks found."
                )
                return

            logger.info(
                f"Claiming task "
                f"{task.task_uuid}"
            )

            task = update_media_task_status(
                session,
                task.task_uuid,
                status="RUNNING",
                worker_id=self.worker_id,
                stage="INITIALIZING",
                message="Executor claimed task."
            )

            self.execute_task(
                session,
                task
            )

    def execute_task(
            self,
            session,
            task
    ):
        try:
            logger.info(
                f"Executing task "
                f"{task.task_uuid}"
            )

            task.last_heartbeat = datetime.utcnow()

            session.add(task)
            session.commit()
            session.refresh(task)

            if task.action == TaskAction.REPROCESS:
                ReprocessService.execute(
                    session,
                    task
                )
            else:
                raise Exception(
                    f"Unsupported task action: "
                    f"{task.action}"
                )

            update_media_task_status(
                session,
                task.task_uuid,
                status="COMPLETED",
                progress=100,
                stage="COMPLETE",
                message="Task completed."
            )

        except Exception as e:
            logger.exception(
                "Task execution failed"
            )

            update_media_task_status(
                session,
                task.task_uuid,
                status="FAILED",
                error_message=str(e)
            )
