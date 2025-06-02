from pydantic import BaseModel

class InteractiveRequest(BaseModel):
    plot_type: str = "umap"
    plot_url: str
