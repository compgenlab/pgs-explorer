from fastapi import APIRouter, Request, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse

from apps.core.config import templates
from apps.session.service import SessionManager
from .models import HeatmapRequest, UMAPRequest, SVDRequest, PCARequest, TSNERequest, InteractiveRequest
from .heatmap import process_heatmap
from .umap import process_umap
from .svd import process_svd
from .pca import process_pca
from .tsne import process_tsne
from .interactive import add_interactive_filter_umap, add_interactive_filter_tsne

from apps.tasks.service import process_image_request
from apps.core.models import PlotResponse

router = APIRouter(tags=["multivariate"])

@router.get("/multivariate", response_class=HTMLResponse)
async def multivariate_view(request: Request):
    return templates.TemplateResponse("multivariate.html", {"request": request})

@router.post("/api/generate_heatmap")
async def generate_heatmap(
    request: Request,
    heatmap_request: HeatmapRequest,
    background_tasks: BackgroundTasks
):
    """Generates a heatmap visualization and saves it as HTML file"""
    
    # Get user ID for tracking
    user_id = SessionManager.get_or_create_user_id(request)
    request_to_pass=heatmap_request.dict()
    request_to_pass["user_id"] = user_id

    # Track this activity
    SessionManager.track_user_activity(
        request,
        "generate_heatmap",
        {
            "name": heatmap_request.name,
            "pgs_ids_count": len(getattr(heatmap_request, 'pgs_ids', [])),
            "cohort": getattr(heatmap_request, 'cohort', 'unknown')
        }
    )

    print(f"Submitting job for task: {heatmap_request.name} - User: {user_id[:8]}...")
    
    return await process_image_request(
        request=request,
        request_data=request_to_pass,
        task_type="heatmap",
        task_name=heatmap_request.name,
        processing_function=process_heatmap,
        background_tasks=background_tasks
    )

@router.post("/api/generate_umap")
async def generate_umap(
    request: Request,
    umap_request: UMAPRequest,
    background_tasks: BackgroundTasks
):
    """Generates a UMAP visualization and saves it as HTML file"""
    
    # Get user ID for tracking
    user_id = SessionManager.get_or_create_user_id(request)
    request_to_pass=umap_request.dict()
    request_to_pass["user_id"] = user_id

    # Track this activity
    SessionManager.track_user_activity(
        request,
        "generate_umap",
        {
            "name": umap_request.name,
            "pgs_ids_count": len(getattr(umap_request, 'pgs_ids', [])),
            "cohort": getattr(umap_request, 'cohort', 'unknown')
        }
    )

    print(f"Submitting job for task: {umap_request.name} - User: {user_id[:8]}...")
    
    return await process_image_request(
        request=request,
        request_data=request_to_pass,
        task_type="umap",
        task_name=umap_request.name,
        processing_function=process_umap,
        background_tasks=background_tasks
    )

@router.post("/api/generate_svd_image")
async def generate_svd_image(
    request: Request,
    svd_request: SVDRequest,
    background_tasks: BackgroundTasks
):
    """Routes to the appropriate SVD image generation function based on plot_type"""
    
    # Get user ID for tracking
    user_id = SessionManager.get_or_create_user_id(request)
    request_to_pass=svd_request.dict()
    request_to_pass["user_id"] = user_id
    # Track this activity
    SessionManager.track_user_activity(
        request,
        "generate_svd",
        {
            "name": svd_request.name,
            "plot_type": getattr(svd_request, 'plot_type', 'unknown'),
            "cohort": getattr(svd_request, 'cohort', 'unknown')
        }
    )
    
    print(f"Submitting job for task: {svd_request.name} - User: {user_id[:8]}...")
    
    return await process_image_request(
        request=request,
        request_data=request_to_pass,
        task_type="svd",
        task_name=svd_request.name,
        processing_function=process_svd,
        background_tasks=background_tasks
    )

@router.post("/api/generate_pca")
async def generate_pca(
    request: Request,
    pca_request: PCARequest,
    background_tasks: BackgroundTasks
):
    """Routes to PCA image generation."""
    
    # Get user ID for tracking
    user_id = SessionManager.get_or_create_user_id(request)
    request_to_pass=pca_request.dict()
    request_to_pass["user_id"] = user_id

    # Track this activity
    SessionManager.track_user_activity(
        request,
        "generate_pca",
        {
            "name": pca_request.name,
            "pgs_ids_count": len(getattr(pca_request, 'pgs_ids', [])),
            "cohort": getattr(pca_request, 'cohort', 'unknown')
        }
    )
    
    print(f"Submitting job for task: {pca_request.name} - User: {user_id[:8]}...")
    
    return await process_image_request(
        request=request,
        request_data=request_to_pass,
        task_type="pca",
        task_name=pca_request.name,
        processing_function=process_pca,
        background_tasks=background_tasks
    )

@router.post("/api/generate_tsne")
async def generate_tsne(
    request: Request,
    tsne_request: TSNERequest,
    background_tasks: BackgroundTasks
):
    """Routes to t-SNE image generation."""
    
    # Get user ID for tracking
    user_id = SessionManager.get_or_create_user_id(request)
    request_to_pass=tsne_request.dict()
    request_to_pass["user_id"] = user_id

    # Track this activity
    SessionManager.track_user_activity(
        request,
        "generate_tsne",
        {
            "name": tsne_request.name,
            "pgs_ids_count": len(getattr(tsne_request, 'pgs_ids', [])),
            "cohort": getattr(tsne_request, 'cohort', 'unknown')
        }
    )
    
    print(f"Submitting job for task: {tsne_request.name} - User: {user_id[:8]}...")
    
    return await process_image_request(
        request=request,
        request_data=request_to_pass,
        task_type="tsne",
        task_name=tsne_request.name,
        processing_function=process_tsne,
        background_tasks=background_tasks
    )

@router.post("/api/generate_interactive_plot")
def interactive_filter_router(
    request: Request,
    interactive_request: InteractiveRequest
):
    """Routes to interactive image generation."""
    
    # Get user ID for tracking
    user_id = SessionManager.get_or_create_user_id(request)
    request_to_pass=interactive_request.dict()
    request_to_pass["user_id"] = user_id

    # Track this activity
    SessionManager.track_user_activity(
        request,
        "generate_interactive_plot",
        {
            "plot_type": interactive_request.plot_type,
            "plot_url": interactive_request.plot_url
        }
    )
    
    print(f"Submitting job to apply interactive filters for plot type: {interactive_request.plot_type} - User: {user_id[:8]}...")
    
    if interactive_request.plot_type == "umap":
        output_url = add_interactive_filter_umap(html_file_path=interactive_request.plot_url)
    elif interactive_request.plot_type == "pca":
        output_url = add_interactive_filter_pca(html_file_path=interactive_request.plot_url)
    elif interactive_request.plot_type == "tsne":
        output_url = add_interactive_filter_tsne(html_file_path=interactive_request.plot_url)
    elif interactive_request.plot_type == "svd":
        output_url = add_interactive_filter_sva(html_file_path=interactive_request.plot_url)
    else:
        raise HTTPException(status_code=501, detail=f"Interactive plot generation for {interactive_request.plot_type} not available at this time.")
    
    return PlotResponse(plot_url=output_url, table_data=[{}])