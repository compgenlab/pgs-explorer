import uuid
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from typing import List, Dict, Any
from pydantic import BaseModel

from apps.core.config import templates
from apps.session.service import SessionManager
from database import db

import requests

router = APIRouter(tags=["cohorts"])

class CreateCohortRequest(BaseModel):
    cohort_name: str
    sample_ids: List[str]

@router.get("/cohorts", response_class=HTMLResponse)
async def cohorts_page(request: Request):
    """Render the cohorts management page."""
    user_id = SessionManager.get_or_create_user_id(request)
    cohorts = db.active_db.cohorts.get_user_cohorts(user_id)
    
    return templates.TemplateResponse("cohorts.html", {
        "request": request,
        "cohorts": cohorts
    })

@router.post("/api/cohorts")
async def create_cohort(request: Request, cohort_request: CreateCohortRequest):
    """Create a new cohort."""
    user_id = SessionManager.get_or_create_user_id(request)
    
    # Validate sample IDs exist in your database
    valid_sample_ids = db.active_db.ancestry.get_valid_sample_ids(cohort_request.sample_ids)
    if not valid_sample_ids:
        raise HTTPException(status_code=400, detail="No valid sample IDs provided")
    
    # Create cohort
    cohort_id = str(uuid.uuid4())
    db.active_db.cohorts.create_cohort(cohort_id, user_id, cohort_request.cohort_name, valid_sample_ids)
    
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

@router.get("/api/cohorts/import-biobank")
async def import_cohorts(request: Request):
    cohort_id = request.query_params.get("cohort_id")
    token = request.query_params.get("token")
    callback = request.query_params.get("api_base_url")
    dataset = request.query_params.get("dataset")

    error = ""
    cohort_name = ""
    sample_ids = []

    headers = {"Authorization": "Basic %s" % token}

    samples_url = "%s/cohorts/%s/participant-ids" % (callback, cohort_id)
    cohort_url = "%s/cohorts/%s/" % (callback, cohort_id)

    response_samples = None
    attempts = 0
    while not response_samples or (response_samples.status_code != 200 and attempts < 3):
        print(f"Requesting API call: {samples_url}")
        response_samples = requests.get(samples_url, headers=headers)
        attempts += 1
    
    if response_samples and response_samples.status_code == 200:
        sample_ids = response_samples.json()
        # print(sample_ids)

        response_cohort = None
        attempts = 0
        while not response_cohort or (response_cohort.status_code != 200 and attempts < 3):
            response_cohort = requests.get(cohort_url, headers=headers)
            attempts += 1

        if response_cohort and response_cohort.status_code == 200:
            cohort_json = response_cohort.json()
            cohort_name = cohort_json["name"]
            print(cohort_json)
        elif response_cohort:
            error = "Unable to retrieve cohort information (%s)" % response_cohort.status_code
        else:
            error = "Unable to retrieve cohort information (unknown error)"

    elif response_samples:
        error = "Unable to retrieve cohort samples (%s)" % response_samples.status_code
    else:
        error = "Unable to retrieve cohort samples (unknown error)"

    valid_sample_ids = sample_ids

    if not error:
        user_id = SessionManager.get_or_create_user_id(request)
        existing_cohort = db.active_db.cohorts.get_cohort(cohort_id, user_id)
        
        print("Existing cohort: %s (None?: %s, not none?: %s)" % (existing_cohort, existing_cohort is None, not existing_cohort is None))

        if existing_cohort is None:
            print("Cohort does not exist!")
            valid_sample_ids = db.active_db.ancestry.get_valid_sample_ids(sample_ids)
            if not valid_sample_ids:
                # raise HTTPException(status_code=400, detail="No valid sample IDs provided")
                error = "No valid sample IDs provided"
            else:
                db.active_db.cohorts.create_cohort(cohort_id, user_id, cohort_name, valid_sample_ids)
                # return RedirectResponse(url="/cohorts", status_code=307)
        else:
            print("Cohort exists")
            error = "Cohort with the ID: %s already exists. (Try deleting it first!)" % cohort_id


    return templates.TemplateResponse("cohorts-import.html", {
        "request": request,
        "cohort_id": cohort_id,
        "cohort_name": cohort_name,
        "sample_id_count": len(sample_ids),
        "valid_sample_id_count": len(valid_sample_ids),
        "dataset": dataset,
        "error": error,
        })

@router.get("/api/cohorts")
async def list_cohorts(request: Request):
    """List user's cohorts."""
    user_id = SessionManager.get_or_create_user_id(request)
    cohorts = db.active_db.cohorts.get_user_cohorts(user_id)
    return {"cohorts": cohorts}

@router.delete("/api/cohorts/{cohort_id}")
async def delete_cohort(request: Request, cohort_id: str):
    """Delete a cohort."""
    user_id = SessionManager.get_or_create_user_id(request)
    deleted = db.active_db.cohorts.delete_cohort(cohort_id, user_id)
    
    if not deleted:
        raise HTTPException(status_code=404, detail="Cohort not found")
    
    return {"status": "success", "message": "Cohort deleted"}
