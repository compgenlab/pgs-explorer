from fastapi import APIRouter, Request, BackgroundTasks
from fastapi.responses import HTMLResponse
from apps.core.app_config import templates
from apps.subcohorts.models import SubcohortPlotRequest
from apps.subcohorts.service import process_subcohort_plot
from apps.tasks.service import process_image_request

router = APIRouter(tags=["subcohorts"])

@router.get("/subcohorts", response_class=HTMLResponse)
async def subcohort_view(request: Request):
    return templates.TemplateResponse("subcohorts.html", {"request": request})

@router.post("/api/generate_subcohort_plot")
async def generate_subcohort_plot(request: SubcohortPlotRequest, background_tasks: BackgroundTasks):
    """Generate a subcohort plot with odds ratio calculation as a background task"""
    print(f"Submitting job for task: {request.name}")
    return await process_image_request(
        request_data=request.dict(),
        task_type="subcohort_plot",
        task_name=getattr(request, "name", None),
        processing_function=process_subcohort_plot,
        background_tasks=background_tasks
    )
