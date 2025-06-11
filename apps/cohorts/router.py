import uuid
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from typing import List, Dict, Any
from pydantic import BaseModel

from apps.core.config import templates
from apps.session.service import SessionManager
from database import db

router = APIRouter(tags=["cohorts"])

class CreateCohortRequest(BaseModel):
    cohort_name: str
    sample_ids: List[str]

@router.get("/cohorts", response_class=HTMLResponse)
async def cohorts_page(request: Request):
    """Render the cohorts management page."""
    user_id = SessionManager.get_or_create_user_id(request)
    cohorts = db.cohorts.get_user_cohorts(user_id)
    
    return templates.TemplateResponse("cohorts.html", {
        "request": request,
        "cohorts": cohorts
    })

@router.post("/api/cohorts")
async def create_cohort(request: Request, cohort_request: CreateCohortRequest):
    """Create a new cohort."""
    user_id = SessionManager.get_or_create_user_id(request)
    
    # Validate sample IDs exist in your database
    valid_sample_ids = db.ancestry.get_valid_sample_ids(cohort_request.sample_ids)
    if not valid_sample_ids:
        raise HTTPException(status_code=400, detail="No valid sample IDs provided")
    
    # Create cohort
    cohort_id = str(uuid.uuid4())
    db.cohorts.create_cohort(cohort_id, user_id, cohort_request.cohort_name, valid_sample_ids)
    
    # Track activity
    SessionManager.track_user_activity(request, "create_cohort", {
        "cohort_name": cohort_request.cohort_name,
        "sample_count": len(valid_sample_ids)
    })
    
    return {
        "status": "success",
        "cohort_id": cohort_id,
        "cohort_name": cohort_request.cohort_name,
        "sample_count": len(valid_sample_ids)
    }

@router.get("/api/cohorts")
async def list_cohorts(request: Request):
    """List user's cohorts."""
    user_id = SessionManager.get_or_create_user_id(request)
    cohorts = db.cohorts.get_user_cohorts(user_id)
    return {"cohorts": cohorts}

@router.delete("/api/cohorts/{cohort_id}")
async def delete_cohort(request: Request, cohort_id: str):
    """Delete a cohort."""
    user_id = SessionManager.get_or_create_user_id(request)
    deleted = db.cohorts.delete_cohort(cohort_id, user_id)
    
    if not deleted:
        raise HTTPException(status_code=404, detail="Cohort not found")
    
    return {"status": "success", "message": "Cohort deleted"}
