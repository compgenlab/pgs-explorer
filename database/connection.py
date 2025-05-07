import sqlite3
from contextlib import contextmanager

class DatabaseConnection:
    def __init__(self, db_path):
        self.db_path = db_path
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable row factory for named columns
        try:
            yield conn
        finally:
            conn.close()
            
    async def get_db(self):
        """Async connection provider for FastAPI dependency injection"""
        with self.get_connection() as conn:
            yield conn