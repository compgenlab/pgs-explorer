from fastapi import APIRouter, Request, BackgroundTasks
from fastapi.responses import HTMLResponse
from apps.core.app_config import templates
from apps.distribution.models import DistributionRequest
from apps.distribution.service import process_distribution
from apps.tasks.service import process_image_request

router = APIRouter(tags=["distribution"])

@router.get("/distribution", response_class=HTMLResponse)
async def distribution_view(request: Request):
    return templates.TemplateResponse("distribution.html", {"request": request})

@router.post("/api/generate_distribution")
async def generate_distribution(request: DistributionRequest, background_tasks: BackgroundTasks):
    """Generate distribution plots on the backend as a background task"""
    print(f"Submitting job for task: {request.name}")
    return await process_image_request(
        request_data=request.dict(),
        task_type="distribution",
        task_name=getattr(request, "name", None),
        processing_function=process_distribution,
        background_tasks=background_tasks
    )
