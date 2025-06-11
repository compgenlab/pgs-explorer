from fastapi import Depends
from .connection import DatabaseConnection
from .repositories.score_repository import ScoreRepository
from .repositories.ancestry_repository import AncestryRepository
from .repositories.metadata_repository import MetadataRepository
from .repositories.task_repository import TaskRepository
from .repositories.session_repository import SessionRepository
from .repositories.cohort_repository import CohortRepository
from apps.core.config import DB_PATH, TASK_DB_PATH

class Database:
    """Master database object that provides access to all repositories"""
    
    def __init__(self, db_path=None, task_db_path=None):
        """
        Initialize the Database with all repositories
        
        Parameters:
        -----------
        db_path : str, optional
            Path to the database. Defaults to DB_PATH if not provided
        """
        self.db_path = db_path or DB_PATH
        self.task_db_path = task_db_path or TASK_DB_PATH

        self.connection = DatabaseConnection(self.db_path)
        self.tasks_connection = DatabaseConnection(self.task_db_path, is_task_db=True)

        # Initialize repositories
        self.scores = ScoreRepository(self.connection)
        self.ancestry = AncestryRepository(self.connection)
        self.metadata = MetadataRepository(self.connection)
        self.tasks = TaskRepository(self.tasks_connection)
        self.sessions = SessionRepository(self.tasks_connection)
        self.cohorts = CohortRepository(self.tasks_connection)  
        
    def get_connection(self):
        """Get the underlying database connection manager"""
        return self.connection

    def get_all_cohorts(self, user_id: str = None):
        """Get all cohorts available (ancestry + custom), formatted consistently."""
        all_cohorts = []
        
        # Get ancestry cohorts
        ancestry_cohorts = self.ancestry.get_all_cohorts()
        all_cohorts.extend(ancestry_cohorts)
        # for cohort in ancestry_cohorts:
        #     all_cohorts.append({
        #         "cohort_id": cohort["name"],
        #         "cohort_name": cohort["name"],
        #         "type": "ancestry",
        #         "sample_count": len(cohort["sample_ids"])
        #     })
        
        if user_id:
            print(f"Getting cohorts for {user_id}")
            custom_cohorts = self.cohorts.get_user_cohorts(user_id)
            
            # Format to match ancestry cohort structure
            formatted_custom = [
                {
                    "name": cohort["cohort_name"],
                    "sample_ids": cohort["sample_ids"]
                }
                for cohort in custom_cohorts
            ]
            
            all_cohorts.extend(formatted_custom)
        
        return all_cohorts
    
    def get_sample_ids_by_cohort(self, cohort: str, user_id: str = None):
        """Get sample IDs for any cohort type (ancestry or custom)."""
        
        # Handle "ALL" case
        if cohort == "ALL":
            return self.ancestry.get_all_sample_ids()
        
        # Try custom cohort first (if user_id provided)
        if user_id:
            custom_cohort = self.cohorts.get_cohort(cohort, user_id)
            if custom_cohort:
                return custom_cohort["sample_ids"]
        
        # Try ancestry cohort
        try:
            return self.ancestry.get_sample_ids_by_cohort(cohort)
        except ValueError:
            pass
        
        # If nothing found, raise error
        raise ValueError(f"Cohort '{cohort}' not found")

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

def get_task_repository():
    """Get TaskRepository instance"""
    return db.tasks