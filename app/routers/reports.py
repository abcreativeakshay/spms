"""Report export endpoints (FR-36)."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query, Response

from app.core.security import Principal, require_admin
from app.routers.deps import get_reports_service
from app.services.reports import ReportsService

router = APIRouter(tags=["reports"])

REPORTS = ("placements", "students", "applications", "attendance", "drives")


@router.get("/reports/export")
def export_report(
    report: Literal["placements", "students", "applications", "attendance", "drives"] = Query(...),
    fmt: Literal["csv", "pdf"] = Query("csv", alias="format"),
    college_id: str | None = Query(None, alias="collegeId"),
    batch_id: str | None = Query(None, alias="batchId"),
    user: Principal = Depends(require_admin),
    service: ReportsService = Depends(get_reports_service),
) -> Response:
    content, media_type, filename = service.export(
        user, report=report, fmt=fmt, college_id=college_id, batch_id=batch_id
    )
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
