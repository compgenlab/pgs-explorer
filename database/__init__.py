# database/__init__.py
from fastapi import Depends
from .connection import DatabaseConnection
from .repositories.score_repository import ScoreRepository
from .repositories.ancestry_repository import AncestryRepository
from .repositories.metadata_repository import MetadataRepository

DB_PATH = '/data/dev/db/pgs_data.db'

class Database:
    """Master database object that provides access to all repositories"""
    
    def __init__(self, db_path=None):
        """
        Initialize the Database with all repositories
        
        Parameters:
        -----------
        db_path : str, optional
            Path to the database. Defaults to DB_PATH if not provided
        """
        self.db_path = db_path or DB_PATH
        self.connection = DatabaseConnection(self.db_path)
        
        # Initialize repositories
        self.scores = ScoreRepository(self.connection)
        self.ancestry = AncestryRepository(self.connection)
        self.metadata = MetadataRepository(self.connection)
    
    def get_connection(self):
        """Get the underlying database connection manager"""
        return self.connection

# Create a default instance
db = Database()

# FastAPI dependency functions
async def get_db():
    """FastAPI dependency for database connection"""
    with db.connection.get_connection() as conn:
        yield conn

def get_database():
    """Get the Database instance for FastAPI"""
    return db

def get_score_repository():
    """Get ScoreRepository instance"""
    return db.scores

def get_ancestry_repository():
    """Get AncestryRepository instance"""
    return db.ancestry

def get_metadata_repository():
    """Get MetadataRepository instance"""
    return db.metadata
