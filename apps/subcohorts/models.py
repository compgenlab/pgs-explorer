from pydantic import BaseModel
from typing import List, Optional

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