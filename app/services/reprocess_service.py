import shutil
import subprocess
import json
from pathlib import Path
from datetime import datetime
from sqlmodel import Session
from app.crud import update_media_task_status
from app.crud import (
    delete_file_operations,
    delete_processing_reports,
    get_processing_report_by_hash
)
from app.utils.logger import get_logger

logger = get_logger(__name__)

class ReprocessService:
    @staticmethod
    def execute(
        session: Session,
        task
    ):

        logger.info(
            f"payload_json={task.payload_json}"
        )

        logger.info(
            f"payload={task.payload}"
        )

        payload = json.loads(
            task.payload_json or "{}"
        )
        ReprocessService.update_progress(
            session,
            task,
            progress=5,
            stage="VALIDATING",
            message="Validating task payload."
        )

        source_path_str = payload.get(
            "source_path"
        )

        if not source_path_str:
            raise Exception(
                "Task payload missing source_path."
            )

        source_path = Path(
            source_path_str
        )
        ReprocessService.update_progress(
            session,
            task,
            progress=10,
            stage="CHECKING_SOURCE",
            message="Checking source file."
        )

        if not source_path.exists():
            raise Exception(
                "Source file missing."
            )

        ReprocessService.update_progress(
            session,
            task,
            progress=20,
            stage="GETTING_PROCESSING_REPORT",
            message="Getting processing report from database."
        )
        report = get_processing_report_by_hash(
            session,
            task.info_hash,
            task.file_hash
        )

        if not report:
            raise Exception(
                "Processing report missing."
            )

        if not report.destination_path:
            raise Exception(
                "Destination path missing from report."
            )

        destination_path = Path(
            report.destination_path
        )

        ReprocessService.update_progress(
            session,
            task,
            progress=25,
            stage="CHECKING_DESTINATION",
            message="Checking destination file."
        )
        if destination_path.exists():
            logger.info(
                f"Deleting {destination_path}"
            )

            ReprocessService.update_progress(
                session,
                task,
                progress=27,
                stage="REMOVING_DESTINATION",
                message="Removing existing destination media."
            )
            if destination_path.is_file():
                destination_path.unlink()

            elif destination_path.is_dir():
                shutil.rmtree(destination_path)

        parent = destination_path.parent

        try:
            if parent.exists() and not any(parent.iterdir()):
                parent.rmdir()
        except Exception:
            logger.warning(
                f"Unable to remove empty folder "
                f"{parent}"
            )

        MEDIA_ORGANIZER_BAT = (
            r"C:\Users\akki0\PycharmProjects"
            r"\media-organizer"
            r"\media_organizer_py.bat"
        )

        logger.info(
            f"Delete DB records for fileoperations and processing_reports "
            f"for task {task.task_uuid}"
        )
        ReprocessService.update_progress(
            session,
            task,
            progress=30,
            stage="DELETING_OLD_RECORDS",
            message="Deleting existing database records."
        )
        # delete DB records for fileoperations and processing_reports
        delete_file_operations(
            session,
            task.info_hash,
            task.file_hash
        )

        delete_processing_reports(
            session,
            task.info_hash,
            task.file_hash
        )

        logger.info(
            f"Launching Media Organizer "
            f"for task {task.task_uuid}"
        )
        ReprocessService.update_progress(
            session,
            task,
            progress=40,
            stage="STARTING_ORGANIZER",
            message="Launching Media Organizer."
        )

        ReprocessService.update_progress(
            session,
            task,
            progress=80,
            stage="REBUILDING_REPORTS",
            message="Rebuilding metadata and reports."
        )
        started = datetime.utcnow()
        result = subprocess.run(
            [
                MEDIA_ORGANIZER_BAT,
                str(source_path),
                "media-organizerr",
                task.info_hash
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        elapsed = (
                datetime.utcnow() - started
        ).total_seconds()
        ReprocessService.update_progress(
            session,
            task,
            progress=90,
            stage="FINALIZING",
            message="Finalizing task execution."
        )

        if result.returncode != 0:
            raise Exception(
                f"Media Organizer failed.\n"
                f"STDOUT:\n{result.stdout}\n\n"
                f"STDERR:\n{result.stderr}"
            )

        logger.info(
            f"Task completed in "
            f"{elapsed:.2f}s"
        )
        logger.debug(
            f"Media Organizer stdout:\n"
            f"{result.stdout}"
        )

        logger.info(
            f"Media Organizer completed "
            f"for task {task.task_uuid}"
        )

    @staticmethod
    def update_progress(
            session,
            task,
            progress,
            stage,
            message
    ):
        update_media_task_status(
            session,
            task.task_uuid,
            status="RUNNING",
            progress=progress,
            stage=stage,
            message=message
        )