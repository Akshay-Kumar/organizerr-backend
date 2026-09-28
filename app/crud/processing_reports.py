import json
from sqlmodel import Session, select, desc
from app.crud import find_by_info_hash
from app.models import (
    ProcessingReport
)
from app.utils.logger import get_logger

logger = get_logger(__name__)

def create_processing_report(
    session: Session,
    data: dict
) -> ProcessingReport:

    torrent = None

    if data.get("info_hash"):
        torrent = find_by_info_hash(
            session,
            data["info_hash"]
        )

    report = ProcessingReport(
        torrent_id=torrent.id if torrent else None,
        info_hash=data.get("info_hash"),
        file_hash=data.get("file_hash"),
        media_type=data.get("media_type"),
        source_path=data.get("source_path"),
        destination_path=data.get("destination_path"),
        success=data.get("success", False),
        processing_time=data.get("processing_time"),
        report_json=json.dumps(
            data.get("report", {}),
            default=str
        )
    )

    session.add(report)
    session.commit()
    session.refresh(report)

    return report


def get_processing_reports(
    session: Session,
    info_hash: str
):
    return session.exec(
        select(ProcessingReport)
        .where(
            ProcessingReport.info_hash == info_hash
        )
        .order_by(
            desc(ProcessingReport.created_at)
        )
    ).all()


def get_processing_report(
    session: Session,
    report_id: int
):
    return session.get(
        ProcessingReport,
        report_id
    )

def delete_processing_reports(
    session,
    info_hash,
    file_hash
):
    reports = session.exec(
        select(ProcessingReport)
        .where(
            ProcessingReport.info_hash == info_hash,
            ProcessingReport.file_hash == file_hash
        )
    ).all()

    for r in reports:
        session.delete(r)

    session.commit()

def get_processing_report_by_hash(
    session,
    info_hash,
    file_hash
):
    return session.exec(
        select(ProcessingReport)
        .where(
            ProcessingReport.info_hash == info_hash,
            ProcessingReport.file_hash == file_hash
        )
    ).first()