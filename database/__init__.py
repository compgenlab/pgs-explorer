from fastapi import Depends
from .connection import DatabaseConnection
from .repositories.score_repository import ScoreRepository
from .repositories.ancestry_repository import AncestryRepository
from .repositories.metadata_repository import MetadataRepository

DB_PATH = '/data/dev/db/pgs_data.db' 
db_connection = DatabaseConnection(DB_PATH)

# Create global repository instances for non-FastAPI contexts
score_repository = ScoreRepository(db_connection)
ancestry_repository = AncestryRepository(db_connection)
metadata_repository = MetadataRepository(db_connection)

# Define dependency functions for FastAPI
async def get_db():
    """FastAPI dependency for database connection"""
    with db_connection.get_connection() as conn:
        yield conn

def get_score_repository():
    """Get ScoreRepository instance"""
    return score_repository

def get_ancestry_repository():
    """Get AncestryRepository instance"""
    return ancestry_repository

def get_metadata_repository():
    """Get MetadataRepository instance"""
    return metadata_repository