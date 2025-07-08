from fastapi import APIRouter, Request, BackgroundTasks
from fastapi.responses import HTMLResponse
from apps.core.config import templates
from apps.distribution.models import DistributionRequest
from apps.distribution.service import process_distribution
from apps.tasks.service import process_image_request
from apps.session.service import SessionManager

router = APIRouter(tags=["search"])

@router.get("/search", response_class=HTMLResponse)
async def distribution_view(request: Request):
    return templates.TemplateResponse("search.html", {"request": request})


@router.post("/api/submit_search")
async def submit_search(
    request: Request,
    distribution_request: DistributionRequest,
    background_tasks: BackgroundTasks
):

    # Get user ID for tracking
    user_id = SessionManager.get_or_create_user_id(request)
    request_to_pass = distribution_request.dict()
    request_to_pass["user_id"] = user_id
    print(f"User id: {user_id}")

    # Track this activity
    SessionManager.track_user_activity(
        request,
        "submit_search",
        {
            "name": distribution_request.name,
            "pgs_ids_count": len(getattr(distribution_request, 'pgs_ids', [])),
           # "cohort": getattr(distribution_request, 'cohort', 'unknown')
        }
    )
    
    print(f"Submitting job for task: {distribution_request.name} - User: {user_id[:8]}...")
    
    return await process_image_request(
        request=request,  # Pass the FastAPI Request object
        request_data=request_to_pass,
        task_type="distribution", 
        task_name=distribution_request.name,
        processing_function=process_search,
        background_tasks=background_tasks
    )

