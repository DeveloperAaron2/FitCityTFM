from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database import get_supabase_client

router = APIRouter(prefix="/prs", tags=["reports"])


class ReportCreate(BaseModel):
    reporter_id: str
    reason: str = "weight_mismatch"


# ── POST /prs/{pr_id}/report ──────────────────────────────────────────────────

@router.post("/{pr_id}/report")
def report_pr(pr_id: str, body: ReportCreate):
    """
    Report a PR for suspicious weight.
    - A user cannot report the same PR twice.
    - A user cannot report their own PR.
    """
    db = get_supabase_client()

    # 1. Check that the PR exists and get the owner
    pr_res = (
        db.table("lifting_prs")
        .select("id, user_id")
        .eq("id", pr_id)
        .limit(1)
        .execute()
    )
    if not pr_res.data:
        raise HTTPException(status_code=404, detail="PR no encontrado.")

    pr_owner = pr_res.data[0]["user_id"]

    # 2. Cannot report your own PR
    if body.reporter_id == pr_owner:
        raise HTTPException(
            status_code=403,
            detail="No puedes reportar tu propio PR."
        )

    # 3. Check for duplicate report
    existing_report = (
        db.table("pr_reports")
        .select("id")
        .eq("pr_id", pr_id)
        .eq("reporter_id", body.reporter_id)
        .limit(1)
        .execute()
    )
    if existing_report.data:
        raise HTTPException(
            status_code=409,
            detail="Ya has reportado este PR anteriormente."
        )

    # 4. Create the report
    report_payload = {
        "pr_id": pr_id,
        "reporter_id": body.reporter_id,
        "reason": body.reason,
    }
    res = db.table("pr_reports").insert(report_payload).execute()

    if not res.data:
        raise HTTPException(status_code=400, detail="No se pudo crear el reporte.")

    # 5. Get updated report count
    count_res = (
        db.table("pr_reports")
        .select("id", count="exact")
        .eq("pr_id", pr_id)
        .execute()
    )
    report_count = count_res.count if count_res.count is not None else 0

    return {
        "success": True,
        "message": "Reporte enviado correctamente. Gracias por ayudar a mantener la integridad de la comunidad.",
        "report_count": report_count,
    }


# ── GET /prs/{pr_id}/reports/count ────────────────────────────────────────────

@router.get("/{pr_id}/reports/count")
def get_pr_report_count(pr_id: str):
    """Get the number of reports for a specific PR."""
    db = get_supabase_client()

    count_res = (
        db.table("pr_reports")
        .select("id", count="exact")
        .eq("pr_id", pr_id)
        .execute()
    )
    report_count = count_res.count if count_res.count is not None else 0

    return {
        "pr_id": pr_id,
        "report_count": report_count,
        "is_suspicious": report_count >= 3,
    }
