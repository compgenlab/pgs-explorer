from pydantic import BaseModel
from typing import List, Optional
import sqlite3
import json

class SQLDatabase(BaseModel):
    DB_PATH: str = '/data/dev/db/pgs_data.db'
    
    class Config:
        arbitrary_types_allowed = True