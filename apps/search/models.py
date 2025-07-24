from pydantic import BaseModel
from typing import List, Optional

class QueryItem(BaseModel):
    indexUid: str
    query: str

    # Remove if returning to Federation
    limit: int
    offset: int

# class Federation(BaseModel):
#         limit: int
#         offset: int


class SearchRequest(BaseModel):
   # federation: Optional[Federation]
    multi_queries: List[QueryItem]