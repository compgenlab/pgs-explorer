from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, validator
from typing import List, Optional, Dict, Any
import sqlite3
import pandas as pd
import uvicorn
import io
import gzip
import os
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.cluster.hierarchy import linkage, dendrogram
from scipy import stats
from sklearn.manifold import TSNE
from collections import defaultdict
import json
from pydantic import BaseModel
from typing import List, Optional, Literal
from datetime import datetime
import random 
import hashlib
import umap
import time
import uuid 
from bs4 import BeautifulSoup

# Initialize FastAPI
app = FastAPI(title="PGS Visualizer", description="Tool for visualizing Polygenic Score data")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)

# Setup templates and static files
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/temp", StaticFiles(directory="temp"), name="temp")

# SQLite Database Setup
DB_PATH = "/data/dev/db/pgs_data_with_morphology.db"
TASK_DB_PATH = "/data/dev/db/tasks.db"

def init_task_db():
    # Ensure the directory exists
    os.makedirs(os.path.dirname(TASK_DB_PATH), exist_ok=True)

    conn = sqlite3.connect(TASK_DB_PATH)
    cursor = conn.cursor()
    
    # Create tasks table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS image_tasks (
        task_id TEXT PRIMARY KEY,
        task_type TEXT,
        name TEXT,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        completed_at TEXT,
        result_path TEXT,
        error TEXT,
        request_data TEXT NOT NULL
    )
    ''')
    
    conn.commit()
    conn.close()

# Initialize DB on startup
init_task_db()

# Classes for API request/response models
class CohortRequest(BaseModel):
    sample_ids: List[str]
    color: str
    name: Optional[str] = None

class ScoreComparisonRequest(BaseModel):
    pgs_ids: List[str]
    sample_ids: List[str]
    colors: List[str]
    names: List[str]

class DistributionRequest(BaseModel):
    analysis_type: str  # 'cohort' or 'score'
    chart_type: str  # 'density', 'histogram', or 'boxplot'
    plot_title: str
    score_type: str
    
    # For cohort analysis
    pgs_id: Optional[str] = None
    cohorts: Optional[List[CohortRequest]] = None
    
    # For score comparison
    cohort_name: Optional[str] = None
    pgs_comparison: Optional[ScoreComparisonRequest] = None

    # Job name
    name: Optional[str] = None

class PGSRequestItem(BaseModel):
    pgs_id: str
    color: str
    name: Optional[str] = None

class PGSRequest(BaseModel):
    pgs_cohorts: List[PGSRequestItem]

class Subcohort(BaseModel):
    name: str
    color: str
    sampleIds: List[str]

class HeatmapRequest(BaseModel):
    score_type: str
    max_pgs_ids: int = 5500
    std_dev_threshold: float = 3.0
    dendrogram_view: bool = False
    pgs_ids: Optional[List[str]] = None
    cohort: Optional[str] = None
    subcohorts: Optional[List[Subcohort]] = None
    # Job name
    name: Optional[str] = None

class UMAPRequest(BaseModel):
    score_type: str
    n_neighbors: int
    min_dist: float  
    pgs_ids: Optional[List[str]] = None
    cohort: Optional[str] = None
    view_type: str = "sample"  
    # Job name
    name: Optional[str] = None

class SVDRequest(BaseModel):
    score_type: str
    pgs_ids: Optional[List[str]] = None
    cohort: Optional[str] = None
    plot_type: str = "combined"
    perspective: Optional[str] = "sample"
    max_vectors: Optional[int] = 20 
    # Job name
    name: Optional[str] = None
    @validator('plot_type')
    def validate_plot_type(cls, v):
        allowed_types = ["scree", "biplot", "component_weights", "heatmap", "combined"]
        if v not in allowed_types:
            raise ValueError(f"plot_type must be one of {allowed_types}")
        return v
    
    @validator('perspective')
    def validate_perspective(cls, v):
        if v is not None:
            allowed_perspectives = ["sample", "score"]
            if v not in allowed_perspectives:
                raise ValueError(f"perspective must be one of {allowed_perspectives}")
        return v
    
    @validator('max_vectors')
    def validate_max_vectors(cls, v):
        if v is not None:
            if v < 5 or v > 100:
                raise ValueError("max_vectors must be between 5 and 50")
        return v
    
class PCARequest(BaseModel):
    score_type: str
    pgs_ids: Optional[List[str]] = None
    cohort: Optional[str] = None
    perspective: Optional[str] = "sample"
    x_axis: str = "1"
    y_axis: str = "2"
    include_variance: bool = True
    # Job name
    name: Optional[str] = None

class TSNERequest(BaseModel):
    score_type: str
    pgs_ids: Optional[List[str]] = None
    cohort: Optional[str] = None
    perspective: Optional[str] = "sample"
    perplexity: int
    iterations: int
    learning_rate: int
    # Job name
    name: Optional[str] = None

class SampleData(BaseModel):
    SAMPLE_ID: str
    SCORE: float

class Subcohort(BaseModel):
    name: str
    color: str
    sample_ids: List[str]
    active: bool = True

class SubcohortPlotRequest(BaseModel):
    pgs_id: str
    score_type: str
    base_cohort: str
    plot_title: Optional[str] = None
    normalize_bins: bool = False
    subcohorts: List[Subcohort] = []
    
    # Odds Ratio configuration
    display_or: bool = False
    or_calculation_type: Optional[str] = None  # "bin", "quantile", "threshold", "decileBaseline", "decileCumulative"
    bin_size: Optional[int] = None
    quantile_count: Optional[int] = None
    threshold_value: Optional[float] = None
    decile_count: Optional[int] = None

    # Job name
    name: Optional[str] = None

class PlotResponse(BaseModel):
    plot_url: str
    table_data: List[Dict[str, Any]]

class InteractiveRequest(BaseModel):
    plot_type: str = "umap"
    plot_url: str

class TaskResponse(BaseModel):
    task_id: str
    task_type: str
    name: Optional[str] = None
    status: str
    created_at: str

# On startup, clear old tasks
@app.on_event("startup")
async def startup_recovery():
    """Mark abandoned processing/queued tasks as failed when server starts up"""
    try:
        conn = sqlite3.connect(TASK_DB_PATH)
        cursor = conn.cursor()
        
        # Find all tasks in processing or queued state
        cursor.execute(
            "SELECT task_id FROM image_tasks WHERE status IN ('processing', 'queued')"
        )
        abandoned_tasks = cursor.fetchall()
        
        if abandoned_tasks:
            # Mark them as failed
            for task in abandoned_tasks:
                task_id = task[0]
                cursor.execute(
                    "UPDATE image_tasks SET status = ?, error = ?, completed_at = ? WHERE task_id = ?",
                    ("failed", "Task abandoned due to server restart", datetime.now().isoformat(), task_id)
                )
            
            conn.commit()
            print(f"Marked {len(abandoned_tasks)} abandoned tasks as failed during startup")
        
        conn.close()
    except Exception as e:
        print(f"Error during startup recovery: {str(e)}")

# Frontend routes
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/multivariate", response_class=HTMLResponse)
async def multivariate_view(request: Request):
    return templates.TemplateResponse(
        "multivariate.html", 
        {"request": request}
    )

@app.get("/distribution", response_class=HTMLResponse)
async def distribution_view(request: Request):
    return templates.TemplateResponse("distribution.html", {"request": request})

@app.get("/subcohorts", response_class=HTMLResponse)
async def subcohort_view(request: Request):
    return templates.TemplateResponse("subcohorts.html", {"request": request})

@app.get("/metadata", response_class=HTMLResponse)
async def metadata_view(request: Request):
    return templates.TemplateResponse("metadata.html", {"request": request})

@app.get("/tasks", response_class=HTMLResponse)
async def tasks_page(request: Request):
    return templates.TemplateResponse("tasks.html", {"request": request})

# API Routes
@app.get("/api/metadata/{pgs_id}")
def get_metadata(pgs_id: str):
    """Fetches metadata for a given PGS_ID from the `pgs_metadata` table."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Fetch metadata for the given PGS_ID
    cursor.execute("SELECT * FROM pgs_metadata WHERE PGS_ID = ?", (pgs_id,))
    metadata = cursor.fetchone()

    # Fetch column names
    cursor.execute("PRAGMA table_info(pgs_metadata);")
    columns = [col[1] for col in cursor.fetchall()]

    conn.close()

    if not metadata:
        raise HTTPException(status_code=404, detail=f"Metadata not found for PGS_ID '{pgs_id}'")

    # Combine column names and metadata into a dictionary
    metadata_dict = dict(zip(columns, metadata))

    return {"metadata": metadata_dict}

@app.get("/api/pgs_list")
def get_pgs_list():
    """Fetches PGS IDs from pgs_metadata."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT DISTINCT pgs_id FROM scores ORDER BY PGS_ID")
    pgs_list = [row[0] for row in cursor.fetchall()]
    
    conn.close()
    return {"pgs": pgs_list}

@app.get("/api/score_types")
def get_score_types():
    """Fetches all distinct score types available in the database."""
    print("hi nadia")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT DISTINCT SCORE_TYPE FROM scores ORDER BY SCORE_TYPE")
    score_types = [row[0] for row in cursor.fetchall()]
    
    conn.close()
    return {"score_types": score_types}

@app.get("/api/score_types/{pgs_id}")
def get_score_types_for_pgs(pgs_id: str):
    """Fetches distinct score types for a given PGS_ID from the `scores` table."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get unique score types for the given PGS_ID
    cursor.execute(
        "SELECT DISTINCT SCORE_TYPE FROM scores WHERE PGS_ID = ? ORDER BY SCORE_TYPE", 
        (pgs_id,)
    )
    score_types = [row[0] for row in cursor.fetchall()]

    conn.close()

    if not score_types:
        raise HTTPException(status_code=404, detail=f"No score types found for PGS_ID '{pgs_id}'")

    return {"score_types": score_types}

@app.get("/api/pgs_data/{pgs_id}")
def get_pgs_data(pgs_id: str):
    """Fetches sample scores from `scores` for a given PGS_ID."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Fetch sample score data
    cursor.execute(
        "SELECT SAMPLE_ID, SCORE_TYPE, SCORE FROM scores WHERE PGS_ID = ?", 
        (pgs_id,)
    )
    scores = cursor.fetchall()

    # Convert scores to list of dictionaries
    scores_list = [
        {"SAMPLE_ID": row[0], "SCORE_TYPE": row[1], "SCORE": row[2]} 
        for row in scores
    ]

    conn.close()

    return {"scores": scores_list}

@app.post("/api/generate_tsne")
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

def process_tsne(request_data):
    try:
        # Create temp directory if it doesn't exist
        os.makedirs("temp", exist_ok=True)

        # Extract parameters from request_data
        score_type = request_data["score_type"]
        pgs_ids = request_data.get("pgs_ids")
        cohort = request_data.get("cohort")
        perspective = request_data.get("perspective", "sample")
        perplexity = request_data["perplexity"]
        iterations = request_data["iterations"]
        learning_rate = request_data["learning_rate"]

        # Generate hash for caching
        request_hash = generate_tsne_hash(
            score_type,
            pgs_ids,
            cohort,
            perspective,
            perplexity,
            iterations,
            learning_rate
        )

        # Check for existing cached file
        for filename in os.listdir("temp"):
            if filename.endswith(".html") and request_hash in filename and "tsne" in filename:
                cached_filepath = os.path.join("temp", filename)
                os.utime(cached_filepath)
                print(f"Using cached t-SNE visualization: {filename}")
                return f"/temp/{filename}"

        # Perform t-SNE analysis
        tsne_result, pgs_ids, sample_ids = perform_tsne_analysis(
            score_type=score_type,
            specific_pgs_ids=pgs_ids,
            cohort=cohort,
            perspective=perspective,
            perplexity=perplexity,
            n_iter=iterations,
            learning_rate=learning_rate
        )

        # Generate filename with hash
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        score_type_safe = score_type.replace("/", "_").replace("\\", "_")
        cohort_indicator = f"{cohort}_" if cohort and cohort != "ALL" else ""
        filename = f"tsne_{cohort_indicator}{score_type_safe}_{request_hash}_{timestamp}.html"
        filepath = os.path.join("temp", filename)

        # Generate the appropriate visualization
        if perspective == "score":
            fig = generate_tsne_score(tsne_result, pgs_ids=pgs_ids)
        else:
            fig = generate_tsne_sample(tsne_result, sample_ids=sample_ids)

        # Save the figure to HTML
        fig.write_html(
            filepath,
            include_plotlyjs='cdn',
            include_mathjax=False,
            config={
                'displayModeBar': True,
                'responsive': True
            }
        )

        return f"/temp/{filename}"

    except Exception as e:
        print(f"Error generating t-SNE visualization: {str(e)}")
        raise e

def perform_tsne_analysis(score_type, specific_pgs_ids, cohort, perspective, perplexity, n_iter, learning_rate):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get PGS IDs
    if specific_pgs_ids:
        placeholders = ','.join(['?'] * len(specific_pgs_ids))
        cursor.execute(f"""
            SELECT DISTINCT PGS_ID 
            FROM scores 
            WHERE SCORE_TYPE = ?
            AND PGS_ID IN ({placeholders})
            ORDER BY PGS_ID
        """, [score_type] + specific_pgs_ids)
    else:
        pgs_ids = None
        print("all pgs")

    pgs_ids = [row[0] for row in cursor.fetchall()]
    print(f"Selected {len(pgs_ids)} PGS_IDs.")

    # --- Get sample IDs ---
    if cohort and cohort != "ALL":
        cursor.execute("SELECT sample_ids FROM ancestry_groups WHERE population = ?", (cohort,))
        cohort_result = cursor.fetchone()
        sample_ids = json.loads(cohort_result[0])
        print(f"Filtering to {len(sample_ids)} samples from {cohort} population")
    else:
        sample_ids = None
        print("all samples")

    # --- Matrix build ---
    matrix, pgs_ids = get_matrix(
        sample_ids=sample_ids,
        pgs_ids=pgs_ids,
        score_type=score_type,
        output_format="numpy",
        handle_missing=True
    )

    # --- Run t-SNE ---
    tsne = TSNE(
        n_components=2,
        perplexity=perplexity,
        n_iter=n_iter,  # Use n_iter as passed from the calling function
        learning_rate=learning_rate,
        random_state=42
    )
    
    # Transform matrix based on perspective
    if perspective == "score" and matrix.shape[0] > matrix.shape[1]:
        # Transpose matrix for score-centered analysis (if samples > scores)
        matrix = matrix.T
        tsne_result = tsne.fit_transform(matrix)
        return tsne_result, pgs_ids, sample_ids
    else:
        # For sample-centered or already transposed matrices
        tsne_result = tsne.fit_transform(matrix)
        return tsne_result, pgs_ids, sample_ids

def generate_tsne_sample(tsne_result, sample_ids):
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=tsne_result[:, 0],
            y=tsne_result[:, 1],
            mode="markers",
            marker=dict(size=6, color="blue", opacity=0.7),
            text=sample_ids,
            hoverinfo="text",
            name="Samples"
        )
    )
    fig.update_layout(
        title="t-SNE Projection (Samples as Points)",
        xaxis_title="t-SNE 1",
        yaxis_title="t-SNE 2",
        showlegend=False
    )
    return fig

def generate_tsne_score(tsne_result, pgs_ids):
    pgs_metadata = fetch_pgs_metadata(pgs_ids)
    hover_text = []
    for pgs_id in pgs_ids:
        meta = pgs_metadata.get(pgs_id, {})
        if not meta:
            print(f"Missing metadata for {pgs_id}")
        hover_text.append(
            f"PGS ID: {pgs_id}<br>"
            f"Name: {meta.get('PGS_Name', 'N/A')}<br>"
            f"Trait: {meta.get('Reported_Trait', 'N/A')}<br>"
            f"Publication: {meta.get('Publication_ID', 'N/A')}"
        )

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=tsne_result[:, 0],
            y=tsne_result[:, 1],
            mode="markers",
            marker=dict(size=6, color="red", opacity=0.7),
            text=hover_text,
            hoverinfo="text",
            name="PGS Scores"
        )
    )
    fig.update_layout(
        title="t-SNE Projection (PGS Scores as Points)",
        xaxis_title="t-SNE 1",
        yaxis_title="t-SNE 2",
        showlegend=False
    )
    return fig

def generate_tsne_hash(score_type, pgs_ids, cohort, perspective, perplexity, iterations, learning_rate):
    hash_input = json.dumps({
        "score_type": score_type,
        "pgs_ids": pgs_ids,
        "cohort": cohort,
        "perspective": perspective,
        "perplexity": perplexity,
        "iterations": iterations,
        "learning_rate": learning_rate
    }, sort_keys=True)
    print(hash_input)
    print(hashlib.md5(hash_input.encode()).hexdigest())
    return hashlib.md5(hash_input.encode()).hexdigest()

@app.post("/api/generate_heatmap")
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

def process_heatmap(request_data):
    try:
        # Create temp directory if it doesn't exist
        os.makedirs("temp", exist_ok=True)
        
        # Extract parameters from request_data
        score_type = request_data["score_type"]
        std_dev_threshold = request_data["std_dev_threshold"]
        dendrogram_view = request_data["dendrogram_view"]
        pgs_ids = request_data["pgs_ids"]
        cohort = request_data["cohort"]
        subcohorts = request_data["subcohorts"]
        max_pgs_ids = request_data.get("max_pgs_ids")
        
        # Generate hash based on request parameters
        request_hash = generate_heatmap_hash(
            score_type,
            std_dev_threshold,
            dendrogram_view,
            pgs_ids,
            cohort,
            subcohorts 
        )

        # Check if we already have a file with this hash
        for filename in os.listdir("temp"):
            if filename.endswith(".html") and request_hash in filename and "heatmap" in filename:
                # Found a cached file, update its access time
                cached_filepath = os.path.join("temp", filename)
                os.utime(cached_filepath)
                
                print(f"Using cached heatmap: {filename}")
                
                # Return file path with empty statistics
                return f"/temp/{filename}"

        # Check and clean up temp directory if needed
        # cleanup_temp_files(max_size_in_gb=10)  

        # Generate filename with hash for future cache hits
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        score_type_safe = score_type.replace("/", "_").replace("\\", "_")
        cohort_indicator = f"{cohort}_" if cohort and cohort != "ALL" else ""
        filename = f"heatmap_{cohort_indicator}{score_type_safe}_{request_hash}_{timestamp}.html"
        filepath = os.path.join("temp", filename)
        
        # Generate the heatmap
        print(f"Large dataset detected. Using static heatmap generator.")
        fig, stats = generate_static_heatmap_for_large_dataset(
            score_type=score_type,
            max_pgs_ids=max_pgs_ids,
            std_dev_threshold=std_dev_threshold,
            dendrogram_view=dendrogram_view,
            specific_pgs_ids=pgs_ids,
            cohort=cohort,
            subcohorts=subcohorts 
        )
        
        # Save the heatmap
        fig.write_html(
            filepath,
            include_plotlyjs='cdn',
            include_mathjax=False,
            config={
                'displayModeBar': False,
                'responsive': True
            }
        )

        # Return the file path
        return f"/temp/{filename}"
        
    except Exception as e:
        # Log the error
        print(f"Error generating heatmap: {str(e)}")
        raise e

def generate_static_heatmap_for_large_dataset(score_type='Z_norm2', max_pgs_ids=5500, 
                                             std_dev_threshold=3, dendrogram_view=False, 
                                             specific_pgs_ids=None, cohort=None, subcohorts=None):
    """
    Generate a simplified static heatmap for very large datasets.
    Similar to the regular heatmap but optimized for file size and rendering performance.
    
    Parameters:
    - score_type: The SCORE_TYPE to filter on
    - max_pgs_ids: Maximum number of PGS_IDs to include
    - std_dev_threshold: Number of standard deviations beyond which to cap outliers
    - dendrogram_view: If True, simplifies visualization
    - specific_pgs_ids: List of specific PGS IDs to include
    - cohort: Name of cohort to filter samples (optional)
    
    Returns:
    - fig: Plotly figure object (static version)
    - stats: Tuple containing statistics about the data
    """
    # TODO dendrograms - we may have to change formt altogether? 
    print(f"=== Generating Static Heatmap for Large Dataset ===")
    print(f"Score Type: {score_type}")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get PGS IDs
    if specific_pgs_ids:
        placeholders = ','.join(['?'] * len(specific_pgs_ids))
        cursor.execute(f"""
            SELECT DISTINCT PGS_ID 
            FROM scores 
            WHERE SCORE_TYPE = ?
            AND PGS_ID IN ({placeholders})
            ORDER BY PGS_ID
            LIMIT ?
        """, [score_type] + specific_pgs_ids + [max_pgs_ids])
    else:
        cursor.execute("""
            SELECT DISTINCT PGS_ID 
            FROM scores 
            WHERE SCORE_TYPE = ?
            ORDER BY PGS_ID
            LIMIT ?
        """, (score_type, max_pgs_ids))
    
    pgs_ids = [row[0] for row in cursor.fetchall()]
    print(f"Selected {len(pgs_ids)} PGS_IDs.")
    
    # Get metadata for PGS IDs
    pgs_metadata = {}
    if pgs_ids:
        placeholder = ','.join(['?'] * len(pgs_ids))
        cursor.execute(f"""
            SELECT PGS_ID, PGS_Name, Reported_Trait, PGS_Publication_ID
            FROM pgs_metadata
            WHERE PGS_ID IN ({placeholder})
        """, pgs_ids)
        
        for pgs_id, pgs_name, reported_trait, publication_id in cursor.fetchall():
            pgs_metadata[pgs_id] = {
                'PGS_Name': pgs_name or 'N/A',
                'Reported_Trait': reported_trait or 'N/A',
                'Publication_ID': publication_id or 'N/A'
            }
    
    # Check for missing metadata
    missing_metadata = set(pgs_ids) - set(pgs_metadata.keys())
    if missing_metadata:
        print(f"Warning: {len(missing_metadata)} PGS_IDs don't have metadata")
        for pgs_id in missing_metadata:
            pgs_metadata[pgs_id] = {
                'PGS_Name': 'Unknown',
                'Reported_Trait': 'Unknown',
                'Publication_ID': 'Unknown'
            }
    
    # Modified sample ID fetching with population filtering
    print("Getting all SAMPLE_IDs for the selected PGS_IDs...")


    if cohort and cohort != "ALL":
        # Query the ancestry table to get sample IDs for the specified population
        cursor.execute("SELECT sample_ids FROM ancestry_groups WHERE population = ?", (cohort,))
        cohort_result = cursor.fetchone()
        sample_ids = json.loads(cohort_result[0])
        print(f"Filtering to {len(sample_ids)} samples from {cohort} population")
    else:
        # No population filtering
        cursor.execute(f"""
            SELECT DISTINCT SAMPLE_ID 
            FROM scores 
            WHERE SCORE_TYPE = ? 
            AND PGS_ID IN ({','.join(['?']*len(pgs_ids))})
            ORDER BY SAMPLE_ID
        """, [score_type] + pgs_ids)
        sample_ids = [row[0] for row in cursor.fetchall()]    

    print(f"Large dataset optimization: {len(sample_ids)} samples × {len(pgs_ids)} PGS IDs")
    
    # Calculate overall statistics for outlier detection
    print("Calculating overall score distribution...")
    cursor.execute("""
        SELECT 
            AVG(SCORE), 
            MIN(SCORE), 
            MAX(SCORE), 
            SQRT(AVG(SCORE * SCORE) - AVG(SCORE) * AVG(SCORE)) AS stdev
        FROM scores
        WHERE SCORE_TYPE = ? AND PGS_ID IN ({})
    """.format(','.join(['?']*len(pgs_ids))),
        [score_type] + pgs_ids)
    
    row = cursor.fetchone()
    avg, min_score, max_score, stdev = row
    
    if stdev is None:  # Handle case where calculation fails
        print("Warning: Standard deviation calculation failed. Using default value.")
        stdev = 1.0
    
    print(f"Score distribution: Mean = {avg:.4f}, Std Dev = {stdev:.4f}")
    
    # Calculate outlier thresholds
    upper_threshold = avg + (std_dev_threshold * stdev)
    lower_threshold = avg - (std_dev_threshold * stdev)
    
    print(f"Outlier thresholds: Lower = {lower_threshold:.4f}, Upper = {upper_threshold:.4f}")
    
    # Count outliers
    cursor.execute("""
        SELECT COUNT(*)
        FROM scores
        WHERE SCORE_TYPE = ? AND PGS_ID IN ({})
        AND (SCORE > ? OR SCORE < ?)
    """.format(','.join(['?']*len(pgs_ids))),
        [score_type] + pgs_ids + [upper_threshold, lower_threshold])
    
    outlier_count = cursor.fetchone()[0]
    print(f"Found {outlier_count} outliers in dataset")
    print("Creating matrix data structure...")
    start_time = time.time()

    matrix = get_matrix(
        sample_ids=sample_ids,
        pgs_ids=pgs_ids,
        score_type=score_type,
        output_format="numpy",  # This will return a numpy matrix directly
        upper_threshold=upper_threshold,
        lower_threshold=lower_threshold
    )
    end_time = time.time()
    print(f"Matrix created in {end_time - start_time:.2f} seconds.")

    # For clustering, we need to temporarily replace NaNs
    clustering_matrix = np.copy(matrix)
    
    print("Preparing data for clustering...")
    # Replace NaNs with column means for row clustering
    for j in range(len(pgs_ids)):
        col = clustering_matrix[:, j]
        valid_values = col[~np.isnan(col)]
        if len(valid_values) > 0:
            col_mean = np.mean(valid_values)
            clustering_matrix[:, j] = np.where(np.isnan(col), col_mean, col)
    
    # Create a transposed matrix for column (PGS_ID) clustering
    clustering_matrix_t = np.copy(matrix).T
    for i in range(len(sample_ids)):
        row = matrix[i, :]
        valid_values = row[~np.isnan(row)]
        if len(valid_values) > 0:
            row_mean = np.mean(valid_values)
            clustering_matrix_t[:, i] = np.where(np.isnan(clustering_matrix_t[:, i]), row_mean, clustering_matrix_t[:, i])
    
    print("Performing hierarchical clustering...")
    
    # Sample (row) clustering
    try:
        # Only use rows that have at least one non-NaN value
        valid_row_indices = np.where(~np.isnan(matrix).all(axis=1))[0]
        if len(valid_row_indices) > 0:
            # Extract valid rows for clustering
            valid_rows = clustering_matrix[valid_row_indices]
            sample_linkage = linkage(valid_rows, method='average')
            sample_dendro = dendrogram(sample_linkage, no_plot=not dendrogram_view)
            
            # Create the full ordering by starting with clustered valid rows
            sample_order = [valid_row_indices[i] for i in sample_dendro['leaves']]
            nan_row_indices = np.where(np.isnan(matrix).all(axis=1))[0]
            sample_order.extend(nan_row_indices)
        else:
            # If no valid rows, use original order
            sample_order = list(range(len(sample_ids)))
            
        ordered_sample_ids = [sample_ids[i] for i in sample_order]
    except Exception as e:
        print(f"Error during sample clustering: {e}. Using original order.")
        sample_order = list(range(len(sample_ids)))
        ordered_sample_ids = sample_ids
    
    # PGS_ID (column) clustering
    try:
        # Only use columns that have at least one non-NaN value
        valid_col_indices = np.where(~np.isnan(matrix).all(axis=0))[0]
        if len(valid_col_indices) > 0:
            # Extract valid columns for clustering
            valid_cols_t = clustering_matrix_t[valid_col_indices]
            pgs_linkage = linkage(valid_cols_t, method='average')
            pgs_dendro = dendrogram(pgs_linkage, no_plot=not dendrogram_view)
            
            # Create the full ordering by starting with clustered valid columns
            pgs_order = [valid_col_indices[i] for i in pgs_dendro['leaves']]
            nan_col_indices = np.where(np.isnan(matrix).all(axis=0))[0]
            pgs_order.extend(nan_col_indices)
        else:
            # If no valid columns, use original order
            pgs_order = list(range(len(pgs_ids)))
            
        ordered_pgs_ids = [pgs_ids[i] for i in pgs_order]
    except Exception as e:
        print(f"Error during PGS_ID clustering: {e}. Using original order.")
        pgs_order = list(range(len(pgs_ids)))
        ordered_pgs_ids = pgs_ids
    
    # Reorder matrix based on both clusterings
    ordered_matrix = matrix[sample_order, :][:, pgs_order]
    
    # Convert to list structure for Plotly
    z_data = ordered_matrix.tolist()
        
    if subcohorts and len(subcohorts) > 0:
        print("Generating heatmap with subcohort-aware clustering...")
        # Pass the original matrix (before clustering) and other necessary data
        subcohort_fig, stats = cluster_with_subcohorts(
            matrix=matrix,  # The original matrix before clustering
            ordered_sample_ids=sample_ids,  # Original sample IDs
            ordered_pgs_ids=ordered_pgs_ids,  # Keep the clustered PGS_ID order
            pgs_metadata=pgs_metadata,
            lower_threshold=lower_threshold,
            upper_threshold=upper_threshold,
            score_type=score_type,
            subcohorts=subcohorts
        )
        return subcohort_fig, stats
        
    # Create hover text matrix with metadata
    hover_text = []
    for i, sample_idx in enumerate(sample_order):
        sample_id = sample_ids[sample_idx]
        hover_row = []
        for j, pgs_idx in enumerate(pgs_order):
            pgs_id = pgs_ids[pgs_idx]
            score = ordered_matrix[i, j]
            if not np.isnan(score):
                metadata = pgs_metadata.get(pgs_id, {})
                hover_text_cell = (
                    f"PGS ID: {pgs_id}<br>"
                    f"Publication_ID: {metadata.get('Publication_ID', 'N/A')}<br>"
                    f"Sample ID: {sample_id}<br>"
                    f"Score: {score:.4f}<br>"
                    f"Trait: {metadata.get('Reported_Trait', 'N/A')}"
                )
                hover_row.append(hover_text_cell)
            else:
                hover_row.append("")
        hover_text.append(hover_row)

    # Create static heatmap with clustered data
    print("Creating static heatmap visualization with clustering...")
    cohort_text = f" - {cohort} Cohort" if cohort and cohort != "ALL" else ""
    title = f'Heatmap of {score_type} Scores{cohort_text}<br>({len(pgs_ids)} PGS_IDs, {len(sample_ids)} Samples, Clustered)'
    
    fig = go.Figure(data=go.Heatmap(
        z=z_data,
        x=ordered_pgs_ids,  # Use ordered PGS IDs
        y=None,  # Don't show sample IDs for large datasets
        colorscale='Viridis',
        colorbar=dict(
            title=f'{score_type} Score',
            tickvals=[lower_threshold, upper_threshold],
            ticktext=[f"{lower_threshold:.2f}", f"{upper_threshold:.2f}"]
        ),
        zmin=lower_threshold,
        zmax=upper_threshold,
        connectgaps=False,
        hoverinfo='text',  # Enable hover info
        text=hover_text,  # Use the hover text we created
        showscale=True
    ))
    
    # Configure layout for performance
    fig.update_layout(
        title=title,
        xaxis=dict(
            showticklabels=False,  # Hide tick labels by default
            showgrid=False,
            zeroline=False,
            hoverformat='.4f'  # Format for hover
        ),
        yaxis=dict(
            showticklabels=False,  # Hide tick labels by default
            showgrid=False,
            zeroline=False
        ),
        width=1000,
        height=800,
        autosize=False,
        margin=dict(l=20, r=20, t=80, b=20),  # Minimal margins
        plot_bgcolor='rgba(0,0,0,0)',  # Transparent background
        paper_bgcolor='white',
        hovermode='closest'  # Enable hover interactions
    )
    
    # Add customized hover behavior with plotly's configuration
    fig.update_layout(
        hoverlabel=dict(
            bgcolor="white",
            font_size=12,
            font_family="Arial"
        )
    )
       # After creating the main heatmap figure, add subcohort annotations if provided
    if subcohorts and len(subcohorts) > 0:
        print(f"Adding {len(subcohorts)} subcohort annotations...")
        
        # Create a mapping from sample_id to row index in the ordered matrix
        sample_id_to_idx = {sample_id: idx for idx, sample_id in enumerate(ordered_sample_ids)}
        
        # For each subcohort, create an annotation trace
        for subcohort in subcohorts:
            # Find which samples from this subcohort are in our dataset
            subcohort_indices = []
            for sample_id in subcohort.sampleIds:
                if sample_id in sample_id_to_idx:
                    subcohort_indices.append(sample_id_to_idx[sample_id])
            
            if not subcohort_indices:
                print(f"Warning: No samples from subcohort '{subcohort.name}' found in dataset")
                continue
                
            print(f"Adding subcohort '{subcohort.name}' with {len(subcohort_indices)} samples")
            
            # Create annotation rectangle for each sample in the subcohort
            for idx in subcohort_indices:
                # Add a thin rectangle at the left edge of the heatmap
                fig.add_shape(
                    type="rect",
                    x0=-0.5,  # Just to the left of the first column
                    x1=-0.1,
                    y0=idx - 0.5,  # Position matches the sample's row
                    y1=idx + 0.5,
                    fillcolor=subcohort.color,
                    opacity=0.8,
                    layer="above",
                    line_width=0,
                )
            fig.add_shape(
                type="rect",
                x0=ordered_pgs_ids[0],  # Ensure it's inside the heatmap area
                x1=ordered_pgs_ids[1], 
                y0=0,
                y1=10,  # Cover multiple rows for visibility
                fillcolor="red",
                opacity=0.8,
                layer="above",
            )
            # Add a legend item for this subcohort
            fig.add_trace(go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                marker=dict(size=10, color=subcohort.color),
                name=subcohort.name,
                legendgroup=subcohort.name,
                showlegend=True
            ))
        
        # Adjust layout to make room for the annotations
        fig.update_layout(
            margin=dict(l=40, r=20, t=80, b=20),  # Increase left margin
            legend=dict(
                title="Subcohorts",
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01,
                bgcolor="rgba(255,255,255,0.8)"
            )
        )
    # Close database connection
    conn.close()
    
    # Return statistics
    stats = (min_score, max_score, None, None, outlier_count)
    return fig, stats

def cluster_with_subcohorts(matrix, ordered_sample_ids, ordered_pgs_ids, pgs_metadata, 
                           lower_threshold, upper_threshold, score_type, subcohorts):
    """
    Generate a single heatmap with subcohort-aware clustering.
    Samples are grouped by subcohorts with each subcohort independently clustered.
    
    Parameters:
    - matrix: The original data matrix (before clustering)
    - ordered_sample_ids: Sample IDs in the order they appear in the matrix
    - ordered_pgs_ids: PGS IDs in the order they appear in the matrix
    - pgs_metadata: Dictionary of metadata for each PGS ID
    - lower_threshold: Lower threshold for color scale
    - upper_threshold: Upper threshold for color scale
    - score_type: Type of score (for labels)
    - subcohorts: List of subcohort objects containing name, color, and sampleIds
    
    Returns:
    - fig: Plotly figure object with subcohort-aware clustering
    - stats: Dictionary containing statistics about each subcohort's data
    """
    
    print(f"=== Generating Heatmap with Subcohort-Aware Clustering ===")
    print(f"Number of subcohorts: {len(subcohorts)}")
    
    # Create a mapping from sample_id to index in the ordered matrix
    sample_id_to_idx = {sample_id: idx for idx, sample_id in enumerate(ordered_sample_ids)}
    
    # Get the set of all sample indices included in subcohorts
    all_subcohort_indices = set()
    for subcohort in subcohorts:
        for sample_id in subcohort.sampleIds:
            if sample_id in sample_id_to_idx:
                all_subcohort_indices.add(sample_id_to_idx[sample_id])
    
    # Determine which samples aren't in any subcohort
    remaining_indices = [i for i in range(len(ordered_sample_ids)) if i not in all_subcohort_indices]
    print(f"Found {len(remaining_indices)} samples not belonging to any subcohort")
    
    # Create a "remaining" subcohort object if we have any remaining samples
    if remaining_indices:
        remaining_subcohort = type('obj', (object,), {
            'name': 'Remaining Samples',
            'color': 'gray',
            'sampleIds': [ordered_sample_ids[i] for i in remaining_indices]
        })
        # Add to the end of subcohorts list
        all_subcohorts = list(subcohorts) + [remaining_subcohort]
    else:
        all_subcohorts = list(subcohorts)
    
    # Create a new ordering of samples based on subcohorts
    # Each subcohort will be clustered independently
    new_sample_order = []
    subcohort_boundaries = []  # To keep track of where each subcohort begins/ends
    current_position = 0
    
    # Process each subcohort
    for subcohort in all_subcohorts:
        print(f"Processing subcohort: {subcohort.name}")
        
        # Find which samples from this subcohort are in our dataset
        subcohort_indices = []
        for sample_id in subcohort.sampleIds:
            if sample_id in sample_id_to_idx:
                subcohort_indices.append(sample_id_to_idx[sample_id])
        
        if not subcohort_indices:
            print(f"Warning: No samples from subcohort '{subcohort.name}' found in dataset")
            continue
        
        print(f"Found {len(subcohort_indices)} samples for subcohort '{subcohort.name}'")
        
        # Extract the submatrix for this subcohort
        subcohort_matrix = matrix[subcohort_indices, :]
        subcohort_sample_ids = [ordered_sample_ids[idx] for idx in subcohort_indices]
        
        # Perform clustering on this submatrix for rows
        # For clustering, we need to temporarily replace NaNs
        clustering_matrix = np.copy(subcohort_matrix)
        
        # Replace NaNs with column means for row clustering
        for j in range(clustering_matrix.shape[1]):
            col = clustering_matrix[:, j]
            valid_values = col[~np.isnan(col)]
            if len(valid_values) > 0:
                col_mean = np.mean(valid_values)
                clustering_matrix[:, j] = np.where(np.isnan(col), col_mean, col)
        
        # Sample (row) clustering for this subcohort
        try:
            # Only use rows that have at least one non-NaN value
            valid_row_indices = np.where(~np.isnan(subcohort_matrix).all(axis=1))[0]
            if len(valid_row_indices) > 0:
                # Extract valid rows for clustering
                valid_rows = clustering_matrix[valid_row_indices]
                if len(valid_rows) > 1:  # Need at least 2 rows for clustering
                    sample_linkage = linkage(valid_rows, method='average')
                    sample_dendro = dendrogram(sample_linkage, no_plot=True)
                    
                    # Create the full ordering by starting with clustered valid rows
                    sample_order = [valid_row_indices[i] for i in sample_dendro['leaves']]
                    nan_row_indices = np.where(np.isnan(subcohort_matrix).all(axis=1))[0]
                    sample_order.extend(nan_row_indices)
                else:
                    sample_order = list(range(len(subcohort_indices)))
            else:
                # If no valid rows, use original order
                sample_order = list(range(len(subcohort_indices)))
        except Exception as e:
            print(f"Error during sample clustering for subcohort: {e}. Using original order.")
            sample_order = list(range(len(subcohort_indices)))
        
        # Add these indices to our new overall ordering
        for idx in sample_order:
            new_sample_order.append(subcohort_indices[idx])
        
        # Record the boundary for this subcohort
        if len(subcohort_indices) > 0:
            if current_position > 0:  # Not the first subcohort
                subcohort_boundaries.append({
                    'name': subcohort.name,
                    'color': subcohort.color,
                    'start': current_position,
                    'size': len(subcohort_indices)
                })
            else:  # First subcohort
                subcohort_boundaries.append({
                    'name': subcohort.name,
                    'color': subcohort.color,
                    'start': 0,
                    'size': len(subcohort_indices)
                })
            current_position += len(subcohort_indices)
              
    # Reorder matrix based on new sample ordering
    # The PGS_ID order remains the same
    new_ordered_matrix = matrix[new_sample_order, :]
    new_ordered_sample_ids = [ordered_sample_ids[i] for i in new_sample_order]
    
    # Convert to list structure for Plotly
    z_data = new_ordered_matrix.tolist()
    
    # Create hover text matrix with metadata
    hover_text = []
    for i, sample_idx in enumerate(new_sample_order):
        sample_id = ordered_sample_ids[sample_idx]
        hover_row = []
        for j, pgs_id in enumerate(ordered_pgs_ids):
            score = new_ordered_matrix[i, j]
            if not np.isnan(score):
                metadata = pgs_metadata.get(pgs_id, {})
                hover_text_cell = (
                    f"PGS ID: {pgs_id}<br>"
                    f"Publication_ID: {metadata.get('Publication_ID', 'N/A')}<br>"
                    f"Sample ID: {sample_id}<br>"
                    f"Score: {score:.4f}<br>"
                    f"Trait: {metadata.get('Reported_Trait', 'N/A')}"
                )
                hover_row.append(hover_text_cell)
            else:
                hover_row.append("")
        hover_text.append(hover_row)
    
    # Create static heatmap with subcohort-aware clustering
    print("Creating heatmap visualization with subcohort-aware clustering...")
    title = f'Heatmap of {score_type} Scores<br>({len(ordered_pgs_ids)} PGS_IDs, {len(ordered_sample_ids)} Samples, Subcohort-Clustered)'
    
    fig = go.Figure(data=go.Heatmap(
        z=z_data,
        x=ordered_pgs_ids,  # Use original ordered PGS IDs
        y=None,  # Don't show sample IDs for large datasets
        colorscale='Viridis',
        colorbar=dict(
            title=f'{score_type} Score',
            tickvals=[lower_threshold, upper_threshold],
            ticktext=[f"{lower_threshold:.2f}", f"{upper_threshold:.2f}"]
        ),
        zmin=lower_threshold,
        zmax=upper_threshold,
        connectgaps=False,
        hoverinfo='text',  # Enable hover info
        text=hover_text,  # Use the hover text we created
        showscale=True
    ))
    
    # Add horizontal lines to separate subcohorts
    for boundary in subcohort_boundaries[1:]:  # Skip the first boundary (start of first subcohort)
        y_pos = boundary['start'] - 0.5  # Position line between subcohorts
        fig.add_shape(
            type="line",
            x0=-0.5,  # Start at the left edge
            x1=len(ordered_pgs_ids) - 0.5,  # End at the right edge
            y0=y_pos,
            y1=y_pos,
            line=dict(
                color="white",
                width=2,
            ),
            layer="above"
        )
    
    # Add colored rectangles on the left to indicate subcohorts
    for boundary in subcohort_boundaries:
        y0 = boundary['start'] - 0.5
        y1 = boundary['start'] + boundary['size'] - 0.5
        fig.add_shape(
            type="rect",
            x0=-0.5,  # Left of the heatmap
            x1=-0.1,  # Width of the indicator
            y0=y0,
            y1=y1,
            fillcolor=boundary['color'],
            opacity=0.8,
            layer="above",
            line_width=0,
        )
        
        # Add a text label for the subcohort
        fig.add_annotation(
            x=-0.3,  # Position of the text
            y=(y0 + y1) / 2,  # Middle of the subcohort
            text=boundary['name'],
            showarrow=False,
            textangle=-90,  # Vertical text
            xanchor="center",
            yanchor="middle",
            font=dict(
                color="white",
                size=10
            )
        )
    
    # Add legend entries for each subcohort
    for boundary in subcohort_boundaries:
        fig.add_trace(go.Scatter(
            x=[None],
            y=[None],
            mode="markers",
            marker=dict(size=10, color=boundary['color']),
            name=f"{boundary['name']} ({boundary['size']} samples)",
            legendgroup=boundary['name'],
            showlegend=True
        ))
    
    # Configure layout
    fig.update_layout(
        title=title,
        xaxis=dict(
            showticklabels=False,  # Hide tick labels by default
            showgrid=False,
            zeroline=False,
            hoverformat='.4f'  # Format for hover
        ),
        yaxis=dict(
            showticklabels=False,  # Hide tick labels by default
            showgrid=False,
            zeroline=False
        ),
        width=1000,
        height=800,
        autosize=False,
        margin=dict(l=60, r=20, t=80, b=20),  # Increased left margin for subcohort labels
        plot_bgcolor='rgba(0,0,0,0)',  # Transparent background
        paper_bgcolor='white',
        hovermode='closest',  # Enable hover interactions
        hoverlabel=dict(
            bgcolor="white",
            font_size=12,
            font_family="Arial"
        ),
        legend=dict(
            title="Subcohorts",
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01,
            bgcolor="rgba(255,255,255,0.8)"
        )
    )
    
    return fig, (0, 0, None, None, 0)

def cleanup_temp_files(max_size_in_gb=10):
    """
    Cleans up temporary heatmap files when the directory exceeds the specified size limit.
    
    Args:
        max_size_in_gb: Maximum allowed size of the temp directory in GB
    """
    temp_dir = "temp"
    max_size_in_bytes = max_size_in_gb * 1024 * 1024 * 1024
    
    # Check if the directory exists
    if not os.path.exists(temp_dir):
        return
    
    # Get all HTML files in the temp directory with their stats
    files = []
    total_size = 0
    
    for filename in os.listdir(temp_dir):
        if filename.endswith(".html"):
            filepath = os.path.join(temp_dir, filename)
            file_stats = os.stat(filepath)
            file_size = file_stats.st_size
            access_time = file_stats.st_atime  # Last access time
            
            files.append({
                "path": filepath,
                "size": file_size,
                "last_accessed": access_time
            })
            
            total_size += file_size
    
    print(f"Current temp directory size: {total_size / (1024 * 1024):.2f} MB")
    
    # If we're under the limit, do nothing
    if total_size <= max_size_in_bytes:
        return
    
    print(f"Temp directory size ({total_size / (1024 * 1024 * 1024):.2f} GB) exceeds limit of {max_size_in_gb} GB")
    
    # Sort files by last access time (oldest first)
    files.sort(key=lambda x: x["last_accessed"])
    
    # Remove files until we're under the limit
    deleted_count = 0
    freed_space = 0
    
    while total_size > max_size_in_bytes and files:
        file_to_remove = files.pop(0)  # Get the oldest file
        
        try:
            os.remove(file_to_remove["path"])
            freed_space += file_to_remove["size"]
            total_size -= file_to_remove["size"]
            deleted_count += 1
            print(f"Deleted: {os.path.basename(file_to_remove['path'])}")
        except Exception as e:
            print(f"Error deleting {file_to_remove['path']}: {e}")
    
    print(f"Cleanup complete: Deleted {deleted_count} files, freed {freed_space / (1024 * 1024):.2f} MB")

def generate_heatmap_hash(score_type, std_dev_threshold, dendrogram_view, pgs_ids, cohort=None, subcohort=None):
    """
    Generate a consistent hash based on heatmap request parameters.
    
    Args:
        score_type: The type of score to display
        std_dev_threshold: Threshold for outlier detection
        dendrogram_view: Whether compact view is enabled
        pgs_ids: List of PGS IDs to include
        cohort: Selected sample cohort
    
    Returns:
        str: A hash string representing the request parameters
    """
    
    all_subcohort_sample_ids = []
    if subcohort:
        for c in subcohort:
            all_subcohort_sample_ids.extend(c.sampleIds)
        all_subcohort_sample_ids = sorted(all_subcohort_sample_ids)

    # Create a dictionary of parameters
    params = {
        "score_type": score_type,
        "std_dev_threshold": std_dev_threshold,
        "dendrogram_view": dendrogram_view,
        "pgs_ids": sorted(pgs_ids) if pgs_ids else [],  
        "cohort": cohort,
        "subcohort": all_subcohort_sample_ids
    }
    
    # Convert to JSON string
    param_str = json.dumps(params, sort_keys=True)
    
    # Generate hash
    hash_obj = hashlib.md5(param_str.encode())
    return hash_obj.hexdigest()

@app.post("/api/generate_umap")
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

def process_umap(request_data):
    try:
        # Create temp directory if it doesn't exist
        os.makedirs("temp", exist_ok=True)
        
        # Extract parameters from request_data
        score_type = request_data["score_type"]
        n_neighbors = request_data["n_neighbors"]
        min_dist = request_data["min_dist"]
        pgs_ids = request_data["pgs_ids"]
        cohort = request_data["cohort"]
        view_type = request_data["view_type"]
        
        # Generate hash based on request parameters
        request_hash = generate_umap_hash(
            score_type,
            n_neighbors,
            min_dist,
            pgs_ids,
            cohort,
            view_type  
        )

        print(f"Request hash: {request_hash}")

        # Check if we already have a file with this hash
        for filename in os.listdir("temp"):
            if filename.endswith(".html") and request_hash in filename and "umap" in filename:
                # Found a cached file, update its access time
                cached_filepath = os.path.join("temp", filename)
                os.utime(cached_filepath)
                
                print(f"Using cached UMAP: {filename}")
                
                # Return file path
                return f"/temp/{filename}"

        # Parameters for hash
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        score_type_safe = score_type.replace("/", "_").replace("\\", "_")
        cohort_indicator = f"{cohort}_" if cohort and cohort != "ALL" else ""
        view_indicator = f"{view_type}_"  # Add view type to filename
        filename = f"umap_{cohort_indicator}{view_indicator}{score_type_safe}_{request_hash}_{timestamp}.html"
        filepath = os.path.join("temp", filename)
        
        # Generate UMAP
        fig, stats = generate_umap_html(
            score_type=score_type,
            n_neighbors=n_neighbors,
            min_dist=min_dist,
            specific_pgs_ids=pgs_ids,
            cohort=cohort,
            view_type=view_type
        )
        
        # Save the visualization
        fig.write_html(
            filepath,
            include_plotlyjs='cdn',    
            include_mathjax=False,    
            config={
                'displayModeBar': False,  
                'responsive': True        
            }
        )
        
        # Return the file path
        return f"/temp/{filename}"
        
    except Exception as e:
        # Log the error
        print(f"Error generating UMAP: {str(e)}")
        raise e

def generate_umap_html(score_type, n_neighbors=15, min_dist=0.1, specific_pgs_ids=None, cohort=None, view_type="sample"):
    """
    Generate a UMAP visualization for PGS score data.
    
    Parameters:
    - score_type: The SCORE_TYPE to filter on
    - n_neighbors: Number of neighbors for UMAP (default: 15)
    - min_dist: Minimum distance for UMAP (default: 0.1)
    - specific_pgs_ids: List of specific PGS IDs to include
    - cohort: Name of cohort to filter samples (optional)
    
    Returns:
    - fig: Plotly figure object
    - stats: Tuple containing statistics about the data
    """
    print(f"=== Generating UMAP Visualization ===")
    print(len(specific_pgs_ids))
    print(f"View Type: {view_type}")
    print(f"Score Type: {score_type}")
    
    # Database connection and data retrieval 
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get PGS IDs 
    if specific_pgs_ids:
        placeholders = ','.join(['?'] * len(specific_pgs_ids))
        cursor.execute(f"""
            SELECT DISTINCT PGS_ID 
            FROM scores 
            WHERE SCORE_TYPE = ?
            AND PGS_ID IN ({placeholders})
            ORDER BY PGS_ID
        """, [score_type] + specific_pgs_ids)
    else:
        cursor.execute("""
            SELECT DISTINCT PGS_ID 
            FROM scores 
            WHERE SCORE_TYPE = ?
            ORDER BY PGS_ID
        """, (score_type,))

    # Get metadata for PGS IDs
    pgs_metadata = {}
    if pgs_ids:
        placeholder = ','.join(['?'] * len(pgs_ids))
        cursor.execute(f"""
            SELECT PGS_ID, PGS_Name, Reported_Trait, PGS_Publication_ID
            FROM pgs_metadata
            WHERE PGS_ID IN ({placeholder})
        """, pgs_ids)
        
        for pgs_id, pgs_name, reported_trait, publication_id in cursor.fetchall():
            pgs_metadata[pgs_id] = {
                'PGS_Name': pgs_name or 'N/A',
                'Reported_Trait': reported_trait or 'N/A',
                'Publication_ID': publication_id or 'N/A'
            }
    
    # Check for missing metadata
    missing_metadata = set(pgs_ids) - set(pgs_metadata.keys())
    if missing_metadata:
        print(f"Warning: {len(missing_metadata)} PGS_IDs don't have metadata")
        for pgs_id in missing_metadata:
            pgs_metadata[pgs_id] = {
                'PGS_Name': 'Unknown',
                'Reported_Trait': 'Unknown',
                'Publication_ID': 'Unknown'
            }
    
    # Modified sample ID fetching with cohort filtering
    print("Getting all SAMPLE_IDs for the selected PGS_IDs...")
    
    if cohort and cohort != "ALL":
        # Get sample IDs from the ancestry_groups table
        cursor.execute("SELECT sample_ids FROM ancestry_groups WHERE population = ?", (cohort,))
        cohort_result = cursor.fetchone()
        sample_ids = json.loads(cohort_result[0])
    else:
        cursor.execute("SELECT DISTINCT SAMPLE_ID FROM scores")
        sample_ids = [row[0] for row in cursor.fetchall()]
        print(f"Using {len(sample_ids)} total samples")

    print(f"Found {len(sample_ids)} unique SAMPLE_IDs.")
    
    if cohort and cohort != "ALL":
        print(f"Using {len(sample_ids)} samples from {cohort} cohort.")
    
    data_dict = get_matrix(
        sample_ids=sample_ids,
        pgs_ids=pgs_ids,
        score_type=score_type,
        output_format="dict"  
    )

    # Close database connection
    conn.close()

    # Branch based on view_type
    if view_type == "sample":
        # Original sample-based UMAP - mostly unchanged
        return generate_sample_based_umap(
            sample_ids, pgs_ids, data_dict, n_neighbors, min_dist, 
            score_type, cohort
        )
    else:  # "score" view type
        # New score-based UMAP
        return generate_score_based_umap(
            sample_ids, pgs_ids, data_dict, n_neighbors, min_dist, 
            score_type, cohort, pgs_metadata
        )

def generate_sample_based_umap(sample_ids, pgs_ids, data_dict, n_neighbors, min_dist, score_type, cohort):
    print("Creating matrix for clustering...")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create a numpy matrix with NaN for missing values
    matrix = np.full((len(sample_ids), len(pgs_ids)), np.nan)
    for i, sample_id in enumerate(sample_ids):
        for j, pgs_id in enumerate(pgs_ids):
            if pgs_id in data_dict[sample_id]:
                matrix[i, j] = data_dict[sample_id][pgs_id]
    
    # Apply UMAP for dimensionality reduction
    print("Applying UMAP dimensionality reduction...")
    
    # Handle missing values before UMAP
    matrix_for_umap = np.copy(matrix)
    for j in range(matrix_for_umap.shape[1]):
        col_mean = np.nanmean(matrix_for_umap[:, j])
        mask = np.isnan(matrix_for_umap[:, j])
        matrix_for_umap[mask, j] = col_mean
    
    # Import and create UMAP
    reducer = umap.UMAP(
        n_neighbors=n_neighbors,
        min_dist=min_dist,
        n_components=2,
        random_state=42
    )
    
    # Apply UMAP to get 2D embedding
    embedding = reducer.fit_transform(matrix_for_umap)
    
    # Calculate statistics for color mapping
    all_scores = [score for sample in data_dict.values() for score in sample.values()]
    min_score = min(all_scores)
    max_score = max(all_scores)
    
    # Create hover text for points
    hover_text = []
    for i, sample_id in enumerate(sample_ids):
        avg_score = np.nanmean([data_dict[sample_id].get(pgs_id, np.nan) for pgs_id in pgs_ids])
        cursor.execute('SELECT population FROM ancestry WHERE sample_id = ?', (sample_id,))
        result = cursor.fetchone()
        ancestry = result[0] if result else 'Unknown'
        hover_info = f"Sample: {sample_id}<br>Ancestry: {ancestry}<br>Avg Score: {avg_score:.4f}"
        hover_text.append(hover_info)
    
    # Create UMAP scatter plot
    print("Creating UMAP visualization...")
    cohort_text = f" - {cohort} Cohort" if cohort and cohort != "ALL" else ""
    title = f'UMAP of {score_type} Scores{cohort_text}<br>({len(pgs_ids)} PGS_IDs, {len(sample_ids)} Samples)'
    print(f"embedding: {embedding.shape}")
    print(f"PGS_IDs count: {len(pgs_ids)}, Sample count: {len(sample_ids)}")

    # Create a color scale based on average score per sample
    avg_scores = [np.nanmean([data_dict[sample_id].get(pgs_id, np.nan) for pgs_id in pgs_ids]) for sample_id in sample_ids]
    
    fig = go.Figure(data=go.Scatter(
        x=embedding[:, 0],
        y=embedding[:, 1],
        mode='markers',
        marker=dict(
            size=5,
            color=avg_scores,
            colorscale='Viridis',
            colorbar=dict(
                title=f'Avg {score_type} Score'
            ),
            showscale=True
        ),
        text=hover_text,
        hoverinfo='text'
    ))
    
    # Configure layout
    fig.update_layout(
        title=title,
        xaxis=dict(
            title='UMAP Dimension 1',
            showgrid=True,
            zeroline=False,
        ),
        yaxis=dict(
            title='UMAP Dimension 2',
            showgrid=True,
            zeroline=False,
        ),
        width=1000,
        height=800,
        autosize=False,
        margin=dict(l=20, r=20, t=80, b=20),
        plot_bgcolor='white',
        paper_bgcolor='white',
        hovermode='closest'
    )
    
    # Add customized hover behavior
    fig.update_layout(
        hoverlabel=dict(
            bgcolor="white",
            font_size=12,
            font_family="Arial"
        )
    )
    
    # Close database connection
    conn.close()

    # Return statistics (keeping the same structure as your original function)
    stats = (None)
    return fig, stats

def generate_score_based_umap(sample_ids, pgs_ids, data_dict, n_neighbors, min_dist, score_type, cohort, pgs_metadata):
    """Generate UMAP where each point is a PGS score"""
    print("Creating matrix for score-based clustering...")
    
    # Transpose the matrix - now rows are PGS IDs and columns are samples
    matrix = np.full((len(pgs_ids), len(sample_ids)), np.nan)
    for i, pgs_id in enumerate(pgs_ids):
        for j, sample_id in enumerate(sample_ids):
            if pgs_id in data_dict[sample_id]:
                matrix[i, j] = data_dict[sample_id][pgs_id]
    
    # Handle missing values
    matrix_for_umap = np.copy(matrix)
    for j in range(matrix_for_umap.shape[1]):
        col_mean = np.nanmean(matrix_for_umap[:, j])
        mask = np.isnan(matrix_for_umap[:, j])
        matrix_for_umap[mask, j] = col_mean
    
    # Apply UMAP
    reducer = umap.UMAP(
        n_neighbors=min(n_neighbors, len(pgs_ids) - 1),  # Adjust neighbors if needed
        min_dist=min_dist,
        n_components=2,
        random_state=42
    )
    
    embedding = reducer.fit_transform(matrix_for_umap)
    
    # Create hover text for points
    hover_text = []
    for i, pgs_id in enumerate(pgs_ids):
        # Get metadata for this PGS ID
        metadata = pgs_metadata.get(pgs_id, {
            'PGS_Name': 'Unknown',
            'Reported_Trait': 'Unknown',
            'Publication_ID': 'Unknown'
        })
        
        # Calculate average score for this PGS ID across samples
        scores = [data_dict[sample_id].get(pgs_id, np.nan) for sample_id in sample_ids]
        avg_score = np.nanmean([s for s in scores if not np.isnan(s)])
        
        hover_info = (
            f"PGS ID: {pgs_id}<br>"
            f"Name: {metadata['PGS_Name']}<br>"
            f"Trait: {metadata['Reported_Trait']}<br>"
            f"Publication: {metadata['Publication_ID']}<br>"
            f"Avg Score: {avg_score:.4f}"
        )
        hover_text.append(hover_info)
    
    # Create UMAP scatter plot
    cohort_text = f" - {cohort} Cohort" if cohort and cohort != "ALL" else ""
    title = f'Score-based UMAP of {score_type} Scores{cohort_text}<br>({len(pgs_ids)} PGS_IDs across {len(sample_ids)} Samples)'
    
    # Get traits for coloring 
    traits = [pgs_metadata.get(pgs_id, {}).get('Reported_Trait', 'Unknown') for pgs_id in pgs_ids]
    unique_traits = list(set(traits))
    
    # Create a colormap
    color_indices = [unique_traits.index(trait) for trait in traits]
    
    fig = go.Figure(data=go.Scatter(
        x=embedding[:, 0],
        y=embedding[:, 1],
        mode='markers',
        marker=dict(
            size=8,
            color=color_indices,
            colorscale='Rainbow',  # Different colorscale for scores
            showscale=False
        ),
        text=hover_text,
        hoverinfo='text'
    ))
    
    # Configure layout
    fig.update_layout(
        title=title,
        xaxis=dict(title='UMAP Dimension 1', showgrid=True, zeroline=False),
        yaxis=dict(title='UMAP Dimension 2', showgrid=True, zeroline=False),
        width=1000, height=800, autosize=False,
        margin=dict(l=20, r=20, t=80, b=20),
        plot_bgcolor='white', paper_bgcolor='white',
        hovermode='closest',
        hoverlabel=dict(bgcolor="white", font_size=12, font_family="Arial")
    )
    
    stats = (None)
    return fig, stats

def generate_umap_hash(score_type, n_neighbors, min_dist, pgs_ids, cohort, view_type):
    """Generate a consistent hash based on UMAP request parameters."""
    params = {
        "score_type": score_type,
        "n_neighbors": n_neighbors,
        "min_dist": min_dist,
        "pgs_ids": sorted(pgs_ids) if pgs_ids else [],
        "cohort": cohort,
        "view_type": view_type  
    }

    # Convert to JSON string
    param_str = json.dumps(params, sort_keys=True)
    
    # Generate hash
    hash_obj = hashlib.md5(param_str.encode())
    return hash_obj.hexdigest()

@app.post("/api/generate_svd_image")
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

def process_svd(request_data):
    try:
        # Create temp directory if it doesn't exist
        os.makedirs("temp", exist_ok=True)
        
        # Extract parameters from request_data
        score_type = request_data["score_type"]
        pgs_ids = request_data["pgs_ids"]
        cohort = request_data["cohort"]
        plot_type = request_data["plot_type"]
        perspective = request_data.get("perspective", "sample")  # Default to sample
        max_vectors = request_data.get("max_vectors", 10)  # Default to 10
        
        # Generate hash for caching
        request_hash = generate_svd_hash(
            score_type,
            pgs_ids,
            cohort,
            plot_type,
            perspective,
            max_vectors
        )
        
        # Check if we already have a file with this hash
        for filename in os.listdir("temp"):
            if filename.endswith(".html") and request_hash in filename and "svd" in filename:
                # Found a cached file, update its access time
                cached_filepath = os.path.join("temp", filename)
                os.utime(cached_filepath)
                
                print(f"Using cached SVD visualization: {filename}")
                
                # Return file path
                return f"/temp/{filename}"
        
        # First, perform SVD analysis to get the matrices
        U, S, Vt, pgs_ids, sample_ids, stats = perform_svd_analysis(
            score_type=score_type,
            specific_pgs_ids=pgs_ids,
            cohort=cohort
        )
        
        # Generate filename with hash
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        score_type_safe = score_type.replace("/", "_").replace("\\", "_")
        cohort_indicator = f"{cohort}_" if cohort and cohort != "ALL" else ""
        filename = f"svd_{cohort_indicator}{score_type_safe}_{plot_type}_{request_hash}_{timestamp}.html"
        filepath = os.path.join("temp", filename)
        
        # Route to the appropriate visualization function
        if plot_type == "scree":
            fig = generate_svd_scree_plot(S, stats)
        elif plot_type == "biplot":
            if perspective == "score":
                fig = generate_svd_biplot_score(U, S, Vt, pgs_ids, sample_ids, stats, max_vectors=max_vectors)
            else:  # Default to sample perspective
                fig = generate_svd_biplot_sample(U, S, Vt, pgs_ids, sample_ids, stats, max_vectors=max_vectors)
        elif plot_type == "component_weights":
            fig = generate_svd_component_weights(Vt, pgs_ids, stats)
        elif plot_type == "heatmap":
            fig = generate_svd_heatmap(Vt, pgs_ids, stats)
        elif plot_type == "combined":
            fig = generate_svd_combined(U, S, Vt, pgs_ids, sample_ids, stats)
        
        # Save the figure to HTML
        fig.write_html(
            filepath,
            include_plotlyjs='cdn',
            include_mathjax=False,
            config={
                'displayModeBar': True,
                'responsive': True
            }
        )
        
        # Return file path
        return f"/temp/{filename}"
        
    except Exception as e:
        # Log the error
        print(f"Error generating SVD visualization: {str(e)}")
        raise e 

def perform_svd_analysis(score_type, specific_pgs_ids=None, cohort=None):
    """
    Build a matrix of PGS scores x samples and perform SVD on it.
    
    Parameters:
    - score_type: The SCORE_TYPE to filter on
    - specific_pgs_ids: List of specific PGS IDs to include (if None, use all)
    - cohort: Name of cohort to filter samples (optional)
    
    Returns:
    - U: Left singular vectors (sample space)
    - S: Singular values
    - Vt: Right singular vectors (PGS score space)
    - pgs_ids: List of PGS IDs used (for reference)
    - sample_ids: List of sample IDs used (for reference)
    - stats: Dictionary containing additional statistics
    """
    print(f"=== Performing SVD Analysis ===")
    print(f"Score Type: {score_type}")
    
    # Database connection
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get PGS IDs 
    if specific_pgs_ids:
        placeholders = ','.join(['?'] * len(specific_pgs_ids))
        cursor.execute(f"""
            SELECT DISTINCT PGS_ID 
            FROM scores 
            WHERE SCORE_TYPE = ?
            AND PGS_ID IN ({placeholders})
            ORDER BY PGS_ID
        """, [score_type] + specific_pgs_ids)
    else:
        cursor.execute("""
            SELECT DISTINCT PGS_ID 
            FROM scores 
            WHERE SCORE_TYPE = ?
            ORDER BY PGS_ID
        """, (score_type,))
    
    pgs_ids = [row[0] for row in cursor.fetchall()]
    print(f"Selected {len(pgs_ids)} PGS_IDs.")
            
    # Modified sample ID fetching with population filtering
    print("Getting all SAMPLE_IDs for the selected PGS_IDs...")

    if cohort and cohort != "ALL":
        # Query the ancestry table to get sample IDs for the specified population
        cursor.execute("SELECT sample_ids FROM ancestry_groups WHERE population = ?", (cohort,))
        cohort_result = cursor.fetchone()
        
        if cohort_result:
            # Parse the JSON array of sample IDs
            sample_ids = json.loads(cohort_result[0])
            print(f"Filtering to {len(sample_ids)} samples from {cohort} population")
            

        else:
            print(f"Warning: Population {cohort} not found in database. Using all samples.")
            cursor.execute(f"""
                SELECT DISTINCT SAMPLE_ID 
                FROM scores 
                WHERE SCORE_TYPE = ? 
                AND PGS_ID IN ({','.join(['?']*len(pgs_ids))})
                ORDER BY SAMPLE_ID
            """, [score_type] + pgs_ids)
            sample_ids = [row[0] for row in cursor.fetchall()]
    else:
        # No population filtering
        cursor.execute(f"""
            SELECT DISTINCT SAMPLE_ID 
            FROM scores 
            WHERE SCORE_TYPE = ? 
            AND PGS_ID IN ({','.join(['?']*len(pgs_ids))})
            ORDER BY SAMPLE_ID
        """, [score_type] + pgs_ids)
    
        sample_ids = [row[0] for row in cursor.fetchall()]

    print(f"Found {len(sample_ids)} unique SAMPLE_IDs.")

    start_time = time.time()
    print("Starting data processing...")

    matrix = get_matrix(
        sample_ids=sample_ids,
        pgs_ids=pgs_ids,
        score_type=score_type,
        output_format="numpy",
        handle_missing=True  
    )

    total_time = time.time() - start_time
    print(f"Total processing time: {total_time:.2f} seconds.")
    print(f"Matrix shape: {matrix.shape}")   

    # Center the data (important for SVD/PCA interpretation)
    matrix_centered = matrix - np.mean(matrix, axis=0)
    
    # Perform SVD
    print("Performing SVD...")
    U, S, Vt = np.linalg.svd(matrix_centered, full_matrices=False)
    
    # Calculate explained variance
    explained_variance = (S ** 2) / (matrix_centered.shape[0] - 1)
    total_variance = np.sum(explained_variance)
    explained_variance_ratio = explained_variance / total_variance
    
    # Compile statistics
    stats = {
        "explained_variance_ratio": explained_variance_ratio.tolist(),
        "cumulative_variance": np.cumsum(explained_variance_ratio).tolist(),
        "singular_values": S.tolist(),
        "num_samples": len(sample_ids),
        "num_pgs_ids": len(pgs_ids),
        "score_type": score_type,
        "cohort": cohort if cohort else "ALL"
    }
    
    # Close database connection
    conn.close()
    
    return U, S, Vt, pgs_ids, sample_ids, stats

def generate_svd_scree_plot(S, stats):
    """Generate a scree plot to visualize singular values and explained variance"""
    explained_variance_ratio = stats["explained_variance_ratio"]
    cumulative_variance = stats["cumulative_variance"]
    
    # Create scree plot with two traces
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Bar chart for individual explained variance
    fig.add_trace(
        go.Bar(
            x=list(range(1, len(S)+1)),
            y=explained_variance_ratio,
            name="Explained Variance",
            marker_color="blue"
        ),
        secondary_y=False
    )
    
    # Line chart for cumulative explained variance
    fig.add_trace(
        go.Scatter(
            x=list(range(1, len(S)+1)),
            y=cumulative_variance,
            name="Cumulative Variance",
            mode="lines+markers",
            line=dict(color="red")
        ),
        secondary_y=True
    )
    
    # Update layout
    fig.update_layout(
        title=f'SVD Scree Plot: {stats["score_type"]} Scores',
        xaxis=dict(
            title='Component',
            tickmode='linear',
            tick0=1,
            dtick=1
        ),
        yaxis=dict(
            title='Explained Variance Ratio',
            range=[0, max(explained_variance_ratio) * 1.1]
        ),
        yaxis2=dict(
            title='Cumulative Explained Variance',
            range=[0, 1.05],
            tickformat='.0%'
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        height=600,
        width=900
    )
    
    fig.update_traces(
        marker_line_color='rgb(8,48,107)',
        marker_line_width=1.5,
        opacity=0.6,
        selector=dict(type='bar')
    )
    
    return fig

def generate_svd_biplot_sample(U, S, Vt, pgs_ids, sample_ids, stats, pgs_metadata=None, max_vectors=20):
    """Generate a biplot to visualize samples and features in the same 2D space"""
    # Number of components to use (typically 2 for a 2D plot)
    n_components = 2

    # Scale the singular vectors by the singular values
    U_scaled = U[:, :n_components] * S[:n_components]

    # Create figure
    fig = go.Figure()

    # Add samples as scatter points
    fig.add_trace(
        go.Scatter(
            x=U_scaled[:, 0],
            y=U_scaled[:, 1],
            mode='markers',
            marker=dict(
                size=5,
                color='green',  # Changed from blue to green as per your example
                opacity=0.6
            ),
            name='Samples',
            text=[f"Sample: {sample_id}" for sample_id in sample_ids],
            hoverinfo='text'
        )
    )

    # Calculate scaling factor for feature vectors
    scale_factor = np.percentile(np.abs(U_scaled), 95) / np.percentile(np.abs(Vt[:n_components, :]), 95) * 0.5

    # Find top contributing PGS scores
    if len(pgs_ids) > max_vectors:
        # Calculate contribution of each PGS to the first 2 components
        pgs_contributions = np.sum(Vt[:n_components, :]**2, axis=0)
        # Get indices of top contributors
        top_indices = np.argsort(pgs_contributions)[::-1][:max_vectors]
    else:
        # If fewer PGS than max_vectors, use all of them
        top_indices = range(len(pgs_ids))

    # Create hover text for PGS vectors
    hover_texts = []
    for idx in top_indices:
        pgs_id = pgs_ids[idx]
        
        # Get metadata if available
        if pgs_metadata and pgs_id in pgs_metadata:
            meta = pgs_metadata[pgs_id]
            hover_text = (
                f"PGS ID: {pgs_id}<br>"
                f"Name: {meta.get('PGS_Name', 'N/A')}<br>"
                f"Trait: {meta.get('Reported_Trait', 'N/A')}<br>"
                f"Publication: {meta.get('Publication_ID', 'N/A')}"
            )
        else:
            hover_text = f"PGS ID: {pgs_id}"
        
        hover_texts.append(['', hover_text])  # Empty string for the origin point, hover text for the arrow endpoint

    # Add PGS features as vectors (only top contributors)
    for i, idx in enumerate(top_indices):
        fig.add_trace(
            go.Scatter(
                x=[0, Vt[0, idx] * scale_factor],
                y=[0, Vt[1, idx] * scale_factor],
                mode='lines+text',
                line=dict(color='red', width=1),
                text=['', pgs_ids[idx]],
                textposition='top center',
                name=pgs_ids[idx],
                hovertext=hover_texts[i],
                hoverinfo='text'
            )
        )

    # Update layout
    fig.update_layout(
        title=f'SVD Biplot: {stats["score_type"]} Scores (Sample-centered view)',
        xaxis=dict(
            title=f'Component 1 ({stats["explained_variance_ratio"][0]*100:.1f}%)',
            zeroline=True
        ),
        yaxis=dict(
            title=f'Component 2 ({stats["explained_variance_ratio"][1]*100:.1f}%)',
            zeroline=True
        ),
        showlegend=False,
        height=800,
        width=1000,
        hoverlabel=dict(
            bgcolor="white",
            font_size=12,
            font_family="Arial"
        )
    )

    # Add a dashed circle to indicate scale
    theta = np.linspace(0, 2*np.pi, 100)
    radius = np.percentile(np.sqrt(np.sum(U_scaled**2, axis=1)), 75)
    fig.add_trace(
        go.Scatter(
            x=radius * np.cos(theta),
            y=radius * np.sin(theta),
            mode='lines',
            line=dict(color='gray', dash='dash', width=1),
            name='Scale Reference',
            hoverinfo='skip'
        )
    )

    return fig

def generate_svd_biplot_score(U, S, Vt, pgs_ids, sample_ids, stats, pgs_metadata=None, data_dict=None, max_vectors=20):
    """Generate a biplot to visualize PGS scores and samples in the same 2D space"""
    # Number of components to use (typically 2 for a 2D plot)
    n_components = 2
    
    # Scale the singular vectors by the singular values
    Vt_scaled = Vt[:n_components, :].T * S[:n_components]
    
    # Create figure
    fig = go.Figure()
    
    # Create hover text for PGS points
    hover_text = []
    for i, pgs_id in enumerate(pgs_ids):
        # Get metadata for this PGS ID
        if pgs_metadata and pgs_id in pgs_metadata:
            meta = pgs_metadata[pgs_id]
            
            # Calculate average score if data_dict is available
            avg_score_text = ""
            if data_dict:
                scores = [data_dict[sample_id].get(pgs_id, np.nan) for sample_id in sample_ids]
                avg_score = np.nanmean([s for s in scores if not np.isnan(s)])
                avg_score_text = f"<br>Avg Score: {avg_score:.4f}"
            
            hover_info = (
                f"PGS ID: {pgs_id}<br>"
                f"Name: {meta.get('PGS_Name', 'N/A')}<br>"
                f"Trait: {meta.get('Reported_Trait', 'N/A')}<br>"
                f"Publication: {meta.get('Publication_ID', 'N/A')}"
                f"{avg_score_text}"
            )
        else:
            hover_info = f"PGS ID: {pgs_id}"
            
        hover_text.append(hover_info)
    
    # Add PGS scores as scatter points
    fig.add_trace(
        go.Scatter(
            x=Vt_scaled[:, 0],
            y=Vt_scaled[:, 1],
            mode='markers+text',
            marker=dict(
                size=5,
                color='red',
                opacity=0.6
            ),
            name='PGS Scores',
            text=pgs_ids,
            textposition="top center",
            hovertext=hover_text,
            hoverinfo='text'
        )
    )
    
    # Calculate scaling factor for sample vectors
    scale_factor = np.percentile(np.abs(Vt_scaled), 95) / np.percentile(np.abs(U[:, :n_components]), 95) * 0.5
    
    # Find top contributing samples
    if len(sample_ids) > max_vectors:
        # Calculate contribution of each sample to the first 2 components
        sample_contributions = np.sum(U[:, :n_components]**2, axis=1)
        # Get indices of top contributors
        top_indices = np.argsort(sample_contributions)[::-1][:max_vectors]
    else:
        # If fewer samples than max_vectors, use all of them
        top_indices = range(len(sample_ids))
    
    # Add samples as vectors (only top contributors)
    for idx in top_indices:
        fig.add_trace(
            go.Scatter(
                x=[0, U[idx, 0] * scale_factor],
                y=[0, U[idx, 1] * scale_factor],
                mode='lines',  # Removed text to make the plot cleaner
                line=dict(color='blue', width=1),
                name=sample_ids[idx],
                hoverinfo='name'
            )
        )
    
    # Update layout
    fig.update_layout(
        title=f'SVD Biplot: {stats["score_type"]} Scores (Score-centered view)',
        xaxis=dict(
            title=f'Component 1 ({stats["explained_variance_ratio"][0]*100:.1f}%)',
            zeroline=True
        ),
        yaxis=dict(
            title=f'Component 2 ({stats["explained_variance_ratio"][1]*100:.1f}%)',
            zeroline=True
        ),
        showlegend=False,
        height=800,
        width=1000,
        hoverlabel=dict(
            bgcolor="white",
            font_size=12,
            font_family="Arial"
        )
    )
    
    # Add a dashed circle to indicate scale
    theta = np.linspace(0, 2*np.pi, 100)
    radius = np.percentile(np.sqrt(np.sum(Vt_scaled**2, axis=1)), 75)
    fig.add_trace(
        go.Scatter(
            x=radius * np.cos(theta),
            y=radius * np.sin(theta),
            mode='lines',
            line=dict(color='gray', dash='dash', width=1),
            name='Scale Reference',
            hoverinfo='skip'
        )
    )
    
    return fig

def generate_svd_component_weights(Vt, pgs_ids, stats):
    """Generate a visualization of component weights (loadings) for top components"""
    # Number of components to visualize
    n_components = min(5, Vt.shape[0])
    
    # Number of top PGS IDs to show per component
    n_top_pgs = min(20, len(pgs_ids))
    
    # Create subplots, one for each component
    fig = make_subplots(
        rows=n_components, 
        cols=1,
        subplot_titles=[f'Component {i+1} ({stats["explained_variance_ratio"][i]*100:.1f}%)' 
                        for i in range(n_components)]
    )
    
    # For each component, show the top contributing PGS scores
    for i in range(n_components):
        # Sort PGS IDs by absolute contribution to this component
        sorted_indices = np.argsort(np.abs(Vt[i, :]))[::-1][:n_top_pgs]
        
        # Get the weights and corresponding PGS IDs
        weights = Vt[i, sorted_indices]
        component_pgs_ids = [pgs_ids[idx] for idx in sorted_indices]
        
        # Add bar chart for this component
        fig.add_trace(
            go.Bar(
                x=component_pgs_ids,
                y=weights,
                marker_color=['red' if w < 0 else 'green' for w in weights],
                name=f'Component {i+1}'
            ),
            row=i+1, 
            col=1
        )
    
    # Update layout
    fig.update_layout(
        title=f'SVD Component Weights: {stats["score_type"]} Scores',
        height=300 * n_components,
        width=1000,
        showlegend=False
    )
    
    # Update axes
    for i in range(n_components):
        fig.update_xaxes(title_text="PGS ID", row=i+1, col=1)
        fig.update_yaxes(title_text="Loading Weight", row=i+1, col=1)
    
    return fig

def generate_svd_heatmap(Vt, pgs_ids, stats):
    """Generate a heatmap of component loadings"""
    # Number of components to visualize
    n_components = min(10, Vt.shape[0])
    
    # Number of top PGS IDs to show
    n_top_pgs = min(50, len(pgs_ids))
    
    # Get the top contributing PGS IDs across all components
    overall_importance = np.sum(Vt[:n_components, :]**2, axis=0)
    top_indices = np.argsort(overall_importance)[::-1][:n_top_pgs]
    
    # Extract the submatrix for visualization
    heatmap_data = Vt[:n_components, top_indices]
    
    # Get corresponding PGS IDs
    heatmap_pgs_ids = [pgs_ids[idx] for idx in top_indices]
    
    # Create heatmap
    fig = go.Figure(data=go.Heatmap(
        z=heatmap_data,
        x=heatmap_pgs_ids,
        y=[f'Component {i+1} ({stats["explained_variance_ratio"][i]*100:.1f}%)' for i in range(n_components)],
        colorscale='RdBu',
        zmid=0,
        text=[[f'PGS: {pgs_id}<br>Component: {i+1}<br>Weight: {weight:.3f}' 
              for pgs_id, weight in zip(heatmap_pgs_ids, row)] 
              for i, row in enumerate(heatmap_data)],
        hoverinfo='text'
    ))
    
    # Update layout
    fig.update_layout(
        title=f'SVD Component Loading Heatmap: {stats["score_type"]} Scores',
        xaxis=dict(
            title='PGS ID',
            tickangle=45
        ),
        yaxis=dict(
            title='Component',
            autorange='reversed'
        ),
        height=600,
        width=1200
    )
    
    return fig

def generate_svd_combined(U, S, Vt, pgs_ids, sample_ids, stats):
    """Generate a combined visualization with multiple SVD plots"""
    # Create a figure with subplots
    fig = make_subplots(
        rows=2, 
        cols=2,
        subplot_titles=[
            "Scree Plot", 
            "Biplot (PC1 vs PC2)",
            "Top PGS Contributions to PC1", 
            "Component Loading Heatmap"
        ],
        specs=[
            [{"type": "xy"}, {"type": "xy"}],
            [{"type": "xy"}, {"type": "heatmap"}]
        ]
    )
    
    # 1. Scree plot
    explained_variance_ratio = stats["explained_variance_ratio"]
    cumulative_variance = stats["cumulative_variance"]
    
    # Bar chart for individual explained variance
    fig.add_trace(
        go.Bar(
            x=list(range(1, min(11, len(S))+1)),
            y=explained_variance_ratio[:10],
            name="Explained Variance"
        ),
        row=1, col=1
    )
    
    # Line chart for cumulative explained variance
    fig.add_trace(
        go.Scatter(
            x=list(range(1, min(11, len(S))+1)),
            y=cumulative_variance[:10],
            name="Cumulative Variance",
            mode="lines+markers"
        ),
        row=1, col=1
    )
    
    # 2. Biplot
    n_components = 2
    U_scaled = U[:, :n_components] * S[:n_components]
    
    # Add samples as scatter points
    fig.add_trace(
        go.Scatter(
            x=U_scaled[:, 0],
            y=U_scaled[:, 1],
            mode='markers',
            marker=dict(size=5, opacity=0.6),
            name='Samples'
        ),
        row=1, col=2
    )
    
    # Add a few key PGS features as vectors
    scale_factor = np.percentile(np.abs(U_scaled), 95) / np.percentile(np.abs(Vt[:n_components, :]), 95) * 0.5
    
    # Find the top 10 contributors to PC1 and PC2
    pc_importance = Vt[0, :]**2 + Vt[1, :]**2
    top_indices = np.argsort(pc_importance)[::-1][:10]
    
    for idx in top_indices:
        pgs_id = pgs_ids[idx]
        fig.add_trace(
            go.Scatter(
                x=[0, Vt[0, idx] * scale_factor],
                y=[0, Vt[1, idx] * scale_factor],
                mode='lines+text',
                line=dict(width=1),
                text=['', pgs_id],
                textposition='top center',
                name=pgs_id
            ),
            row=1, col=2
        )
    
    # 3. Top PGS contributions to PC1
    n_top_pgs = 15
    sorted_indices = np.argsort(np.abs(Vt[0, :]))[::-1][:n_top_pgs]
    weights = Vt[0, sorted_indices]
    component_pgs_ids = [pgs_ids[idx] for idx in sorted_indices]
    
    fig.add_trace(
        go.Bar(
            x=component_pgs_ids,
            y=weights,
            marker_color=['red' if w < 0 else 'green' for w in weights],
            name='PC1 Weights'
        ),
        row=2, col=1
    )
    
    # 4. Heatmap of top components
    n_components_heatmap = min(5, Vt.shape[0])
    n_top_pgs_heatmap = min(20, len(pgs_ids))
    
    overall_importance = np.sum(Vt[:n_components_heatmap, :]**2, axis=0)
    top_indices_heatmap = np.argsort(overall_importance)[::-1][:n_top_pgs_heatmap]
    
    heatmap_data = Vt[:n_components_heatmap, top_indices_heatmap]
    heatmap_pgs_ids = [pgs_ids[idx] for idx in top_indices_heatmap]
    
    fig.add_trace(
        go.Heatmap(
            z=heatmap_data,
            x=heatmap_pgs_ids,
            y=[f'PC{i+1}' for i in range(n_components_heatmap)],
            colorscale='RdBu',
            zmid=0
        ),
        row=2, col=2
    )
    
    # Update layout
    fig.update_layout(
        title=f'SVD Analysis of {stats["score_type"]} Scores ({stats["num_pgs_ids"]} PGS IDs, {stats["num_samples"]} Samples)',
        height=1000,
        width=1200,
        showlegend=False
    )
    
    # Update axes
    fig.update_xaxes(title_text="Component", row=1, col=1)
    fig.update_yaxes(title_text="Explained Variance", row=1, col=1)
    
    fig.update_xaxes(title_text=f"PC1 ({explained_variance_ratio[0]*100:.1f}%)", row=1, col=2)
    fig.update_yaxes(title_text=f"PC2 ({explained_variance_ratio[1]*100:.1f}%)", row=1, col=2)
    
    fig.update_xaxes(title_text="PGS ID", row=2, col=1, tickangle=45)
    fig.update_yaxes(title_text="Component Weight", row=2, col=1)
    
    fig.update_xaxes(title_text="PGS ID", row=2, col=2, tickangle=45)
    
    return fig

def generate_svd_hash(score_type, pgs_ids, cohort, plot_type, perspective, max_vectors):
    """Generate a hash for the SVD request parameters for caching"""
    params = {
        "score_type": score_type,
        "pgs_ids": sorted(pgs_ids) if pgs_ids else "all",
        "cohort": cohort if cohort else "ALL",
        "plot_type": plot_type,
        "perspective": perspective,
        "max_vectors": max_vectors
    }
    param_str = json.dumps(params, sort_keys=True)
    hash_obj = hashlib.md5(param_str.encode())
    return hash_obj.hexdigest()

@app.get("/api/permanent_cohorts")
async def get_permanent_cohorts():
    """Get list of permanent cohorts from the cohorts directory."""
    cohorts_dir = "/Users/nsabry/PGSVisualizer/cohorts"
    
    if not os.path.exists(cohorts_dir):
        return {"cohorts": []}
    
    cohort_list = []
    
    # Look for text files in the cohorts directory
    for filename in os.listdir(cohorts_dir):
        if not filename.endswith(".txt"):
            continue
            
        # Extract cohort name from filename
        name = filename.replace(".txt", "")
        filepath = os.path.join(cohorts_dir, filename)
        
        # Read sample IDs from file
        try:
            with open(filepath, "r") as f:
                sample_ids = [line.strip() for line in f if line.strip()]
                
            if sample_ids:
                cohort_list.append({
                    "name": name,
                    "sample_ids": sample_ids
                })
        except Exception as e:
            print(f"Error reading cohort file {filename}: {e}")
    
    return {"cohorts": cohort_list}

@app.post("/api/generate_distribution")
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

def process_distribution(request_data):
    """
    Generate distribution plots on the backend, cache them, and return the plot path.
    The function calculates a hash of the request to check if it's already been processed.
    """
    try:
        # Create a hash of the request to use as the filename
        request_hash = hashlib.md5(json.dumps(request_data, sort_keys=True).encode()).hexdigest()
        os.makedirs("temp", exist_ok=True)

        html_path = f"temp/{request_hash}.html"
        json_path = f"temp/{request_hash}.json"
        
        # Check if this exact plot has been generated recently
        if os.path.exists(html_path) and os.path.exists(json_path):
            # Return the cached file path
            return f"/{html_path}"
        
        # Connect to the database
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            # Handle cohort analysis
            if request_data["analysis_type"] == 'cohort':
                pgs_id = request_data.get("pgs_id", "")
                score_type = request_data.get("score_type", "")
                cohorts = request_data.get("cohorts", [])
                chart_type = request_data.get("chart_type", "")
                plot_title = request_data.get("plot_title", "")
                
                if not pgs_id or not score_type or not cohorts:
                    raise ValueError("Missing required fields for cohort analysis")
                
                # Retrieve scores for the given PGS and score type
                cursor.execute(
                    "SELECT SAMPLE_ID, SCORE FROM scores WHERE PGS_ID = ? AND SCORE_TYPE = ?",
                    (pgs_id, score_type)
                )
                rows = cursor.fetchall()
                
                if not rows:
                    raise ValueError(f"No data found for PGS '{pgs_id}' and Score Type '{score_type}'")
                
                # Create a dictionary mapping SAMPLE_ID to SCORE
                score_dict = {row["SAMPLE_ID"]: row["SCORE"] for row in rows}
                
                cohort_data = []
                for cohort in cohorts:
                    # Filter to include only samples that exist in our data
                    valid_samples = [
                        {"SAMPLE_ID": sample_id, "SCORE": score_dict[sample_id]}
                        for sample_id in cohort["sample_ids"]
                        if sample_id in score_dict
                    ]
                    
                    cohort_scores = [sample["SCORE"] for sample in valid_samples]
                    
                    cohort_data.append({
                        "color": cohort["color"],
                        "values": cohort_scores,
                        "samples": valid_samples,
                        "name": cohort["name"]
                    })
                
                # Create Plotly figure based on chart_type
                fig = go.Figure()
                
                if chart_type == 'density':
                    # Create a common x-axis range for all distributions
                    all_values = []
                    for cohort in cohort_data:
                        if cohort["values"]:
                            all_values.extend(cohort["values"])
                    
                    if not all_values:
                        raise ValueError("No valid data to plot")
                    
                    # Determine appropriate range for x-axis with padding
                    min_val = min(all_values)
                    max_val = max(all_values)
                    range_padding = (max_val - min_val) * 0.1
                    x_min = min_val - range_padding
                    x_max = max_val + range_padding
                    
                    # Create evenly spaced x values for the density curves
                    x = np.linspace(x_min, x_max, 100)
                    
                    for cohort in cohort_data:
                        if cohort["values"] and len(cohort["values"]) > 1:
                            # Use kernel density estimation to create smooth curve
                            try:
                                kde = stats.gaussian_kde(cohort["values"])
                                y = kde(x)
                                
                                # Create density curve
                                fig.add_trace(go.Scatter(
                                    x=x,
                                    y=y,
                                    mode='lines',
                                    name=cohort["name"],
                                    line=dict(color=cohort["color"], width=2),
                                    fill=None  # No fill, just the line
                                ))
                                
                            except Exception as e:
                                print(f"Error creating density plot for {cohort['name']}: {str(e)}")
                                continue
                    
                    # Update layout
                    fig.update_layout(
                        title=plot_title,
                        xaxis_title="Score",
                        yaxis_title="Density",
                        hovermode="closest",
                        showlegend=True,
                        legend=dict(
                            x=1.02,
                            y=0.98,
                            xanchor="left",
                            yanchor="top"
                        ),
                        margin=dict(l=60, r=150, t=50, b=50)
                    )

                elif chart_type == 'histogram':
                    # Get all values to determine common axis
                    all_values = []
                    for cohort in cohort_data:
                        if cohort["values"]:
                            all_values.extend(cohort["values"])
                    
                    if not all_values:
                        raise ValueError("No valid data to plot")
                    
                    # Determine appropriate range with padding
                    min_val = min(all_values)
                    max_val = max(all_values)
                    range_padding = (max_val - min_val) * 0.1
                    x_min = min_val - range_padding
                    x_max = max_val + range_padding
                    
                    # Calculate optimal number of bins based on data
                    num_bins = min(30, int(np.ceil(np.sqrt(len(all_values)))))
                    
                    # Create histogram bins
                    bin_size = (x_max - x_min) / num_bins
                    
                    # Add histograms for each cohort
                    for i, cohort in enumerate(cohort_data):
                        if cohort["values"]:
                            fig.add_trace(go.Histogram(
                                x=cohort["values"],
                                name=cohort["name"],
                                marker_color=cohort["color"],
                                opacity=0.7,
                                xbins=dict(
                                    start=x_min,
                                    end=x_max,
                                    size=bin_size
                                ),
                                # Offset bins for each cohort to avoid complete overlap
                                offsetgroup=i
                            ))
                    
                    # Update layout
                    fig.update_layout(
                        title=plot_title,
                        xaxis_title="Score",
                        yaxis_title="Frequency",
                        barmode='group',  # Group bars for different cohorts
                        hovermode="closest",
                        showlegend=True,
                        legend=dict(
                            x=1.02,
                            y=0.98,
                            xanchor="left",
                            yanchor="top"
                        ),
                        margin=dict(l=60, r=150, t=50, b=50)
                    )
                elif chart_type == 'box':
                    # Add boxplots for each cohort
                    for cohort in cohort_data:
                        if cohort["values"] and len(cohort["values"]) > 0:
                            # Calculate boxplot stats
                            values = sorted(cohort["values"])
                            
                            fig.add_trace(go.Box(
                                y=values,
                                name=cohort["name"],
                                boxmean=True,  # Show mean as a dashed line
                                marker_color=cohort["color"],
                                line=dict(color='black'),
                                fillcolor=cohort["color"],
                                opacity=0.7
                            ))
                    
                    # Update layout
                    fig.update_layout(
                        title=plot_title,
                        yaxis_title="Score",
                        xaxis_title="Cohort",
                        hovermode="closest",
                        showlegend=False,
                        margin=dict(l=60, r=150, t=50, b=50)
                    )
                
                # Common layout settings for all chart types
                fig.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0.05)',
                    height=600,
                    width=900
                )
                
                # Save the plot as an HTML file
                fig.write_html(html_path)
                
                # Save the data matrix
                data_matrix = {"cohorts": cohort_data}
                with open(json_path, 'w') as f:
                    json.dump(data_matrix, f)
                
                # Return the file path
                return f"/{html_path}"
                    
            # Handle score comparison
            elif request_data["analysis_type"] == 'score':
                score_type = request_data.get("score_type", "")
                pgs_comparison = request_data.get("pgs_comparison", {})
                chart_type = request_data.get("chart_type", "")
                plot_title = request_data.get("plot_title", "")
                
                if not pgs_comparison or not score_type:
                    raise ValueError("Missing required fields for score comparison")
                
                # For each PGS ID, retrieve the scores for the sample IDs
                pgs_data = []
                for i, pgs_id in enumerate(pgs_comparison.get("pgs_ids", [])):
                    # Retrieve scores for this PGS and the score type
                    cursor.execute(
                        "SELECT SAMPLE_ID, SCORE FROM scores WHERE PGS_ID = ? AND SCORE_TYPE = ?",
                        (pgs_id, score_type)
                    )
                    rows = cursor.fetchall()
                    
                    if not rows:
                        continue  # Skip if no data found for this PGS
                    
                    # Create a dictionary mapping SAMPLE_ID to SCORE
                    score_dict = {row["SAMPLE_ID"]: row["SCORE"] for row in rows}
                    
                    # Filter to include only samples that exist in our data
                    valid_samples = [
                        {"SAMPLE_ID": sample_id, "SCORE": score_dict[sample_id]}
                        for sample_id in pgs_comparison.get("sample_ids", [])
                        if sample_id in score_dict
                    ]
                    
                    scores = [sample["SCORE"] for sample in valid_samples]
                    
                    pgs_data.append({
                        "color": pgs_comparison.get("colors", [])[i] if i < len(pgs_comparison.get("colors", [])) else "#000000",
                        "values": scores,
                        "samples": valid_samples,
                        "name": pgs_comparison.get("names", [])[i] if i < len(pgs_comparison.get("names", [])) else pgs_id
                    })
                
                # Create Plotly figure based on chart_type
                fig = go.Figure()
                
                # Similar plotting logic as for cohorts, but with PGS data
                if chart_type == 'density':
                    # Create a common x-axis range for all distributions
                    all_values = []
                    for pgs in pgs_data:
                        if pgs["values"]:
                            all_values.extend(pgs["values"])
                    
                    if not all_values:
                        raise ValueError("No valid data to plot")
                    
                    # Determine appropriate range for x-axis
                    min_val = min(all_values)
                    max_val = max(all_values)
                    range_padding = (max_val - min_val) * 0.1
                    x_min = min_val - range_padding
                    x_max = max_val + range_padding
                    
                    # Create evenly spaced x values for the density curves
                    x = np.linspace(x_min, x_max, 100)
                    
                    for pgs in pgs_data:
                        if pgs["values"] and len(pgs["values"]) > 1:
                            try:
                                # Use kernel density estimation to create smooth curve
                                kde = stats.gaussian_kde(pgs["values"])
                                y = kde(x)
                                
                                # Create density curve
                                fig.add_trace(go.Scatter(
                                    x=x,
                                    y=y,
                                    mode='lines',
                                    name=pgs["name"],
                                    line=dict(color=pgs["color"], width=2),
                                    fill=None  # No fill, just the line
                                ))
                            except Exception as e:
                                print(f"Error creating density plot for {pgs['name']}: {str(e)}")
                                continue
                    
                    fig.update_layout(
                        title=plot_title,
                        xaxis_title="Score",
                        yaxis_title="Density",
                        hovermode="closest",
                        showlegend=True,
                        legend=dict(
                            x=1.02,
                            y=0.98,
                            xanchor="left",
                            yanchor="top"
                        ),
                        margin=dict(l=60, r=150, t=50, b=50)
                    )

                elif chart_type == 'histogram':
                    # Get all values to determine common axis
                    all_values = []
                    for pgs in pgs_data:
                        if pgs["values"]:
                            all_values.extend(pgs["values"])
                    
                    if not all_values:
                        raise ValueError("No valid data to plot")
                    
                    # Determine appropriate range with padding
                    min_val = min(all_values)
                    max_val = max(all_values)
                    range_padding = (max_val - min_val) * 0.1
                    x_min = min_val - range_padding
                    x_max = max_val + range_padding
                    
                    # Calculate optimal number of bins based on data
                    num_bins = min(30, int(np.ceil(np.sqrt(len(all_values)))))
                    
                    # Create histogram bins
                    bin_size = (x_max - x_min) / num_bins
                    
                    # Add histograms for each PGS
                    for i, pgs in enumerate(pgs_data):
                        if pgs["values"]:
                            fig.add_trace(go.Histogram(
                                x=pgs["values"],
                                name=pgs["name"],
                                marker_color=pgs["color"],
                                opacity=0.7,
                                xbins=dict(
                                    start=x_min,
                                    end=x_max,
                                    size=bin_size
                                ),
                                # Offset bins for each PGS to avoid complete overlap
                                offsetgroup=i
                            ))
                    
                    # Update layout
                    fig.update_layout(
                        title=plot_title,
                        xaxis_title="Score",
                        yaxis_title="Frequency",
                        barmode='group',  # Group bars for different PGS
                        hovermode="closest",
                        showlegend=True,
                        legend=dict(
                            x=1.02,
                            y=0.98,
                            xanchor="left",
                            yanchor="top"
                        ),
                        margin=dict(l=60, r=150, t=50, b=50)
                    )

                elif chart_type == 'box':
                    # Add boxplots for each PGS
                    for pgs in pgs_data:
                        if pgs["values"] and len(pgs["values"]) > 0:
                            # Calculate boxplot stats to match D3 implementation
                            values = sorted(pgs["values"])
                            
                            fig.add_trace(go.Box(
                                y=values,
                                name=pgs["name"],
                                boxmean=True,  # Show mean as a dashed line
                                marker_color=pgs["color"],
                                line=dict(color='black'),
                                fillcolor=pgs["color"],
                                opacity=0.7
                            ))
                    
                    # Update layout
                    fig.update_layout(
                        title=plot_title,
                        yaxis_title="Score",
                        xaxis_title="PGS",
                        hovermode="closest",
                        showlegend=False,  # Legend is less important for boxplots since labels are on x-axis
                        margin=dict(l=60, r=150, t=50, b=50)
                    )
                
                # Common layout settings for all chart types
                fig.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0.05)',
                    height=600,
                    width=900
                )
                
                # Save the plot as an HTML file
                fig.write_html(html_path)
                
                # Save the data matrix
                data_matrix = {"pgs_data": pgs_data}
                with open(json_path, 'w') as f:
                    json.dump(data_matrix, f)
                
                # Return the file path
                return f"/{html_path}"
            
            else:
                raise ValueError(f"Invalid analysis type: {request_data['analysis_type']}")
        
        finally:
            conn.close()
            
    except Exception as e:
        # Log error and re-raise to be caught by background task processor
        print(f"Error in process_distribution: {str(e)}")
        raise e      

def calculate_percentile(value: float, array: List[float]) -> float:
    """Calculate the percentile of a value in an array."""
    sorted_array = sorted(array)
    position = next((i for i, x in enumerate(sorted_array) if x >= value), len(sorted_array))
    
    if position == len(sorted_array):
        return 100.0  # Value is greater than all elements
    
    return (position / len(sorted_array) * 100)

@app.post("/api/generate_subcohort_plot")
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

def process_subcohort_plot(request_data):
    try:
        # Extract parameters from request_data
        pgs_id = request_data["pgs_id"]
        score_type = request_data["score_type"]
        base_cohort = request_data["base_cohort"]
        subcohorts = request_data["subcohorts"]
        plot_title = request_data.get("plot_title", "")
        display_or = request_data.get("display_or", False)
        normalize_bins = request_data.get("normalize_bins", False)
        bin_size = request_data.get("bin_size")
        or_calculation_type = request_data.get("or_calculation_type")
        threshold_value = request_data.get("threshold_value")
        quantile_count = request_data.get("quantile_count")
        decile_count = request_data.get("decile_count")
        
        # Connect to the database
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor() 
        
        try:
            # Retrieve scores for the given PGS and score type
            cursor.execute(
                "SELECT SAMPLE_ID, SCORE FROM scores WHERE PGS_ID = ? AND SCORE_TYPE = ?",
                (pgs_id, score_type)
            )
            rows = cursor.fetchall()
            
            if not rows:
                raise ValueError(f"No data found for PGS '{pgs_id}' and Score Type '{score_type}'")

            # Create a dictionary mapping SAMPLE_ID to SCORE
            score_dict = {row["SAMPLE_ID"]: row["SCORE"] for row in rows}
            
            # Get base cohort sample IDs from ancestry groups
            cursor.execute("SELECT sample_ids FROM ancestry_groups WHERE population = ?", (base_cohort,))
            cohort_result = cursor.fetchone()

            if not cohort_result:
                raise ValueError(f"Base cohort '{base_cohort}' not found in database")

            # Parse the JSON array of sample IDs
            base_sample_ids = json.loads(cohort_result[0])

            # Filter to include only samples that exist in our data
            base_valid_samples = [
                {"SAMPLE_ID": sample_id, "SCORE": score_dict[sample_id]}
                for sample_id in base_sample_ids
                if sample_id in score_dict
            ]
            
            base_scores = [sample["SCORE"] for sample in base_valid_samples]
            
            # Process subcohorts
            subcohort_data = []
            table_data = []
            
            for subcohort in subcohorts:
                if not subcohort.get("active", True):
                    continue
                    
                # Filter to include only samples that exist in our data
                valid_samples = [
                    {"SAMPLE_ID": sample_id, "SCORE": score_dict[sample_id]}
                    for sample_id in subcohort["sample_ids"]
                    if sample_id in score_dict
                ]
                
                subcohort_scores = [sample["SCORE"] for sample in valid_samples]
                
                # Calculate percentiles relative to base distribution
                for sample in valid_samples:
                    percentile = calculate_percentile(sample["SCORE"], base_scores)
                    table_data.append({
                        "SAMPLE_ID": sample["SAMPLE_ID"],
                        "SCORE": f"{sample['SCORE']:.4f}",
                        "PERCENTILE": f"{percentile:.2f}",
                        "SUBCOHORT": subcohort["name"]
                    })
                
                subcohort_data.append({
                    "name": subcohort["name"],
                    "color": subcohort["color"],
                    "values": subcohort_scores
                })
        finally:
            conn.close()
        
        # Generate plot using Plotly
        fig = make_subplots(specs=[[{"secondary_y": display_or}]])
        
        # Set plot dimensions
        fig.update_layout(
            title=plot_title or f"Distribution of {pgs_id} - {score_type}",
            xaxis_title="Score",
            yaxis_title="Density" if not normalize_bins else "Proportion of Samples",
            width=1000,
            height=600,
            margin=dict(l=60, r=160, t=50, b=50),
            legend=dict(x=1.05, y=0.5),
            template="plotly_white"
        )
        
        # Add base cohort density curve
        kde_xs = np.linspace(min(base_scores), max(base_scores), 1000)
        kde = stats.gaussian_kde(base_scores)
        kde_ys = kde(kde_xs)
        
        fig.add_trace(
            go.Scatter(
                x=kde_xs,
                y=kde_ys,
                mode="lines",
                line=dict(color="#1f77b4", width=2),
                name=f"{base_cohort} ({len(base_scores)} samples, density)"
            )
        )
        
        # Calculate histogram bins
        bin_size_value = bin_size or 30
        bins = np.histogram_bin_edges(
            np.concatenate([base_scores] + [sc["values"] for sc in subcohort_data]),
            bins=bin_size_value
        )
        
        # Add subcohort histograms
        for subcohort in subcohort_data:
            hist, _ = np.histogram(subcohort["values"], bins=bins)
            
            # Normalize if requested
            if normalize_bins:
                hist = hist / len(subcohort["values"])
                
            fig.add_trace(
                go.Bar(
                    x=[(bins[i] + bins[i+1])/2 for i in range(len(bins)-1)],
                    y=hist,
                    opacity=0.6,
                    width=bins[1]-bins[0],
                    name=f"{subcohort['name']} ({len(subcohort['values'])} samples)",
                    marker_color=subcohort["color"],
                    marker_line_color="black",
                    marker_line_width=0.5
                )
            )
        
        # Add odds ratio calculation if requested
        if display_or and len(subcohort_data) == 2:
            data = subcohort_data  # Just using the values and names
            
            if or_calculation_type == "bin":
                # Calculate OR by bin (cumulative)
                or_result = calculate_OR_by_bin_cumulative(data, bin_size)
                
                # Add OR line and CI area
                fig.add_trace(
                    go.Scatter(
                        x=[d["x"] for d in or_result["oddsRatios"]],
                        y=[d["or"] for d in or_result["oddsRatios"]],
                        mode="lines",
                        line=dict(color="red", width=2),
                        name=f"OR: {data[0]['name']} vs {data[1]['name']}",
                        yaxis="y2"
                    )
                )
                
                fig.add_trace(
                    go.Scatter(
                        x=[d["x"] for d in or_result["confidenceIntervals"]],
                        y=[d["y1"] for d in or_result["confidenceIntervals"]],
                        mode="lines",
                        line=dict(width=0),
                        showlegend=False,
                        yaxis="y2"
                    )
                )
                
                fig.add_trace(
                    go.Scatter(
                        x=[d["x"] for d in or_result["confidenceIntervals"]],
                        y=[d["y0"] for d in or_result["confidenceIntervals"]],
                        mode="lines",
                        line=dict(width=0),
                        fillcolor="rgba(255, 0, 0, 0.2)",
                        fill="tonexty",
                        name="95% CI",
                        yaxis="y2"
                    )
                )
                
            elif or_calculation_type == "quantile":
                # Calculate OR by quantile (cumulative)
                quantile_count = quantile_count or 10
                or_result = calculate_OR_by_quantile_cumulative(data, quantile_count)
                
                # Add vertical lines at quantile breakpoints
                for i, d in enumerate(or_result["oddsRatios"]):
                    if i > 0:  # Skip first point
                        fig.add_shape(
                            type="line",
                            x0=d["x"], x1=d["x"],
                            y0=0, y1=1,
                            yref="paper",
                            line=dict(color="#aaa", width=1, dash="dash"),
                            opacity=0.4
                        )
                
                # Add OR points and CI lines
                for d in or_result["oddsRatios"]:
                    fig.add_trace(
                        go.Scatter(
                            x=[d["x"]],
                            y=[d["or"]],
                            mode="markers",
                            marker=dict(color="red", size=8),
                            showlegend=False,
                            yaxis="y2"
                        )
                    )
                    
                    fig.add_shape(
                        type="line",
                        x0=d["x"], x1=d["x"],
                        y0=d["ci95low"], y1=d["ci95high"],
                        line=dict(color="red", width=2),
                        yref="y2"
                    )
                
                # Add OR to legend
                fig.add_trace(
                    go.Scatter(
                        x=[None],
                        y=[None],
                        mode="markers",
                        marker=dict(color="red", size=8),
                        name=f"OR: {data[0]['name']} vs {data[1]['name']}",
                        yaxis="y2"
                    )
                )
                
                fig.add_trace(
                    go.Scatter(
                        x=[None],
                        y=[None],
                        mode="lines",
                        line=dict(color="red", width=2),
                        name="95% CI",
                        yaxis="y2"
                    )
                )
                
            elif or_calculation_type == "threshold":
                # Calculate OR by threshold
                threshold = threshold_value or 0
                or_result = calculate_OR_by_threshold(data, threshold)
                
                # Add threshold line
                fig.add_shape(
                    type="line",
                    x0=or_result["threshold"], x1=or_result["threshold"],
                    y0=0, y1=1,
                    yref="paper",
                    line=dict(color="blue", width=1, dash="dash"),
                    opacity=0.8
                )
                
                # Add OR point and CI line
                fig.add_trace(
                    go.Scatter(
                        x=[or_result["threshold"]],
                        y=[or_result["or"]],
                        mode="markers",
                        marker=dict(color="red", size=8),
                        name=f"OR at {or_result['threshold']:.2f}: {or_result['or']:.2f} ({data[0]['name']} vs {data[1]['name']})",
                        yaxis="y2"
                    )
                )
                
                fig.add_shape(
                    type="line",
                    x0=or_result["threshold"], x1=or_result["threshold"],
                    y0=or_result["ci95low"], y1=or_result["ci95high"],
                    line=dict(color="red", width=2),
                    yref="y2"
                )
                
                # Add CI to legend
                fig.add_trace(
                    go.Scatter(
                        x=[None],
                        y=[None],
                        mode="lines",
                        line=dict(color="red", width=2),
                        name=f"95% CI: [{or_result['ci95low']:.2f}, {or_result['ci95high']:.2f}]",
                        yaxis="y2"
                    )
                )
                
            elif or_calculation_type == "decileBaseline":
                # Calculate OR by decile vs baseline
                decile_count = decile_count or 10
                or_result = calculate_OR_by_decile_vs_baseline(data, decile_count)
                
                # Add decile markers
                for i, breakpoint in enumerate(or_result["decileBreakpoints"]):
                    if i > 0:  # Skip first point (minimum value)
                        fig.add_shape(
                            type="line",
                            x0=breakpoint, x1=breakpoint,
                            y0=0, y1=1,
                            yref="paper",
                            line=dict(color="#aaa", width=1, dash="dash"),
                            opacity=0.4
                        )
                        
                        # Add decile label
                        fig.add_annotation(
                            x=breakpoint,
                            y=0,
                            yref="paper",
                            text=f"D{i+1}",
                            showarrow=False,
                            font=dict(size=8),
                            yshift=-15
                        )
                
                # Add OR points and CI lines
                x_values = []
                or_values = []
                
                for d in or_result["oddsRatios"]:
                    x_values.append(d["x"])
                    or_values.append(d["or"])
                    
                    fig.add_trace(
                        go.Scatter(
                            x=[d["x"]],
                            y=[d["or"]],
                            mode="markers",
                            marker=dict(color="red", size=8),
                            showlegend=False,
                            yaxis="y2"
                        )
                    )
                    
                    fig.add_shape(
                        type="line",
                        x0=d["x"], x1=d["x"],
                        y0=d["ci95low"], y1=d["ci95high"],
                        line=dict(color="red", width=2),
                        yref="y2"
                    )
                
                # Connect points with line
                fig.add_trace(
                    go.Scatter(
                        x=x_values,
                        y=or_values,
                        mode="lines",
                        line=dict(color="red", width=1.5, dash="dash"),
                        name=f"OR by Decile vs Baseline: {data[0]['name']} vs {data[1]['name']}",
                        yaxis="y2"
                    )
                )
                
                # Add CI to legend
                fig.add_trace(
                    go.Scatter(
                        x=[None],
                        y=[None],
                        mode="lines",
                        line=dict(color="red", width=2),
                        name="95% CI",
                        yaxis="y2"
                    )
                )
                
            elif or_calculation_type == "decileCumulative":
                # Calculate OR by decile vs cumulative lower deciles
                decile_count = decile_count or 10
                or_result = calculate_OR_by_decile_vs_cumulative(data, decile_count)
                
                # Add decile markers
                for i, breakpoint in enumerate(or_result["decileBreakpoints"]):
                    if i > 0:  # Skip first point (minimum value)
                        fig.add_shape(
                            type="line",
                            x0=breakpoint, x1=breakpoint,
                            y0=0, y1=1,
                            yref="paper",
                            line=dict(color="#aaa", width=1, dash="dash"),
                            opacity=0.4
                        )
                        
                        # Add decile label
                        fig.add_annotation(
                            x=breakpoint,
                            y=0,
                            yref="paper",
                            text=f"D{i+1}",
                            showarrow=False,
                            font=dict(size=8),
                            yshift=-15
                        )
                
                # Add OR points and CI lines
                x_values = []
                or_values = []
                
                for d in or_result["oddsRatios"]:
                    x_values.append(d["x"])
                    or_values.append(d["or"])
                    
                    fig.add_trace(
                        go.Scatter(
                            x=[d["x"]],
                            y=[d["or"]],
                            mode="markers",
                            marker=dict(color="purple", size=8),
                            showlegend=False,
                            yaxis="y2"
                        )
                    )
                    
                    fig.add_shape(
                        type="line",
                        x0=d["x"], x1=d["x"],
                        y0=d["ci95low"], y1=d["ci95high"],
                        line=dict(color="purple", width=2),
                        yref="y2"
                    )
                
                # Connect points with line
                fig.add_trace(
                    go.Scatter(
                        x=x_values,
                        y=or_values,
                        mode="lines",
                        line=dict(color="purple", width=1.5, dash="dash"),
                        name=f"OR by Decile vs Cumulative Lower: {data[0]['name']} vs {data[1]['name']}",
                        yaxis="y2"
                    )
                )
                
                # Add CI to legend
                fig.add_trace(
                    go.Scatter(
                        x=[None],
                        y=[None],
                        mode="lines",
                        line=dict(color="purple", width=2),
                        name="95% CI",
                        yaxis="y2"
                    )
                )
            
            # Configure secondary y-axis for OR
            fig.update_layout(
                yaxis2=dict(
                    title="Odds Ratio",
                    side="right",
                    type="log",
                    overlaying="y",
                    showgrid=False
                )
            )
            
            # Add reference line at OR = 1
            fig.add_shape(
                type="line",
                x0=0, x1=1,
                y0=1, y1=1,
                xref="paper",
                yref="y2",
                line=dict(color="black", width=1, dash="dash"),
                opacity=0.6
            )
    
        # Save plot to file
        plot_id = str(uuid.uuid4())
        plot_dir = "temp"
        os.makedirs(plot_dir, exist_ok=True)
        plot_path = os.path.join(plot_dir, f"{plot_id}.html")
        
        fig.write_html(plot_path, include_plotlyjs="cdn")
        
        # Return the file path
        return f"/temp/{plot_id}.html"
        
    except Exception as e:
        # Log the error
        print(f"Error generating subcohort plot: {str(e)}")
        raise e

# OR calculation functions
def calculate_OR_by_bin_cumulative(data, bin_size):
    """Calculate odds ratio by histogram bin (cumulative)."""
    all_values = data[0]["values"] + data[1]["values"]
    domain = [min(all_values), max(all_values)]
    
    # Create histogram bins
    bin_edges = np.linspace(domain[0], domain[1], bin_size + 1)
    
    odds_ratios = []
    confidence_intervals = []
    
    # For each bin threshold, calculate OR cumulatively
    for i in range(len(bin_edges) - 1):
        threshold = bin_edges[i]
        
        # Count values greater than or equal to threshold
        a = sum(1 for v in data[0]["values"] if v >= threshold)
        b = len(data[0]["values"]) - a
        c = sum(1 for v in data[1]["values"] if v >= threshold)
        d = len(data[1]["values"]) - c
        
        # Add small constant to avoid division by zero
        epsilon = 0.5
        
        # Calculate odds ratio
        or_value = ((a + epsilon) * (d + epsilon)) / ((b + epsilon) * (c + epsilon))
        
        # Calculate 95% CI
        log_or = np.log(or_value)
        se_log_or = np.sqrt(1/(a + epsilon) + 1/(b + epsilon) + 1/(c + epsilon) + 1/(d + epsilon))
        ci95low = np.exp(log_or - 1.96 * se_log_or)
        ci95high = np.exp(log_or + 1.96 * se_log_or)
        
        odds_ratios.append({
            "x": float(threshold),
            "or": float(or_value),
            "ci95low": float(ci95low),
            "ci95high": float(ci95high)
        })
        
        confidence_intervals.append({
            "x": float(threshold),
            "y0": float(ci95low),
            "y1": float(ci95high)
        })
    
    return {"oddsRatios": odds_ratios, "confidenceIntervals": confidence_intervals}

def calculate_OR_by_quantile_cumulative(data, num_quantiles):
    """Calculate odds ratio by quantiles (cumulative)."""
    all_values = data[0]["values"] + data[1]["values"]
    
    # Calculate quantile breakpoints
    quantile_breaks = [np.quantile(all_values, i / num_quantiles) for i in range(1, num_quantiles)]
    
    # Add min and max to create complete range
    min_value = min(all_values)
    max_value = max(all_values)
    
    odds_ratios = []
    confidence_intervals = []
    
    # Start with the minimum value
    a0 = len(data[0]["values"])  # All values
    b0 = 0  # Should be 0
    c0 = len(data[1]["values"])  # All values
    d0 = 0  # Should be 0
    
    # Add small constant to avoid division by zero
    epsilon = 0.5
    or0 = ((a0 + epsilon) * (d0 + epsilon)) / ((b0 + epsilon) * (c0 + epsilon))
    
    # Calculate 95% CI
    log_or0 = np.log(or0)
    se_log_or0 = np.sqrt(1/(a0 + epsilon) + 1/(b0 + epsilon) + 1/(c0 + epsilon) + 1/(d0 + epsilon))
    ci95low0 = np.exp(log_or0 - 1.96 * se_log_or0)
    ci95high0 = np.exp(log_or0 + 1.96 * se_log_or0)
    
    odds_ratios.append({
        "x": float(min_value),
        "or": float(or0),
        "ci95low": float(ci95low0),
        "ci95high": float(ci95high0)
    })
    
    confidence_intervals.append({
        "x": float(min_value),
        "y0": float(ci95low0),
        "y1": float(ci95high0)
    })
    
    # For each quantile threshold, calculate cumulative OR
    for i in range(len(quantile_breaks) - 1):
        threshold = quantile_breaks[i]
        upper_bound = quantile_breaks[i + 1]
        
        # Count values above threshold for both cohorts
        a = sum(1 for v in data[0]["values"] if v >= threshold)
        b = len(data[0]["values"]) - a
        c = sum(1 for v in data[1]["values"] if v >= threshold)
        d = len(data[1]["values"]) - c
        
        # Add small constant to avoid division by zero
        epsilon = 0.5
        
        # Calculate odds ratio
        or_value = ((a + epsilon) * (d + epsilon)) / ((b + epsilon) * (c + epsilon))
        
        # Calculate 95% CI
        log_or = np.log(or_value)
        se_log_or = np.sqrt(1/(a + epsilon) + 1/(b + epsilon) + 1/(c + epsilon) + 1/(d + epsilon))
        ci95low = np.exp(log_or - 1.96 * se_log_or)
        ci95high = np.exp(log_or + 1.96 * se_log_or)
        
        odds_ratios.append({
            "x": float(threshold),
            "or": float(or_value),
            "ci95low": float(ci95low),
            "ci95high": float(ci95high)
        })
        
        confidence_intervals.append({
            "x": float(threshold),
            "y0": float(ci95low),
            "y1": float(ci95high)
        })
    
    return {"oddsRatios": odds_ratios, "confidenceIntervals": confidence_intervals}

def calculate_OR_by_threshold(data, threshold):
    """Calculate odds ratio at a specific threshold."""
    # Count values above/below threshold for both subcohorts
    a = sum(1 for v in data[0]["values"] if v >= threshold)
    b = len(data[0]["values"]) - a
    c = sum(1 for v in data[1]["values"] if v >= threshold)
    d = len(data[1]["values"]) - c
    
    # Add small constant to avoid division by zero
    epsilon = 0.5
    
    # Calculate odds ratio
    or_value = ((a + epsilon) * (d + epsilon)) / ((b + epsilon) * (c + epsilon))
    
    # Calculate 95% CI
    log_or = np.log(or_value)
    se_log_or = np.sqrt(1/(a + epsilon) + 1/(b + epsilon) + 1/(c + epsilon) + 1/(d + epsilon))
    ci95low = np.exp(log_or - 1.96 * se_log_or)
    ci95high = np.exp(log_or + 1.96 * se_log_or)
    
    return {
        "threshold": float(threshold),
        "or": float(or_value),
        "ci95low": float(ci95low), 
        "ci95high": float(ci95high)
    }

def calculate_OR_by_decile_vs_baseline(data, num_deciles=10):
    """Calculate odds ratio by decile compared to baseline (1st decile)."""
    # Combine all values to determine decile breakpoints
    all_values = data[0]["values"] + data[1]["values"]
    all_values.sort()
    
    # Calculate decile breakpoints
    decile_breakpoints = [np.quantile(all_values, i / num_deciles) for i in range(num_deciles + 1)]
    
    # Create containers for counts in each decile
    cases_by_decile = [0] * num_deciles
    ctrls_by_decile = [0] * num_deciles
    
    # Assign values to appropriate deciles
    for value in data[0]["values"]:
        decile_index = next((i for i in range(1, len(decile_breakpoints)) 
                            if value < decile_breakpoints[i]), len(decile_breakpoints) - 1) - 1
        cases_by_decile[decile_index] += 1
    
    for value in data[1]["values"]:
        decile_index = next((i for i in range(1, len(decile_breakpoints)) 
                            if value < decile_breakpoints[i]), len(decile_breakpoints) - 1) - 1
        ctrls_by_decile[decile_index] += 1
    
    # Calculate baseline odds (1st decile)
    baseline_cases = cases_by_decile[0]
    baseline_ctrls = ctrls_by_decile[0]
    
    # Calculate odds ratios for each decile compared to baseline
    odds_ratios = []
    confidence_intervals = []
    
    for i in range(num_deciles):
        # Values for the current decile
        a = cases_by_decile[i]
        b = ctrls_by_decile[i]
        
        # Values for the baseline (1st decile)
        c = baseline_cases
        d = baseline_ctrls
        
        # Add small constant to avoid division by zero
        epsilon = 0.5
        
        # Calculate odds ratio: (a/b)/(c/d) = (a*d)/(b*c)
        or_value = ((a + epsilon) * (d + epsilon)) / ((b + epsilon) * (c + epsilon))
        
        # Calculate 95% CI
        log_or = np.log(or_value)
        se_log_or = np.sqrt(1/(a + epsilon) + 1/(b + epsilon) + 1/(c + epsilon) + 1/(d + epsilon))
        ci95low = np.exp(log_or - 1.96 * se_log_or)
        ci95high = np.exp(log_or + 1.96 * se_log_or)
        odds_ratios.append({"decile": i + 1,
            "x": float(decile_breakpoints[i]),
            "or": float(or_value),
            "ci95low": float(ci95low),
            "ci95high": float(ci95high),
            "caseCount": int(a),
            "ctrlCount": int(b)
        })
        
        confidence_intervals.append({
            "decile": i + 1,
            "x": float(decile_breakpoints[i]),
            "y0": float(ci95low),
            "y1": float(ci95high)
        })
    
    return {
        "oddsRatios": odds_ratios, 
        "confidenceIntervals": confidence_intervals, 
        "decileBreakpoints": [float(bp) for bp in decile_breakpoints]
    }

def calculate_OR_by_decile_vs_cumulative(data, num_deciles=10):
    """Calculate odds ratio by decile compared to all lower deciles combined."""
    # Combine all values to determine decile breakpoints
    all_values = data[0]["values"] + data[1]["values"]
    all_values.sort()
    
    # Calculate decile breakpoints
    decile_breakpoints = [np.quantile(all_values, i / num_deciles) for i in range(num_deciles + 1)]
    
    # Create containers for counts in each decile
    cases_by_decile = [0] * num_deciles
    ctrls_by_decile = [0] * num_deciles
    
    # Assign values to appropriate deciles
    for value in data[0]["values"]:
        decile_index = next((i for i in range(1, len(decile_breakpoints)) 
                            if value < decile_breakpoints[i]), len(decile_breakpoints) - 1) - 1
        cases_by_decile[decile_index] += 1
    
    for value in data[1]["values"]:
        decile_index = next((i for i in range(1, len(decile_breakpoints)) 
                            if value < decile_breakpoints[i]), len(decile_breakpoints) - 1) - 1
        ctrls_by_decile[decile_index] += 1
    
    # Calculate odds ratios for each decile compared to all lower deciles combined
    odds_ratios = []
    confidence_intervals = []
    
    # First decile has no lower deciles, so set to 1.0 (neutral)
    odds_ratios.append({
        "decile": 1,
        "x": float(decile_breakpoints[0]),
        "or": 1.0,
        "ci95low": 1.0,
        "ci95high": 1.0,
        "caseCount": int(cases_by_decile[0]),
        "ctrlCount": int(ctrls_by_decile[0])
    })
    
    confidence_intervals.append({
        "decile": 1,
        "x": float(decile_breakpoints[0]),
        "y0": 1.0,
        "y1": 1.0
    })
    
    # For deciles 2 and above, compare to all lower deciles combined
    for i in range(1, num_deciles):
        # Values for the current decile
        a = cases_by_decile[i]
        b = ctrls_by_decile[i]
        
        # Sum of values for all lower deciles
        c = sum(cases_by_decile[:i])
        d = sum(ctrls_by_decile[:i])
        
        # Add small constant to avoid division by zero
        epsilon = 0.5
        
        # Calculate odds ratio: (a/b)/(c/d) = (a*d)/(b*c)
        or_value = ((a + epsilon) * (d + epsilon)) / ((b + epsilon) * (c + epsilon))
        
        # Calculate 95% CI
        log_or = np.log(or_value)
        se_log_or = np.sqrt(1/(a + epsilon) + 1/(b + epsilon) + 1/(c + epsilon) + 1/(d + epsilon))
        ci95low = np.exp(log_or - 1.96 * se_log_or)
        ci95high = np.exp(log_or + 1.96 * se_log_or)
        
        odds_ratios.append({
            "decile": i + 1,
            "x": float(decile_breakpoints[i]),
            "or": float(or_value),
            "ci95low": float(ci95low),
            "ci95high": float(ci95high),
            "caseCount": int(a),
            "ctrlCount": int(b),
            "lowerCaseCount": int(c),
            "lowerCtrlCount": int(d)
        })
        
        confidence_intervals.append({
            "decile": i + 1,
            "x": float(decile_breakpoints[i]),
            "y0": float(ci95low),
            "y1": float(ci95high)
        })
    
    return {
        "oddsRatios": odds_ratios, 
        "confidenceIntervals": confidence_intervals, 
        "decileBreakpoints": [float(bp) for bp in decile_breakpoints]
    }

@app.post("/api/generate_interactive_plot")
def interactive_filter_router(request: InteractiveRequest):
    if request.plot_type == "umap":
        output_url = add_interactive_filter_umap(html_file_path=request.plot_url)
    elif request.plot_type == "pca":
        output_url = add_interactive_filter_generic(html_file_path=request.plot_url, plot_type='pca')
    elif request.plot_type == "tsne":
        output_url = add_interactive_filter_generic(html_file_path=request.plot_url, plot_type='tsne')
    elif request.plot_type == "svd":
        output_url = add_interactive_filter_generic(html_file_path=request.plot_url, plot_type='svd')
    else:
        raise HTTPException(status_code=501, detail=f"Interactive plot generation for {request.plot_type} not available at this time.")
    return PlotResponse(plot_url=output_url, table_data=[{}])
    
def add_interactive_filter_umap(html_file_path, output_file_path=None):
    """
    Add interactive filtering capability to a saved Plotly HTML file,
    properly extracting IDs from hover text values
    """
    # Create output path if not provided
    if output_file_path is None:
        file_name, file_ext = os.path.splitext(html_file_path)
        output_file_path = f"{file_name}_interactive{file_ext}"
        output_file_path = output_file_path[1:]
    
    # Read the original HTML file
    with open(html_file_path[1:], 'r', encoding='utf-8') as file:
        html_content = file.read()
    
    # Parse HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Add CSS for the filter UI
    style_tag = soup.new_tag('style')
    style_tag.string = """
    .filter-controls {
        padding: 15px;
        margin: 10px 0;
        border: 1px solid #ddd;
        border-radius: 5px;
        background-color: #f9f9f9;
        font-family: Arial, sans-serif;
    }
    .filter-row {
        display: flex;
        gap: 10px;
        margin-bottom: 10px;
        align-items: center;
    }
    .filter-input {
        flex-grow: 1;
        padding: 8px;
        border: 1px solid #ccc;
        border-radius: 4px;
    }
    .filter-button {
        padding: 8px 15px;
        background-color: #4CAF50;
        color: white;
        border: none;
        border-radius: 4px;
        cursor: pointer;
    }
    .filter-button:hover {
        background-color: #45a049;
    }
    .reset-button {
        padding: 8px 15px;
        background-color: #f44336;
        color: white;
        border: none;
        border-radius: 4px;
        cursor: pointer;
    }
    .reset-button:hover {
        background-color: #d32f2f;
    }
    #filter-status {
        margin-top: 10px;
        padding: 5px;
        color: #666;
    }
    """
    soup.head.append(style_tag)
    
    # Create filter control elements
    filter_div = soup.new_tag('div')
    filter_div['class'] = 'filter-controls'
    filter_div.append(soup.new_tag('h3'))
    filter_div.h3.string = 'Filter Points by ID'
    
    # File upload row
    file_row = soup.new_tag('div')
    file_row['class'] = 'filter-row'
    
    file_label = soup.new_tag('label')
    file_label['for'] = 'id-file-input'
    file_label.string = 'Upload ID file:'
    file_row.append(file_label)
    
    file_input = soup.new_tag('input')
    file_input['type'] = 'file'
    file_input['id'] = 'id-file-input'
    file_input['class'] = 'filter-input'
    file_input['accept'] = '.txt,.csv'
    file_row.append(file_input)
    
    apply_button = soup.new_tag('button')
    apply_button['id'] = 'apply-filter'
    apply_button['class'] = 'filter-button'
    apply_button.string = 'Apply Filter'
    file_row.append(apply_button)
    
    reset_button = soup.new_tag('button')
    reset_button['id'] = 'reset-filter'
    reset_button['class'] = 'reset-button'
    reset_button.string = 'Reset'
    file_row.append(reset_button)
    
    filter_div.append(file_row)
    
    # Manual input row
    manual_row = soup.new_tag('div')
    manual_row['class'] = 'filter-row'
    
    manual_label = soup.new_tag('label')
    manual_label['for'] = 'manual-ids'
    manual_label.string = 'Or enter IDs manually:'
    manual_row.append(manual_label)
    
    manual_input = soup.new_tag('input')
    manual_input['type'] = 'text'
    manual_input['id'] = 'manual-ids'
    manual_input['class'] = 'filter-input'
    manual_input['placeholder'] = 'Comma-separated IDs'
    manual_row.append(manual_input)
    
    manual_button = soup.new_tag('button')
    manual_button['id'] = 'apply-manual-filter'
    manual_button['class'] = 'filter-button'
    manual_button.string = 'Apply'
    manual_row.append(manual_button)
    
    filter_div.append(manual_row)
    
    # Status display
    status_div = soup.new_tag('div')
    status_div['id'] = 'filter-status'
    filter_div.append(status_div)
    
    # Find the plotly div and insert our filter controls before it
    plotly_div = soup.select_one('div.plotly-graph-div')
    if plotly_div:
        plotly_div.insert_before(filter_div)
    
    # Add the JavaScript for filtering functionality
    script_tag = soup.new_tag('script')
    script_tag.string = """
// JavaScript for interactive filtering with hover text ID extraction
document.addEventListener('DOMContentLoaded', function() {
    console.log('Hover text ID filter script loaded');
    
    // Store original trace data for reset functionality
    let originalTraceData = [];
    let plotDiv = document.querySelector('.plotly-graph-div');
    
    if (!plotDiv) {
        console.error('Could not find Plotly graph element');
        return;
    }
    
    console.log('Found plot div:', plotDiv.id);
    
    // Wait for Plotly to be fully initialized
    const checkPlotlyInterval = setInterval(() => {
        if (window.Plotly && plotDiv.data) {
            clearInterval(checkPlotlyInterval);
            console.log('Plotly initialized with data');
            
            // Store only the necessary data from each trace
            try {
                plotDiv.data.forEach(trace => {
                    // Create a safe copy without circular references
                    let safeCopy = {
                        x: trace.x ? trace.x.slice() : [],
                        y: trace.y ? trace.y.slice() : [],
                        mode: trace.mode,
                        type: trace.type,
                        name: trace.name,
                        text: trace.text ? (Array.isArray(trace.text) ? trace.text.slice() : trace.text) : null,
                        ids: trace.ids ? trace.ids.slice() : null,
                        customdata: trace.customdata ? trace.customdata.slice() : null,
                        hovertext: trace.hovertext ? (Array.isArray(trace.hovertext) ? trace.hovertext.slice() : trace.hovertext) : null,
                        hovertemplate: trace.hovertemplate,
                        marker: trace.marker ? {
                            size: trace.marker.size,
                            color: Array.isArray(trace.marker.color) ? trace.marker.color.slice() : trace.marker.color,
                            opacity: Array.isArray(trace.marker.opacity) ? trace.marker.opacity.slice() : trace.marker.opacity,
                            symbol: trace.marker.symbol,
                            line: trace.marker.line ? {
                                width: trace.marker.line.width,
                                color: trace.marker.line.color
                            } : null
                        } : null
                    };
                    originalTraceData.push(safeCopy);
                });
                console.log('Original trace data stored safely');
                
                // Analyze first few hover texts to detect format (for console debugging)
                analyzeHoverTextFormat();
            } catch (error) {
                console.error('Error storing original data:', error);
            }
            
            // Setup event listeners
            document.getElementById('apply-filter').addEventListener('click', function() {
                const fileInput = document.getElementById('id-file-input');
                if (fileInput.files.length > 0) {
                    processFile(fileInput.files[0]);
                } else {
                    updateStatus('Please select a file to upload', 'error');
                }
            });
            
            document.getElementById('apply-manual-filter').addEventListener('click', function() {
                const manualInput = document.getElementById('manual-ids').value.trim();
                if (manualInput) {
                    const ids = manualInput.split(',').map(id => id.trim()).filter(id => id);
                    applyFilter(ids);
                } else {
                    updateStatus('Please enter IDs to filter', 'error');
                }
            });
            
            document.getElementById('reset-filter').addEventListener('click', resetFilter);
            
            updateStatus('Filter controls ready. Upload a file with sample IDs or enter IDs manually.', 'info');
        }
    }, 200);
    
    // Analyze hover text format (for debugging in console)
    function analyzeHoverTextFormat() {
        if (!plotDiv || !plotDiv.data) {
            console.error('Plot data not available');
            return;
        }
        
        console.log('Analyzing hover text format...');
        
        plotDiv.data.forEach((trace, i) => {
            if (trace.type === 'scatter' || trace.type === 'scattergl') {
                if (!trace.text || trace.text.length === 0) {
                    console.log('No hover text found in trace ' + i);
                    return;
                }
                
                // Get first few hover texts to analyze
                const samples = Array.isArray(trace.text) ? trace.text.slice(0, 3) : [trace.text];
                
                console.log(`Sample hover texts from trace ${i}:`);
                for (let j = 0; j < samples.length; j++) {
                    const hoverText = samples[j];
                    console.log(`  Sample ${j + 1}: "${hoverText}"`);
                    
                    // Check for "Sample: XXX" pattern
                    const sampleMatch = hoverText.match(/Sample:\s*([^<]+)/);
                    if (sampleMatch && sampleMatch[1]) {
                        console.log(`    → Extracted Sample ID: "${sampleMatch[1].trim()}"`);
                    }
                    
                    // Check for "PGS ID: XXX" pattern
                    const pgsMatch = hoverText.match(/PGS ID:\s*([^<]+)/);
                    if (pgsMatch && pgsMatch[1]) {
                        console.log(`    → Extracted PGS ID: "${pgsMatch[1].trim()}"`);
                    }
                }
            }
        });
    }
    
    function extractIdFromHoverText(hoverText) {
        // If empty or invalid, return null
        if (!hoverText || typeof hoverText !== 'string') {
            return null;
        }
        
        // Try to extract Sample ID
        const sampleMatch = hoverText.match(/Sample:\s*([^<]+)/);
        if (sampleMatch && sampleMatch[1]) {
            return sampleMatch[1].trim();
        }
        
        // Try to extract PGS ID
        const pgsMatch = hoverText.match(/PGS ID:\s*([^<]+)/);
        if (pgsMatch && pgsMatch[1]) {
            return pgsMatch[1].trim();
        }
        
        // If no pattern matches, return null
        return null;
    }
    
    function processFile(file) {
        console.log('Processing file:', file.name);
        updateStatus('Reading file...', 'info');
        
        const reader = new FileReader();
        reader.onload = function(e) {
            console.log('File loaded');
            const content = e.target.result;
            let ids = [];
            
            // Simple parsing based on file extension
            if (file.name.endsWith('.csv')) {
                // Assume CSV has one ID per line or is comma-separated
                ids = content.split(/[\\r\\n,]+/).filter(id => id.trim() !== '');
            } else {
                // Assume plain text with one ID per line
                ids = content.split(/[\\r\\n]+/).filter(id => id.trim() !== '');
            }
            
            console.log(`Extracted ${ids.length} IDs from file`);
            console.log('Sample IDs from file:', ids.slice(0, 5));
            
            applyFilter(ids);
        };
        
        reader.onerror = function() {
            console.error('Error reading file');
            updateStatus('Error reading file', 'error');
        };
        
        reader.readAsText(file);
    }
    
    function applyFilter(idsToHighlight) {
        if (!plotDiv || !plotDiv.data) {
            console.error('Plot data not available');
            updateStatus('Error: Plot data not accessible', 'error');
            return;
        }
        
        console.log(`Applying filter with ${idsToHighlight.length} IDs`);
        
        // Create a set for faster lookups
        const idSet = new Set(idsToHighlight.map(id => id.trim()));
        
        // Create modified traces
        let newData = [];
        let totalMatches = 0;
        
        plotDiv.data.forEach((trace, i) => {
            // Create a new trace based on the original
            let newTrace = {};
            Object.assign(newTrace, trace);
            
            if (newTrace.type === 'scatter' || newTrace.type === 'scattergl') {
                console.log(`Processing trace ${i}, with ${newTrace.x.length} points`);
                
                // Create new marker properties
                let newMarker = {};
                if (newTrace.marker) {
                    Object.assign(newMarker, newTrace.marker);
                } else {
                    newMarker = { size: 6, color: '#1f77b4', opacity: 1 };
                }
                
                // Extract IDs from hover text
                let matchCount = 0;
                
                if (newTrace.text && newTrace.text.length > 0) {
                    // Create color and opacity arrays
                    const colors = [];
                    const opacities = [];
                    
                    // Determine original colors and create new colors
                    const originalColors = Array.isArray(newMarker.color) ? 
                        newMarker.color : 
                        Array(newTrace.x.length).fill(newMarker.color || '#1f77b4');
                    
                    const originalOpacities = Array.isArray(newMarker.opacity) ? 
                        newMarker.opacity : 
                        Array(newTrace.x.length).fill(newMarker.opacity || 1);
                    
                    // Process each point's hover text
                    for (let j = 0; j < newTrace.x.length; j++) {
                        const hoverText = Array.isArray(newTrace.text) ? newTrace.text[j] : newTrace.text;
                        const extractedId = extractIdFromHoverText(hoverText);
                        
                        if (extractedId && idSet.has(extractedId)) {
                            // Highlighted point - keep original color and opacity
                            colors.push(originalColors[j]);
                            opacities.push(originalOpacities[j]);
                            matchCount++;
                        } else {
                            // Non-highlighted point - gray color and reduced opacity
                            colors.push('#cccccc');
                            opacities.push(0.3);
                        }
                    }
                    
                    // Update marker properties
                    newMarker.color = colors;
                    newMarker.opacity = opacities;
                    newTrace.marker = newMarker;
                    
                    console.log(`Updated colors for ${matchCount} highlighted points out of ${newTrace.x.length} total points`);
                    totalMatches += matchCount;
                } else {
                    console.log('No text property found for ID extraction in trace ' + i);
                }
            }
            
            newData.push(newTrace);
        });
        
        // Update the plot with new traces
        try {
            Plotly.react(plotDiv, newData, plotDiv.layout);
            updateStatus(`Filter applied: ${totalMatches} points highlighted out of ${idsToHighlight.length} IDs`, 'success');
        } catch (error) {
            console.error('Error updating plot:', error);
            updateStatus('Error updating plot. Check browser console for details.', 'error');
        }
    }
    
    function resetFilter() {
        console.log('Resetting filter');
        
        if (originalTraceData.length > 0) {
            // Restore original data
            try {
                Plotly.react(plotDiv, originalTraceData, plotDiv.layout);
                updateStatus('Filter reset - showing all points with original colors', 'info');
            } catch (error) {
                console.error('Error resetting plot:', error);
                updateStatus('Error resetting plot. Check browser console for details.', 'error');
            }
        } else {
            updateStatus('Error: Original data not available', 'error');
        }
    }
    
    function updateStatus(message, type) {
        const statusElement = document.getElementById('filter-status');
        if (statusElement) {
            statusElement.textContent = message;
            statusElement.style.color = type === 'error' ? '#f44336' : 
                                       type === 'success' ? '#4CAF50' : '#666';
        }
        console.log(`Status: ${message} (${type})`);
    }
});
    """
    soup.body.append(script_tag)
    
    # Write the modified HTML to the output file
    with open(output_file_path, 'w', encoding='utf-8') as file:
        file.write(str(soup))
    
    print(f"Interactive filter added successfully!")
    print(f"Modified file saved to: {output_file_path}")
    return output_file_path

def add_interactive_filter_pca(html_file_path, output_file_path=None):
    """
    Add interactive filtering capability to a PCA plot HTML file,
    extracting IDs from hover text for either sample or score points
    """
    return add_interactive_filter_generic(html_file_path, output_file_path, 'pca')

def add_interactive_filter_generic(html_file_path, output_file_path=None, plot_type='generic'):
    """
    Generalized function to add interactive filtering to various plot types
    """
    import os
    from bs4 import BeautifulSoup
    
    # Create output path if not provided
    if output_file_path is None:
        file_name, file_ext = os.path.splitext(html_file_path)
        output_file_path = f"{file_name}_interactive{file_ext}"
        output_file_path = output_file_path[1:]
    
    # Read the original HTML file
    with open(html_file_path[1:], 'r', encoding='utf-8') as file:
        html_content = file.read()
    
    # Parse HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Add CSS for the filter UI
    style_tag = soup.new_tag('style')
    style_tag.string = """
    .filter-controls {
        padding: 15px;
        margin: 10px 0;
        border: 1px solid #ddd;
        border-radius: 5px;
        background-color: #f9f9f9;
        font-family: Arial, sans-serif;
    }
    .filter-row {
        display: flex;
        gap: 10px;
        margin-bottom: 10px;
        align-items: center;
    }
    .filter-input {
        flex-grow: 1;
        padding: 8px;
        border: 1px solid #ccc;
        border-radius: 4px;
    }
    .filter-button {
        padding: 8px 15px;
        background-color: #4CAF50;
        color: white;
        border: none;
        border-radius: 4px;
        cursor: pointer;
    }
    .filter-button:hover {
        background-color: #45a049;
    }
    .reset-button {
        padding: 8px 15px;
        background-color: #f44336;
        color: white;
        border: none;
        border-radius: 4px;
        cursor: pointer;
    }
    .reset-button:hover {
        background-color: #d32f2f;
    }
    #filter-status {
        margin-top: 10px;
        padding: 5px;
        color: #666;
    }
    #debug-panel {
        margin-top: 15px;
        padding: 10px;
        border: 1px dashed #ccc;
        background-color: #f5f5f5;
        font-family: monospace;
        font-size: 12px;
        max-height: 200px;
        overflow-y: auto;
        white-space: pre-wrap;
    }
    .debug-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .debug-toggle {
        cursor: pointer;
        color: blue;
        text-decoration: underline;
    }
    """
    soup.head.append(style_tag)
    
    # Create filter control elements
    filter_div = soup.new_tag('div')
    filter_div['class'] = 'filter-controls'
    filter_div.append(soup.new_tag('h3'))
    
    # Customize header based on plot type
    if plot_type == 'pca':
        filter_div.h3.string = 'Filter PCA Points by ID'
    elif plot_type == 'umap':
        filter_div.h3.string = 'Filter UMAP Points by ID'
    else:
        filter_div.h3.string = 'Filter Points by ID'
    
    # File upload row
    file_row = soup.new_tag('div')
    file_row['class'] = 'filter-row'
    
    file_label = soup.new_tag('label')
    file_label['for'] = 'id-file-input'
    file_label.string = 'Upload ID file:'
    file_row.append(file_label)
    
    file_input = soup.new_tag('input')
    file_input['type'] = 'file'
    file_input['id'] = 'id-file-input'
    file_input['class'] = 'filter-input'
    file_input['accept'] = '.txt,.csv'
    file_row.append(file_input)
    
    apply_button = soup.new_tag('button')
    apply_button['id'] = 'apply-filter'
    apply_button['class'] = 'filter-button'
    apply_button.string = 'Apply Filter'
    file_row.append(apply_button)
    
    reset_button = soup.new_tag('button')
    reset_button['id'] = 'reset-filter'
    reset_button['class'] = 'reset-button'
    reset_button.string = 'Reset'
    file_row.append(reset_button)
    
    filter_div.append(file_row)
    
    # Manual input row
    manual_row = soup.new_tag('div')
    manual_row['class'] = 'filter-row'
    
    manual_label = soup.new_tag('label')
    manual_label['for'] = 'manual-ids'
    manual_label.string = 'Or enter IDs manually:'
    manual_row.append(manual_label)
    
    manual_input = soup.new_tag('input')
    manual_input['type'] = 'text'
    manual_input['id'] = 'manual-ids'
    manual_input['class'] = 'filter-input'
    manual_input['placeholder'] = 'Comma-separated IDs'
    manual_row.append(manual_input)
    
    manual_button = soup.new_tag('button')
    manual_button['id'] = 'apply-manual-filter'
    manual_button['class'] = 'filter-button'
    manual_button.string = 'Apply'
    manual_row.append(manual_button)
    
    filter_div.append(manual_row)
    
    # Status display
    status_div = soup.new_tag('div')
    status_div['id'] = 'filter-status'
    filter_div.append(status_div)
    
    # Debug panel
    debug_header = soup.new_tag('div')
    debug_header['class'] = 'debug-header'
    
    debug_title = soup.new_tag('span')
    debug_title.string = 'Debug Information'
    debug_header.append(debug_title)
    
    debug_toggle = soup.new_tag('span')
    debug_toggle['class'] = 'debug-toggle'
    debug_toggle['id'] = 'toggle-debug'
    debug_toggle.string = 'Show/Hide'
    debug_header.append(debug_toggle)
    
    filter_div.append(debug_header)
    
    debug_div = soup.new_tag('div')
    debug_div['id'] = 'debug-panel'
    debug_div['style'] = 'display: none;'  # Initially hidden
    filter_div.append(debug_div)
    
    # Find the plotly div and insert our filter controls before it
    plotly_div = soup.select_one('div.plotly-graph-div')
    if plotly_div:
        plotly_div.insert_before(filter_div)
    
    # Add the JavaScript for filtering functionality
    script_tag = soup.new_tag('script')
    script_tag.string = f"""
// JavaScript for interactive filtering with hover text ID extraction - Fixed for Plotly 3.0
document.addEventListener('DOMContentLoaded', function() {{
    console.log('PCA Filter script loaded (Plotly 3.0 compatible)');
    
    // DEBUG: Setup debug panel
    const debugPanel = document.getElementById('debug-panel');
    const toggleDebug = document.getElementById('toggle-debug');
    toggleDebug.addEventListener('click', function() {{
        if (debugPanel.style.display === 'none') {{
            debugPanel.style.display = 'block';
        }} else {{
            debugPanel.style.display = 'none';
        }}
    }});
    
    function logDebug(message, data = null) {{
        // Log to console
        if (data) {{
            console.log(message, data);
        }} else {{
            console.log(message);
        }}
        
        // Log to debug panel
        const timestamp = new Date().toLocaleTimeString();
        let formattedMessage = `[${{timestamp}}] ${{message}}`;
        
        if (data) {{
            // Convert data to string representation
            let dataStr;
            try {{
                if (Array.isArray(data)) {{
                    if (data.length > 20) {{
                        dataStr = JSON.stringify(data.slice(0, 20)) + `... (${{data.length - 20}} more items)`;
                    }} else {{
                        dataStr = JSON.stringify(data);
                    }}
                }} else if (typeof data === 'object' && data !== null) {{
                    dataStr = JSON.stringify(data);
                }} else {{
                    dataStr = String(data);
                }}
            }} catch (e) {{
                dataStr = "[Object could not be stringified]";
            }}
            
            formattedMessage += `\\n${{dataStr}}`;
        }}
        
        // Add to debug panel, prepending to show newest first
        const debugLine = document.createElement('div');
        debugLine.textContent = formattedMessage;
        debugPanel.prepend(debugLine);
        
        // Limit debug panel size
        if (debugPanel.children.length > 100) {{
            debugPanel.removeChild(debugPanel.lastChild);
        }}
    }}
    
    // Store original data for reset functionality
    let originalData = null;
    let plotDiv = document.querySelector('.plotly-graph-div');
    
    if (!plotDiv) {{
        logDebug('ERROR: Could not find Plotly graph element');
        return;
    }}
    
    logDebug('Found plot div:', plotDiv.id);
    
    // Wait for Plotly to be fully initialized
    const checkPlotlyInterval = setInterval(() => {{
        if (window.Plotly && window.Plotly.newPlot) {{
            clearInterval(checkPlotlyInterval);
            logDebug('Plotly initialized');
            
            // Store the original data by capturing the Plotly.newPlot call
            const originalNewPlot = window.Plotly.newPlot;
            window.Plotly.newPlot = function() {{
                // Save the original arguments
                const args = Array.from(arguments);
                originalData = JSON.parse(JSON.stringify(args[1])); // Deep clone the data
                logDebug(`Captured plot data with ${{originalData.length}} traces`);
                
                // Call the original function
                return originalNewPlot.apply(this, args);
            }};
            
            // Force re-rendering to capture the data
            setTimeout(() => {{
                if (!originalData) {{
                    // Try to get data directly from the DOM
                    try {{
                        const scriptContent = document.querySelector('script:not([src])').textContent;
                        const dataMatch = scriptContent.match(/Plotly\.newPlot\([^,]+,\s*(\[[^\]]+\])/);
                        if (dataMatch && dataMatch[1]) {{
                            originalData = JSON.parse(dataMatch[1]);
                            logDebug(`Extracted plot data from script: ${{originalData.length}} traces`);
                        }}
                    }} catch (e) {{
                        logDebug('ERROR: Failed to extract data from script', e.message);
                    }}
                }}
                
                // Setup event listeners
                document.getElementById('apply-filter').addEventListener('click', function() {{
                    const fileInput = document.getElementById('id-file-input');
                    if (fileInput.files.length > 0) {{
                        processFile(fileInput.files[0]);
                    }} else {{
                        updateStatus('Please select a file to upload', 'error');
                    }}
                }});
                
                document.getElementById('apply-manual-filter').addEventListener('click', function() {{
                    const manualInput = document.getElementById('manual-ids').value.trim();
                    if (manualInput) {{
                        const ids = manualInput.split(',').map(id => id.trim()).filter(id => id);
                        logDebug('Applying manual filter with IDs:', ids);
                        applyFilter(ids);
                    }} else {{
                        updateStatus('Please enter IDs to filter', 'error');
                    }}
                }});
                
                document.getElementById('reset-filter').addEventListener('click', resetFilter);
                
                // Analyze the plot structure
                analyzeHoverTextFormat();
                
                updateStatus('Filter controls ready. Upload a file with IDs or enter IDs manually.', 'info');
            }}, 500);
        }}
    }}, 200);
    
    // Analyze hover text format
    function analyzeHoverTextFormat() {{
        logDebug('Analyzing plot structure...');
        
        if (!originalData || originalData.length === 0) {{
            logDebug('ERROR: Plot data not available for analysis');
            return;
        }}
        
        // Log information about each trace
        originalData.forEach((trace, i) => {{
            logDebug(`Trace ${{i}} information:`);
            
            // Log trace type and mode
            logDebug(`  Type: ${{trace.type || 'unknown'}}, Mode: ${{trace.mode || 'unknown'}}, Name: ${{trace.name || 'unnamed'}}`);
            
            // Check for hover text
            if (trace.hoverinfo) {{
                logDebug(`  Hoverinfo: ${{trace.hoverinfo}}`);
            }}
            
            // Check for hover text content
            if (trace.hovertext) {{
                logDebug(`  Has hovertext property: ${{Array.isArray(trace.hovertext) ? trace.hovertext.length + ' items' : 'single value'}}`);
                
                // Show sample text
                if (Array.isArray(trace.hovertext) && trace.hovertext.length > 0) {{
                    const sampleText = trace.hovertext[0].substring(0, 100) + (trace.hovertext[0].length > 100 ? '...' : '');
                    logDebug(`  Sample hovertext: "${{sampleText}}"`);
                    
                    // Test ID extraction
                    const extractedId = extractIdFromHoverText(trace.hovertext[0]);
                    if (extractedId) {{
                        logDebug(`  Extracted ID: "${{extractedId}}"`);
                    }} else {{
                        logDebug(`  Failed to extract ID from hover text`);
                    }}
                }}
            }}
            
            // Check for X and Y data structure
            if (trace.x) {{
                if (typeof trace.x === 'object' && trace.x.dtype) {{
                    logDebug(`  X data format: binary (${{trace.x.dtype}})`);
                }} else if (Array.isArray(trace.x)) {{
                    logDebug(`  X data format: array (${{trace.x.length}} points)`);
                }}
            }}
            
            if (trace.y) {{
                if (typeof trace.y === 'object' && trace.y.dtype) {{
                    logDebug(`  Y data format: binary (${{trace.y.dtype}})`);
                }} else if (Array.isArray(trace.y)) {{
                    logDebug(`  Y data format: array (${{trace.y.length}} points)`);
                }}
            }}
        }});
    }}
    
    function extractIdFromHoverText(hoverText) {{
        // If empty or invalid, return null
        if (!hoverText || typeof hoverText !== 'string') {{
            return null;
        }}
        
        // For PCA plots, the most specific pattern first
        {f'if ("{plot_type}" === "pca") {{' if plot_type else 'if (false) {'}
            // PGS ID pattern specific to this plot
            const pgsMatch = hoverText.match(/PGS ID: ([^<\\r\\n]+)/i);
            if (pgsMatch && pgsMatch[1]) {{
                return pgsMatch[1].trim();
            }}
            
            // Try to extract Sample ID pattern
            const sampleMatch = hoverText.match(/Sample(?:[ :]|\\s*ID\\s*:)\\s*([^<,\\r\\n]+)/i);
            if (sampleMatch && sampleMatch[1]) {{
                return sampleMatch[1].trim();
            }}
            
            // Look for PC component labels with ID in parentheses
            const pcaLabelMatch = hoverText.match(/PC\\d+\\s*\\(([^)]+)\\)/i);
            if (pcaLabelMatch && pcaLabelMatch[1]) {{
                return pcaLabelMatch[1].trim();
            }}
        }}
        
        // More generic patterns
        
        // Try to extract any "ID: value" pattern
        const idLabelMatch = hoverText.match(/\\b(\\w+)\\s*ID\\s*:?\\s*([^<,\\r\\n]+)/i);
        if (idLabelMatch && idLabelMatch[2]) {{
            return idLabelMatch[2].trim();
        }}
        
        // Look for standalone ID-like patterns (e.g. PGS000123)
        const standaloneIdMatch = hoverText.match(/\\b([A-Z]{2,3}\\d{5,}|[A-Z]{3}_\\d+)\\b/);
        if (standaloneIdMatch && standaloneIdMatch[1]) {{
            return standaloneIdMatch[1];
        }}
        
        // Last resort: if the hover text is simple (no special formatting)
        // and looks like an ID itself, use the whole text
        if (!/[<>:]/.test(hoverText) && hoverText.length < 30) {{
            return hoverText.trim();
        }}
        
        // If no pattern matches, return null
        return null;
    }}
    
    function processFile(file) {{
        logDebug('Processing file:', file.name);
        updateStatus('Reading file...', 'info');
        
        const reader = new FileReader();
        reader.onload = function(e) {{
            logDebug('File loaded successfully');
            const content = e.target.result;
            let ids = [];
            
            // Simple parsing based on file extension
            if (file.name.endsWith('.csv')) {{
                // Assume CSV has one ID per line or is comma-separated
                ids = content.split(/[\\r\\n,]+/).filter(id => id.trim() !== '');
            }} else {{
                // Assume plain text with one ID per line
                ids = content.split(/[\\r\\n]+/).filter(id => id.trim() !== '');
            }}
            
            logDebug(`Extracted ${{ids.length}} IDs from file`);
            if (ids.length > 0) {{
                logDebug('Sample IDs from file:', ids.slice(0, 5));
                applyFilter(ids);
            }} else {{
                updateStatus('No valid IDs found in file', 'error');
            }}
        }};
        
        reader.onerror = function() {{
            logDebug('ERROR reading file');
            updateStatus('Error reading file', 'error');
        }};
        
        reader.readAsText(file);
    }}
    
    function applyFilter(idsToHighlight) {{
        if (!originalData || originalData.length === 0) {{
            logDebug('ERROR: Original plot data not available');
            updateStatus('Error: Plot data not accessible', 'error');
            return;
        }}
        
        logDebug(`Applying filter with ${{idsToHighlight.length}} IDs`);
        if (idsToHighlight.length > 0) {{
            logDebug('First few IDs being filtered:', idsToHighlight.slice(0, 5));
        }}
        
        // Create a set for faster lookups
        const idSet = new Set(idsToHighlight.map(id => id.trim()));
        
        // Create modified traces
        let newData = [];
        let totalPoints = 0;
        let totalMatches = 0;
        let matchedIds = new Set(); // Track which IDs we actually matched
        
        originalData.forEach((trace, i) => {{
            // Skip the reference line trace if it exists
            if (trace.hoverinfo === 'skip' || trace.name === 'Scale Reference') {{
                newData.push(JSON.parse(JSON.stringify(trace)));
                return;
            }}
            
            // Create a new trace based on the original
            let newTrace = JSON.parse(JSON.stringify(trace));
            
            // Check if this trace has hover text
            if (newTrace.hovertext) {{
                logDebug(`Processing trace ${{i}} with ${{Array.isArray(newTrace.hovertext) ? newTrace.hovertext.length : 1}} hover texts`);
                
                const hoverTexts = Array.isArray(newTrace.hovertext) ? newTrace.hovertext : [newTrace.hovertext];
                totalPoints += hoverTexts.length;
                
                // Create new marker properties
                if (!newTrace.marker) {{
                    newTrace.marker = {{
                        size: 5,
                        color: 'red',
                        opacity: 0.6
                    }};
                }}
                
                let newMarker = JSON.parse(JSON.stringify(newTrace.marker));
                
                // Create arrays for marker properties
                let colors = [];
                let opacities = [];
                let matchCount = 0;
                
                // Process each hover text
                hoverTexts.forEach((hoverText, j) => {{
                    const extractedId = extractIdFromHoverText(hoverText);
                    
                    if (extractedId && idSet.has(extractedId)) {{
                        // Match found - keep original color and opacity
                        matchCount++;
                        matchedIds.add(extractedId);
                        
                        // Determine original color and opacity
                        let originalColor = Array.isArray(newMarker.color) ? 
                            (newMarker.color[j] || 'red') : newMarker.color || 'red';
                        let originalOpacity = Array.isArray(newMarker.opacity) ?
                            (newMarker.opacity[j] || 1.0) : newMarker.opacity || 0.6;
                        
                        colors.push(originalColor);
                        opacities.push(originalOpacity);
                    }} else {{
                        // No match - gray and low opacity
                        colors.push('#cccccc');
                        opacities.push(0.2);
                    }}
                }});
                
                logDebug(`Trace ${{i}}: Matched ${{matchCount}} out of ${{hoverTexts.length}} points`);
                totalMatches += matchCount;
                
                // Update marker properties
                newMarker.color = colors;
                newMarker.opacity = opacities;
                newTrace.marker = newMarker;
            }} else {{
                logDebug(`Skipping trace ${{i}} (no hover text for ID extraction)`);
            }}
            
            newData.push(newTrace);
        }});
        
        // Update the plot with new traces
        try {{
            logDebug(`Updating plot with modified data (${{newData.length}} traces)`);
            Plotly.react(plotDiv, newData, plotDiv.layout);
            
            const matchPercentage = totalPoints > 0 ? Math.round((totalMatches / totalPoints) * 100) : 0;
            logDebug(`Total matches: ${{totalMatches}} points out of ${{totalPoints}} total points (${{matchPercentage}}%)`);
            logDebug(`Matched ${{matchedIds.size}} unique IDs out of ${{idSet.size}} requested`);
            
            // Show which IDs weren't found
            if (matchedIds.size < idSet.size) {{
                const missingIds = Array.from(idSet).filter(id => !matchedIds.has(id));
                logDebug(`IDs not found in hover text:`, missingIds.slice(0, 10));
                if (missingIds.length > 10) {{
                    logDebug(`(and ${{missingIds.length - 10}} more missing IDs)`);
                }}
            }}
            
            updateStatus(`Filter applied: ${{totalMatches}} points highlighted out of ${{totalPoints}} total points (${{matchPercentage}}%). Matched ${{matchedIds.size}} unique IDs out of ${{idSet.size}} requested.`, 'success');
        }} catch (error) {{
            logDebug('ERROR updating plot:', error.message);
            updateStatus('Error updating plot. Check debug panel for details.', 'error');
        }}
    }}
    
    function resetFilter() {{
        logDebug('Resetting filter');
        
        if (originalData) {{
            // Restore original data
            try {{
                Plotly.react(plotDiv, originalData, plotDiv.layout);
                updateStatus('Filter reset - showing all points with original colors', 'info');
            }} catch (error) {{
                logDebug('ERROR resetting plot:', error.message);
                updateStatus('Error resetting plot. Check debug panel for details.', 'error');
            }}
        }} else {{
            updateStatus('Error: Original data not available', 'error');
        }}
    }}
    
    function updateStatus(message, type) {{
        const statusElement = document.getElementById('filter-status');
        if (statusElement) {{
            statusElement.textContent = message;
            statusElement.style.color = type === 'error' ? '#f44336' : 
                                      type === 'success' ? '#4CAF50' : '#666';
        }}
        logDebug(`Status: ${{message}} (${{type}})`);
    }}
}});
    """
    soup.body.append(script_tag)
    
    # Write the modified HTML to the output file
    with open(output_file_path, 'w', encoding='utf-8') as file:
        file.write(str(soup))
    
    print(f"Interactive filter added successfully for {plot_type} plot!")
    print(f"Modified file saved to: {output_file_path}")
    return output_file_path
    
# TASK MANAGERS 
@app.get("/api/task_status/{task_id}")
async def get_task_status(task_id: str):
    conn = sqlite3.connect(TASK_DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM image_tasks WHERE task_id = ?", (task_id,))
    task = cursor.fetchone()
    conn.close()
    
    if not task:
        return {"error": "Task not found"}
    
    # Convert DB row to dictionary
    columns = ["task_id", "task_type", "name", "status", "created_at", 
               "completed_at", "result_path", "error", "request_data"]
    task_dict = {columns[i]: task[i] for i in range(len(columns))}
    
    return {
        "task_id": task_dict["task_id"],
        "task_type": task_dict["task_type"],
        "name": task_dict["name"],
        "status": task_dict["status"],
        "created_at": task_dict["created_at"],
        "completed_at": task_dict["completed_at"],
        "result_path": task_dict["result_path"] if task_dict["status"] == "completed" else None,
        "error": task_dict["error"] if task_dict["status"] == "failed" else None
    }

@app.get("/api/list_tasks")
async def list_tasks(task_type: Optional[str] = None, limit: int = 20, offset: int = 0):
    conn = sqlite3.connect(TASK_DB_PATH)
    cursor = conn.cursor()
    
    if task_type:
        cursor.execute(
            "SELECT task_id, task_type, name, status, created_at, completed_at FROM image_tasks WHERE task_type = ? ORDER BY created_at DESC LIMIT ? OFFSET ?", 
            (task_type, limit, offset)
        )
    else:
        cursor.execute(
            "SELECT task_id, task_type, name, status, created_at, completed_at FROM image_tasks ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
        )
    
    tasks = cursor.fetchall()
    conn.close()
    
    return [
        {
            "task_id": task[0],
            "task_type": task[1],
            "name": task[2],
            "status": task[3],
            "created_at": task[4],
            "completed_at": task[5]
        }
        for task in tasks
    ]

# Function to update task status in the database
def update_task_status(task_id, status, **kwargs):
    conn = sqlite3.connect(TASK_DB_PATH)
    cursor = conn.cursor()
    
    set_clause = f"status = ?"
    params = [status]
    
    for key, value in kwargs.items():
        set_clause += f", {key} = ?"
        params.append(value)
    
    params.append(task_id)
    
    cursor.execute(f"UPDATE image_tasks SET {set_clause} WHERE task_id = ?", params)
    conn.commit()
    conn.close()

# Utility functions
def get_matrix(
    sample_ids, 
    pgs_ids, 
    score_type,
    output_format="dict",   # Options: "dict", "numpy"
    handle_missing=False,   # Whether to fill NaN values with column means
    upper_threshold=None,   # Cap scores above this value
    lower_threshold=None    # Cap scores below this value
):
    """
    Retrieve scores and construct a matrix using temporary tables for efficiency.
    
    Parameters:
    -----------
    sample_ids : list
        List of sample IDs to include
    pgs_ids : list
        List of PGS IDs to include
    score_type : str
        Type of score to retrieve
    output_format : str, optional
        Format of output, either "dict" or "numpy"
    handle_missing : bool, optional
        Whether to replace missing values with column means (only for numpy output)
    upper_threshold : float, optional
        Maximum value for scores (scores above will be capped)
    lower_threshold : float, optional
        Minimum value for scores (scores below will be capped)
    
    Returns:
    --------
    dict or numpy.ndarray
        Either nested dictionary or numpy matrix of scores
    """
    # Establish connection to the database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        if sample_ids and pgs_ids:
            # Create the temp table with proper placeholders
            sample_placeholders = ','.join(['?'] * len(sample_ids))
            pgs_placeholders = ','.join(['?'] * len(pgs_ids))
            query = f"""
                SELECT SAMPLE_ID, PGS_ID, SCORE
                FROM scores
                WHERE SCORE_TYPE = ?
                AND SAMPLE_ID IN ({sample_placeholders})
                AND PGS_ID IN ({pgs_placeholders})
            """
            params = [score_type] + sample_ids + pgs_ids
        elif sample_ids:
            sample_placeholders = ','.join(['?'] * len(sample_ids))
            query = f"""
                SELECT SAMPLE_ID, PGS_ID, SCORE
                FROM scores
                WHERE SCORE_TYPE = ?
                AND SAMPLE_ID IN ({sample_placeholders})
            """
            params = [score_type] + sample_ids
        elif pgs_ids:
            sample_placeholders = ','.join(['?'] * len(sample_ids))
            query = f"""
                SELECT SAMPLE_ID, PGS_ID, SCORE
                FROM scores
                WHERE SCORE_TYPE = ?
                AND PGS_ID IN ({pgs_placeholders})
            """
            params = [score_type] + pgs_ids
        else:
            query = f"""
                SELECT SAMPLE_ID, PGS_ID, SCORE
                FROM scores
                WHERE SCORE_TYPE = ?
            """
            params = [score_type]

        data_dict = {}
        scores_list = []
        print("Filling table")
        for i, (sample_id, pgs_id, score) in enumerate(cursor.execute(query, params)):
            # Apply thresholds if provided
            if upper_threshold is not None and score > upper_threshold:
                score = upper_threshold
            elif lower_threshold is not None and score < lower_threshold:
                score = lower_threshold
                
            if sample_id not in data_dict:
                data_dict[sample_id] = {}
            data_dict[sample_id][pgs_id] = score
            scores_list.append(score)

            if i % 1000000 == 0:
                print(f"Processed {i} rows.")
        # Return dictionary or convert to numpy matrix
        if output_format == "numpy":
            # Get all unique sample IDs and PGS IDs from the dictionary
            available_samples = list(data_dict.keys())
            
            # Get all unique PGS IDs by combining all dictionaries
            available_pgs = set()
            for sample_scores in data_dict.values():
                available_pgs.update(sample_scores.keys())
            available_pgs = list(available_pgs)
            
            # If specific sample_ids or pgs_ids were requested, filter to those that exist in the data
            if sample_ids:
                final_samples = [s for s in sample_ids if s in available_samples]
            else:
                final_samples = available_samples
            
            if pgs_ids:
                final_pgs = [p for p in pgs_ids if p in available_pgs]
            else:
                final_pgs = available_pgs
            
            # Create the index mappings
            sample_to_index = {sample_id: i for i, sample_id in enumerate(final_samples)}
            pgs_to_index = {pgs_id: j for j, pgs_id in enumerate(final_pgs)}
                
            matrix = np.full((len(final_samples), len(final_pgs)), np.nan)
    
            # Fill the matrix
            for sample_id, pgs_scores in data_dict.items():
                i = sample_to_index.get(sample_id)
                if i is not None:
                    for pgs_id, score in pgs_scores.items():
                        j = pgs_to_index.get(pgs_id)
                        if j is not None:  # Safety check
                            matrix[i, j] = score

            # Handle missing values if requested
            if handle_missing:
                for j in range(matrix.shape[1]):
                    col_values = matrix[:, j]
                    non_nan_values = col_values[~np.isnan(col_values)]
                    if len(non_nan_values) > 0:  # Only calculate mean if there are non-NaN values
                        col_mean = np.mean(non_nan_values)
                        mask = np.isnan(col_values)
                        if mask.any():  # Only fill if there are NaNs
                            matrix[mask, j] = col_mean

            return matrix, final_pgs
        else:
            return data_dict, data_dict.keys()
            
    finally:
        # # Clean up temp table and close connection
        conn.close()
        
def fetch_pgs_metadata(pgs_ids):
    """Fetch metadata for given PGS IDs from the SQLite database."""
    placeholders = ','.join('?' for _ in pgs_ids)
    query = f"""
        SELECT PGS_ID, PGS_Name, Reported_Trait, PGS_Publication_ID
        FROM pgs_metadata
        WHERE PGS_ID IN ({placeholders})
    """
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(query, pgs_ids)
        rows = cursor.fetchall()

    # Convert to dictionary keyed by PGS_ID
    return {
        row[0]: {
            "PGS_Name": row[1],
            "Reported_Trait": row[2],
            "Publication_ID": row[3]
        }
        for row in rows
    }

# Define the background task processor separately
def process_background_task(task_id, request_data, processing_function):
    try:
        # Update status to "processing"
        update_task_status(task_id, "processing")
        
        # Call the actual processing function
        result_path = processing_function(request_data)
        
        # Update task with success status and result path
        update_task_status(
            task_id, 
            "completed",
            result_path=result_path,
            completed_at=datetime.now().isoformat()
        )
        
    except Exception as e:
        # Update task with error status
        update_task_status(
            task_id,
            "failed",
            error=str(e),
            completed_at=datetime.now().isoformat()
        )

async def process_image_request(
    request_data: dict,
    task_type: str,
    task_name: Optional[str],
    processing_function,
    background_tasks: BackgroundTasks
):
    """
    Generic function to handle image generation requests
    
    Args:
        request_data: Dict containing the request parameters
        task_type: Type of task (heatmap, clustering, etc.)
        task_name: Optional user-provided name
        processing_function: The function that will generate the image
        background_tasks: FastAPI BackgroundTasks object
    
    Returns:
        TaskResponse object with task_id and status
    """
    # Generate a unique task ID
    task_id = str(uuid.uuid4())
    created_at = datetime.now().isoformat()
    
    # Store task in database
    conn = sqlite3.connect(TASK_DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        "INSERT INTO image_tasks (task_id, task_type, name, status, created_at, request_data) VALUES (?, ?, ?, ?, ?, ?)",
        (task_id, task_type, task_name, "queued", created_at, json.dumps(request_data))
    )
    
    conn.commit()
    conn.close()
    
    # Add task to background tasks - pass the processing function as an argument
    background_tasks.add_task(process_background_task, task_id, request_data, processing_function)
    
    # Return task ID and initial status to client
    return TaskResponse(
        task_id=task_id,
        task_type=task_type,
        name=task_name,
        status="queued",
        created_at=created_at
    )

# def initialize_db():
#     """Initialize database if it doesn't exist"""
#     if os.path.exists(DB_PATH):
#         return

#     # Create db directory if it doesn't exist
#     os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

#     file_path = "data/samples/pgs_scores_output.tsv.gz"  

#     # Detect if the file is gzipped and read accordingly
#     if file_path.endswith(".gz"):
#         f = gzip.open(file_path, "rt")  
#     else:
#         f = open(file_path, "rt")

#     conn = sqlite3.connect(DB_PATH)
#     cursor = conn.cursor()

#     # Create the pgs_metadata table
#     cursor.execute("DROP TABLE IF EXISTS pgs_metadata")

#     cursor.execute("""
#         CREATE TABLE IF NOT EXISTS pgs_metadata (
#             PGS_ID TEXT PRIMARY KEY,
#             PGS_Name TEXT,
#             Reported_Trait TEXT,
#             Mapped_Trait_Label TEXT,
#             Mapped_Trait_ID TEXT,
#             PGS_Development_Method TEXT,
#             PGS_Development_Details TEXT,
#             Original_Genome_Build TEXT,
#             Number_of_Variants INTEGER,
#             Number_of_Interaction_Terms INTEGER,
#             Type_of_Variant_Weight TEXT,
#             PGS_Publication_ID TEXT,
#             Publication_PMID INTEGER,
#             Publication_DOI TEXT,
#             Score_Matches_Publication BOOLEAN,
#             Ancestry_Distribution_Variant_Associations TEXT,
#             Ancestry_Distribution_Score_Development TEXT,
#             Ancestry_Distribution_PGS_Evaluation TEXT,
#             FTP_Link TEXT,
#             Release_Date TEXT,
#             License_Terms TEXT
#         )
#     """)

#     # Drop old table if it exists
#     cursor.execute("DROP TABLE IF EXISTS scores")

#     # Create table in "long format"
#     cursor.execute("""
#         CREATE TABLE IF NOT EXISTS scores (
#             PGS_ID TEXT REFERENCES pgs_metadata(PGS_ID),
#             SCORE_TYPE TEXT,
#             SAMPLE_ID TEXT,
#             SCORE REAL
#         )
#     """)
#     cursor.execute("CREATE INDEX score_pgs_idx ON scores(PGS_ID)")

#     # Reshape data: Convert wide format (IDs as columns) → long format (one row per (ID, Score))
#     data = []
#     header = []
#     last_pgs=""
#     write=True
#     for line in f:
#         row = line.strip("\n").split("\t")
#         if row[0]=="PGS":
#             header = row
#             continue 
#         pgs = row[0]
#         if pgs != last_pgs:
#             if write:
#                 cursor.executemany("INSERT INTO scores (PGS_ID, SCORE_TYPE, SAMPLE_ID, SCORE) VALUES (?, ?, ?, ?)", data)
#                 # print(f"{last_pgs} written")
#             else:
#                 print(f"{last_pgs} failed")
#             data = []
#             write=True
#             last_pgs=pgs
#         score_type = row[1]
#         for index, score in enumerate(row):  # Iterate over all sample ID columns
#             if index < 2: 
#                 continue 
#             try:
#                 data.append((pgs, score_type, header[index], float(score)))
#             except: 
#                 write=False

#         # Insert Data
#     if data and write:
#         cursor.executemany("INSERT INTO scores (PGS_ID, SCORE_TYPE, SAMPLE_ID, SCORE) VALUES (?, ?, ?, ?)", data)

#     metadata_csv_path = "data/pgs/score_info.csv"

#     # Load the metadata CSV
#     df = pd.read_csv(metadata_csv_path)

#     # Rename columns to match the SQL schema
#     df.columns = [
#         "PGS_ID", "PGS_Name", "Reported_Trait", "Mapped_Trait_Label", "Mapped_Trait_ID",
#         "PGS_Development_Method", "PGS_Development_Details", "Original_Genome_Build",
#         "Number_of_Variants", "Number_of_Interaction_Terms", "Type_of_Variant_Weight",
#         "PGS_Publication_ID", "Publication_PMID", "Publication_DOI", 
#         "Score_Matches_Publication", "Ancestry_Distribution_Variant_Associations", 
#         "Ancestry_Distribution_Score_Development", "Ancestry_Distribution_PGS_Evaluation",
#         "FTP_Link", "Release_Date", "License_Terms"
#     ]

#     # Convert boolean column to actual boolean type
#     df["Score_Matches_Publication"] = df["Score_Matches_Publication"].apply(lambda x: x == "TRUE")

#     # Insert data into the SQLite database
#     df.to_sql("pgs_metadata", conn, if_exists="replace", index=False)

#     conn.commit()
#     conn.close()
#     f.close()

# # Initialize DB when application starts
# initialize_db()

# @app.post("/api/multi_cohort_distribution/{pgs}/{score_type}")
# async def get_multi_cohort_distribution(pgs: str, score_type: str, cohorts: List[CohortRequest]):
#     """Retrieve score distributions for multiple cohorts."""
    
#     conn = sqlite3.connect(DB_PATH)
#     conn.row_factory = sqlite3.Row
#     cursor = conn.cursor()

#     # Retrieve scores for the given PGS and score type
#     cursor.execute(
#         "SELECT SAMPLE_ID, SCORE FROM scores WHERE PGS_ID = ? AND SCORE_TYPE = ?",
#         (pgs, score_type)
#     )
#     rows = cursor.fetchall()
#     conn.close()

#     if not rows:
#         raise HTTPException(
#             status_code=404,
#             detail=f"No data found for PGS '{pgs}' and Score Type '{score_type}'"
#         )

#     # Create a dictionary mapping SAMPLE_ID to SCORE
#     score_dict = {row["SAMPLE_ID"]: row["SCORE"] for row in rows}

#     cohort_data = []
#     for cohort in cohorts:
#         cohort_scores = [
#             score_dict[sample_id] for sample_id in cohort.sample_ids
#             if sample_id in score_dict
#         ]
#         cohort_data.append({
#             "color": cohort.color,
#             "values": cohort_scores,
#             "name": cohort.name
#         })

#     return {"cohorts": cohort_data}

# @app.post("/api/multi_cohort_distribution_with_ids/{pgs}/{score_type}")
# async def get_multi_cohort_distribution_with_ids(pgs: str, score_type: str, cohorts: List[CohortRequest]):
#     """Retrieve score distributions for multiple cohorts with individual sample data."""
    
#     conn = sqlite3.connect(DB_PATH)
#     conn.row_factory = sqlite3.Row
#     cursor = conn.cursor()

#     # Retrieve scores for the given PGS and score type
#     cursor.execute(
#         "SELECT SAMPLE_ID, SCORE FROM scores WHERE PGS_ID = ? AND SCORE_TYPE = ?",
#         (pgs, score_type)
#     )
#     rows = cursor.fetchall()
#     conn.close()

#     if not rows:
#         raise HTTPException(
#             status_code=404,
#             detail=f"No data found for PGS '{pgs}' and Score Type '{score_type}'"
#         )

#     # Create a dictionary mapping SAMPLE_ID to SCORE
#     score_dict = {row["SAMPLE_ID"]: row["SCORE"] for row in rows}

#     cohort_data = []
#     for cohort in cohorts:
#         # Filter to include only samples that exist in our data
#         valid_samples = [
#             {"SAMPLE_ID": sample_id, "SCORE": score_dict[sample_id]}
#             for sample_id in cohort.sample_ids
#             if sample_id in score_dict
#         ]
        
#         cohort_scores = [sample["SCORE"] for sample in valid_samples]
        
#         cohort_data.append({
#             "color": cohort.color,
#             "values": cohort_scores,
#             "samples": valid_samples,
#             "name": cohort.name
#         })

#     return {"cohorts": cohort_data}
