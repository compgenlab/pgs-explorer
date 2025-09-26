from pydantic import BaseModel
from typing import List, Optional

class CohortRequest(BaseModel):
    # sample_ids: List[str]
    color: str
    name: Optional[str] = None
    id: Optional[str] = None

class ScoreComparisonRequest(BaseModel):
    pgs_ids: List[str]
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
    cohort_id: Optional[str] = None
    pgs_comparison: Optional[ScoreComparisonRequest] = None

    # Job name
    name: Optional[str] = None

    # User info
    user_id: Optional[str] = None