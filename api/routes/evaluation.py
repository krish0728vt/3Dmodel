from __future__ import annotations

from fastapi import APIRouter, HTTPException

from evaluation.runner import cases_for_api, latest_report


router = APIRouter(prefix="/api/evaluation", tags=["evaluation"])


@router.get("/latest")
def get_latest_evaluation():
    report = latest_report()
    if report is None:
        return {
            "available": False,
            "message": "No evaluation report has been generated yet.",
            "report": None,
        }
    return {"available": True, "report": report}


@router.get("/cases")
def get_evaluation_cases():
    return cases_for_api()


@router.get("/cases/{case_id}")
def get_evaluation_case(case_id: str):
    for case in cases_for_api():
        if case.case_id == case_id:
            return case
    raise HTTPException(status_code=404, detail=f"Unknown benchmark case: {case_id}")


@router.get("/regressions")
def get_evaluation_regressions():
    report = latest_report()
    if report is None:
        return []
    return report.regressions
