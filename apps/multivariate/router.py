from fastapi import APIRouter, Request, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse

from apps.core.app_config import templates
from .models import HeatmapRequest, UMAPRequest, SVDRequest, PCARequest, TSNERequest, InteractiveRequest
from .heatmap.service import process_heatmap
from .umap.service import process_umap
from .svd.service import process_svd
from .pca.service import process_pca
from .tsne.service import process_tsne
from .interactive.service import add_interactive_filter_umap, add_interactive_filter_tsne

from apps.tasks.service import process_image_request
from apps.core.models import PlotResponse

router = APIRouter(tags=["multivariate"])

@router.get("/multivariate", response_class=HTMLResponse)
async def multivariate_view(request: Request):
    return templates.TemplateResponse("multivariate.html", {"request": request})

@router.post("/api/generate_heatmap")
async def generate_heatmap(request: HeatmapRequest, background_tasks: BackgroundTasks):
    """Generates a heatmap visualization and saves it as HTML file"""
    print(f"Submitting job for task: {request.name}")
    return await process_image_request(
        request_data=request.dict(),
        task_type="heatmap",
        task_name=getattr(request, "name", None),
        processing_function=process_heatmap,
        background_tasks=background_tasks
    )

@router.post("/api/generate_umap")
async def generate_umap(request: UMAPRequest, background_tasks: BackgroundTasks):
    """Generates a UMAP visualization and saves it as HTML file"""
    print(f"Submitting job for task: {request.name}")
    return await process_image_request(
        request_data=request.dict(),
        task_type="umap",
        task_name=getattr(request, "name", None),
        processing_function=process_umap,
        background_tasks=background_tasks
    )

@router.post("/api/generate_svd_image")
async def generate_svd_image(request: SVDRequest, background_tasks: BackgroundTasks):
    """Routes to the appropriate SVD image generation function based on plot_type"""
    print(f"Submitting job for task: {request.name}")
    return await process_image_request(
        request_data=request.dict(),
        task_type="svd",
        task_name=getattr(request, "name", None),
        processing_function=process_svd,
        background_tasks=background_tasks
    )

@router.post("/api/generate_pca")
async def generate_pca(request: PCARequest, background_tasks: BackgroundTasks):
    """Routes to PCA image generation."""
    print(f"Submitting job for task: {request.name}")
    return await process_image_request(
        request_data=request.dict(),
        task_type="pca",
        task_name=getattr(request, "name", None),
        processing_function=process_pca,
        background_tasks=background_tasks
    )

@router.post("/api/generate_tsne")
async def generate_tsne(request: TSNERequest, background_tasks: BackgroundTasks):
    """Routes to t-SNE image generation."""
    print(f"Submitting job for task: {request.name}")
    return await process_image_request(
        request_data=request.dict(),
        task_type="tsne",
        task_name=getattr(request, "name", None),
        processing_function=process_tsne,
        background_tasks=background_tasks
    )

@router.post("/api/generate_interactive_plot")
def interactive_filter_router(request: InteractiveRequest):
    print(request.plot_type)
    if request.plot_type == "umap":
        output_url = add_interactive_filter_umap(html_file_path=request.plot_url)
    elif request.plot_type == "pca":
        output_url = add_interactive_filter_pca(html_file_path=request.plot_url)
    elif request.plot_type == "tsne":
        output_url = add_interactive_filter_tsne(html_file_path=request.plot_url)
    elif request.plot_type == "svd":
        output_url = add_interactive_filter_sva(html_file_path=request.plot_url)
    else:
        raise HTTPException(status_code=501, detail=f"Interactive plot generation for {request.plot_type} not available at this time.")
    return PlotResponse(plot_url=output_url, table_data=[{}])
