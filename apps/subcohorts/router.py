from fastapi import APIRouter, Request, BackgroundTasks
from fastapi.responses import HTMLResponse
from apps.core.config import templates
from apps.session.service import SessionManager
from apps.subcohorts.models import SubcohortPlotRequest
from apps.subcohorts.service import process_subcohort_plot
from apps.tasks.service import process_image_request

router = APIRouter(tags=["subcohorts"])

@router.get("/subcohorts", response_class=HTMLResponse)
async def subcohort_view(request: Request):
    return templates.TemplateResponse("subcohorts.html", {"request": request})

@router.post("/api/generate_subcohort_plot")
async def generate_subcohort_plot(
    request: Request,
    subcohort_request: SubcohortPlotRequest,
    background_tasks: BackgroundTasks
):
    """Generate a subcohort plot with odds ratio calculation as a background task"""
    
    # Get user ID for tracking
    user_id = SessionManager.get_or_create_user_id(request)
    request_to_send = subcohort_request.dict()
    request_to_send["user_id"] = user_id

    # Track this activity
    SessionManager.track_user_activity(
        request,
        "generate_subcohort_plot",
        {
            "name": subcohort_request.name,
            "pgs_ids_count": len(getattr(subcohort_request, 'pgs_ids', [])),
            "cohort": getattr(subcohort_request, 'cohort', 'unknown'),
            "subcohort_type": getattr(subcohort_request, 'subcohort_type', 'unknown')
        }
    )
    
    print(f"Submitting job for task: {subcohort_request.name} - User: {user_id[:8]}...")
    
    return await process_image_request(
        request=request,
        request_data=request_to_send,
        task_type="subcohort_plot",
        task_name=subcohort_request.name,
        processing_function=process_subcohort_plot,
        background_tasks=background_tasks
    )