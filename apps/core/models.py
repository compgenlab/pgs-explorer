from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class TaskResponse(BaseModel):
    task_id: str
    task_type: str
    name: Optional[str] = None
    status: str
    created_at: str

class PlotResponse(BaseModel):
    plot_url: str
    table_data: List[Dict[str, Any]]