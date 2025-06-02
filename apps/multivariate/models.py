from pydantic import BaseModel, validator
from typing import List, Optional

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

class InteractiveRequest(BaseModel):
    plot_type: str = "umap"
    plot_url: str
