from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
import json
from pathlib import Path
from app.utils.db import get_session
from app.models import ProcessingReport, Torrent
from sqlalchemy import func, or_
router = APIRouter(
    prefix="/processing-reports",
    tags=["Processing Reports"]
)


@router.get("")
def get_processing_reports(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: str = Query(None),
    session: Session = Depends(get_session)
):
    offset = (page - 1) * page_size

    query = (
        select(
            ProcessingReport,
            Torrent.name
        )
        .join(
            Torrent,
            ProcessingReport.torrent_id == Torrent.id,
            isouter=True
        )
    )

    if search:
        search_term = f"%{search}%"

        query = query.where(
            or_(
                ProcessingReport.source_path.ilike(search_term),
                ProcessingReport.media_type.ilike(search_term),
                Torrent.name.ilike(search_term)
            )
        )

    total_reports = session.exec(
        select(func.count())
        .select_from(query.subquery())
    ).one()

    results = session.exec(
        query
        .order_by(
            ProcessingReport.created_at.desc()
        )
        .offset(offset)
        .limit(page_size)
    ).all()

    successful_reports = session.exec(
        select(func.count())
        .select_from(ProcessingReport)
        .where(
            ProcessingReport.success == True
        )
    ).one()

    failed_reports = session.exec(
        select(func.count())
        .select_from(ProcessingReport)
        .where(
            ProcessingReport.success == False
        )
    ).one()

    all_reports = session.exec(
        select(ProcessingReport.report_json)
    ).all()

    skipped_reports = sum(
        1
        for r in all_reports
        if r and '"skipped": true' in r.lower()
    )

    failed_reports = failed_reports - skipped_reports

    reports = []
    for report, torrent_name in results:

        report_dict = report.dict()

        parsed_title = None
        is_skipped = False
        skip_reason = None
        warnings = []

        try:
            report_json = json.loads(
                report.report_json
            )

            parsed_title = report_json.get(
                "title"
            )

            is_skipped = report_json.get(
                "skipped",
                False
            )

            skip_reason = report_json.get(
                "skip_reason"
            )

            warnings = report_json.get(
                "warnings",
                []
            )

        except Exception:
            pass

        source_filename = None

        if report.source_path:
            source_filename = Path(
                report.source_path
            ).name

        report_dict["torrent_name"] = torrent_name
        report_dict["parsed_title"] = parsed_title
        report_dict["source_filename"] = source_filename

        report_dict["skipped"] = is_skipped
        report_dict["skip_reason"] = skip_reason
        report_dict["warnings"] = warnings

        reports.append(report_dict)

    return {
        "items": reports,
        "total": total_reports,
        "successful": successful_reports,
        "failed": failed_reports,
        "skipped": skipped_reports,
        "page": page,
        "page_size": page_size
    }


@router.get("/{report_id}")
def get_processing_report(
    report_id: int,
    session: Session = Depends(get_session)
):
    report = session.get(
        ProcessingReport,
        report_id
    )

    if not report:
        raise HTTPException(
            status_code=404,
            detail="Report not found"
        )

    return report


@router.get("/torrent/{torrent_id}")
def get_reports_for_torrent(
    torrent_id: int,
    session: Session = Depends(get_session)
):

    results = session.exec(
        select(
            ProcessingReport,
            Torrent.name
        )
        .join(
            Torrent,
            ProcessingReport.torrent_id == Torrent.id,
            isouter=True
        )
        .where(
            ProcessingReport.torrent_id == torrent_id
        )
        .order_by(
            ProcessingReport.created_at.desc()
        )
    ).all()

    reports = []
    for report, torrent_name in results:
        report_dict = report.dict()
        parsed_title = None
        is_skipped = False
        skip_reason = None
        warnings = []

        try:

            report_json = json.loads(
                report.report_json
            )

            parsed_title = (
                report_json.get("title")
            )

            is_skipped = report_json.get(
                "skipped",
                False
            )

            skip_reason = report_json.get(
                "skip_reason"
            )

            warnings = report_json.get(
                "warnings",
                []
            )

        except Exception:
            pass

        source_filename = None

        if report.source_path:
            source_filename = Path(
                report.source_path
            ).name

        report_dict["torrent_name"] = torrent_name
        report_dict["source_filename"] = source_filename
        report_dict["parsed_title"] = parsed_title

        report_dict["skipped"] = is_skipped
        report_dict["skip_reason"] = skip_reason
        report_dict["warnings"] = warnings

        reports.append(report_dict)

    return reports