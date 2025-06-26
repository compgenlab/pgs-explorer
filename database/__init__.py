from fastapi import Depends
from .connection import DatabaseConnection
from .repositories.score_repository import ScoreRepository
from .repositories.ancestry_repository import AncestryRepository
from .repositories.metadata_repository import MetadataRepository
from .repositories.task_repository import TaskRepository
from .repositories.session_repository import SessionRepository
from .repositories.cohort_repository import CohortRepository
from .repositories.temporary_score_repository import TemporaryScoreRepository
from apps.core.config import DB_PATH, TASK_DB_PATH
import numpy as np

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
        self.temporary_scores = TemporaryScoreRepository(self.tasks_connection)  

    def get_connection(self):
        """Get the underlying database connection manager"""
        return self.connection

    def get_all_cohorts(self, user_id: str = None):
        """Get all cohorts available (ancestry + custom), formatted consistently."""
        all_cohorts = []
        
        # Get ancestry cohorts
        ancestry_cohorts = self.ancestry.get_all_cohorts()
        all_cohorts.extend(ancestry_cohorts)
        
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

    def get_all_pgs_with_traits(self, user_id: str = None):
        """Get all PGS IDs with traits (permanent + temporary), formatted consistently."""
        all_pgs = []
        
        # Get permanent PGS from main database
        permanent_pgs = self.scores.get_all_pgs_with_traits()  
        all_pgs.extend(permanent_pgs)
        print(f"Fetched {len(permanent_pgs)} permanent PGS from the lookup table.")

        # Get temporary PGS for this user
        if user_id:
            temp_pgs = self.temporary_scores.get_all_pgs_with_traits(user_id)
            print(f"Fetched {len(temp_pgs)} temporary PGS from the user session.")
            all_pgs.extend(temp_pgs)
        
        return all_pgs

    def get_all_pgs_ids(self, user_id: str = None):
        """Get all PGS IDs (permanent + temporary)."""
        all_pgs_with_traits = self.get_all_pgs_with_traits(user_id)
        return [pgs["id"] for pgs in all_pgs_with_traits]

    def get_score_types_for_pgs(self, pgs_id: str, user_id: str = None):
        """Get distinct score types for a given PGS_ID from both permanent and temporary sources."""
        # Check permanent scores first
        permanent_valid = self.scores.get_valid_pgs_ids([pgs_id])
        if permanent_valid:
            return self.scores.get_score_types_for_pgs(pgs_id)
        
        # If not found in permanent and user_id provided, try temporary
        if user_id:
            temporary_valid = self.temporary_scores.get_valid_pgs_ids([pgs_id], user_id)
            if temporary_valid:
                return self.temporary_scores.get_score_types_for_pgs(pgs_id, user_id)
        
        return []

    def get_scores_for_pgs(self, pgs_ids, score_type, sample_ids=None, user_id=None):
        """Get scores for one or more PGS IDs from both permanent and temporary sources."""
        if not isinstance(pgs_ids, list):
            pgs_ids = [pgs_ids]
        
        all_scores = {}
        
        # Split into valid permanent and temporary IDs
        permanent_pgs = self.scores.get_valid_pgs_ids(pgs_ids)
        temporary_pgs = []
        
        if user_id:
            temporary_pgs = self.temporary_scores.get_valid_pgs_ids(pgs_ids, user_id)
        
        # Get scores from permanent repository
        if permanent_pgs:
            pgs_scores = self.scores.get_scores_for_pgs(permanent_pgs, score_type, sample_ids)
            all_scores.update(pgs_scores)
        
        # Get scores from temporary repository
        if temporary_pgs and user_id:
            print(f"Detected temporary scores for: {temporary_pgs}")
            temp_scores = self.temporary_scores.get_scores_for_pgs(temporary_pgs, score_type, sample_ids, user_id)
            all_scores.update(temp_scores)
        
        return all_scores

    def get_all_scores_for_pgs(self, pgs_id: str, user_id: str = None):
        """Get all scores for a PGS ID across all score types and samples from both sources."""
        # Check permanent scores first
        permanent_valid = self.scores.get_valid_pgs_ids([pgs_id])
        if permanent_valid:
            return self.scores.get_all_scores_for_pgs(pgs_id)
        
        # If not found in permanent and user_id provided, try temporary
        if user_id:
            temporary_valid = self.temporary_scores.get_valid_pgs_ids([pgs_id], user_id)
            if temporary_valid:
                return self.temporary_scores.get_all_scores_for_pgs(pgs_id, user_id)
        
        return []

    def get_score_matrix(self, sample_ids, pgs_ids, score_type, user_id=None,
                        output_format="dict", handle_missing=False,
                        upper_threshold=None, lower_threshold=None):
        """Get score matrix combining permanent and temporary data."""
        if not isinstance(pgs_ids, list):
            pgs_ids = [pgs_ids]
        
        # Split into valid permanent and temporary IDs
        permanent_pgs = self.scores.get_valid_pgs_ids(pgs_ids)
        temporary_pgs = []
        
        if user_id:
            temporary_pgs = self.temporary_scores.get_valid_pgs_ids(pgs_ids, user_id)
        
        # Get data from both sources
        combined_dict = {}
        sample_pgs = []
        
        if permanent_pgs:
            perm_dict, _ = self.scores.get_score_matrix(
                sample_ids, permanent_pgs, score_type, "dict", 
                handle_missing, upper_threshold, lower_threshold
            )
            if perm_dict:
                sample_pgs = list(list(perm_dict.values())[0].keys())
            combined_dict.update(perm_dict)
        
        if temporary_pgs and user_id:
            temp_dict, _ = self.temporary_scores.get_score_matrix(
                sample_ids, temporary_pgs, score_type, user_id, "dict",
                handle_missing, upper_threshold, lower_threshold
            )
            if temp_dict:
                sample_pgs = list(list(temp_dict.values())[0].keys())
            
            # Merge temporary data into combined dict
            for sample_id, pgs_scores in temp_dict.items():
                if sample_id not in combined_dict:
                    combined_dict[sample_id] = {}
                combined_dict[sample_id].update(pgs_scores)
        
        if combined_dict:
            sample_pgs = list(list(combined_dict.values())[0].keys())
        
        if output_format == "numpy":
            # Convert combined dict to numpy matrix
            available_samples = list(combined_dict.keys())
            available_pgs = set()
            for sample_scores in combined_dict.values():
                available_pgs.update(sample_scores.keys())
            available_pgs = list(available_pgs)
            
            if sample_ids:
                final_samples = [s for s in sample_ids if s in available_samples]
            else:
                final_samples = available_samples
            
            final_pgs = [p for p in pgs_ids if p in available_pgs]
            sample_to_index = {sample_id: i for i, sample_id in enumerate(final_samples)}
            pgs_to_index = {pgs_id: j for j, pgs_id in enumerate(final_pgs)}
                
            matrix = np.full((len(final_samples), len(final_pgs)), np.nan)

            for sample_id, pgs_scores in combined_dict.items():
                i = sample_to_index.get(sample_id)
                if i is not None:
                    for pgs_id, score in pgs_scores.items():
                        j = pgs_to_index.get(pgs_id)
                        if j is not None:
                            matrix[i, j] = score

            if handle_missing:
                for j in range(matrix.shape[1]):
                    col_values = matrix[:, j]
                    non_nan_values = col_values[~np.isnan(col_values)]
                    if len(non_nan_values) > 0:
                        col_mean = np.mean(non_nan_values)
                        mask = np.isnan(col_values)
                        if mask.any():
                            matrix[mask, j] = col_mean

            return matrix, final_pgs
        else:
            return combined_dict, list(combined_dict.keys())

    def get_score_by_cohorts(self, pgs_id, score_type, cohorts, user_id=None):
        """Get scores for a PGS ID, grouped by cohorts from both sources."""
        # Check permanent scores first
        permanent_valid = self.scores.get_valid_pgs_ids([pgs_id])
        if permanent_valid:
            print(f"Score {pgs_id} is a permanent score.")
            return self.scores.get_score_by_cohorts(pgs_id, score_type, cohorts)
        
        # If not permanent and user_id provided, try temporary
        if user_id:
            temporary_valid = self.temporary_scores.get_valid_pgs_ids([pgs_id], user_id)
            if temporary_valid:
                print(f"Score {pgs_id} is a temporary score.")
                return self.temporary_scores.get_score_by_cohorts(pgs_id, score_type, cohorts, user_id)
        
        return []

    def get_sample_ids_with_scores(self, score_type, pgs_ids, user_id=None):
        """Get all sample IDs that have scores for the given PGS IDs and score type."""
        if not isinstance(pgs_ids, list):
            pgs_ids = [pgs_ids]
        
        all_sample_ids = set()
        
        # Split into valid permanent and temporary IDs
        permanent_pgs = self.scores.get_valid_pgs_ids(pgs_ids)
        temporary_pgs = []
        
        if user_id:
            temporary_pgs = self.temporary_scores.get_valid_pgs_ids(pgs_ids, user_id)
        
        # Get sample IDs from both sources (only if we have valid IDs)
        if permanent_pgs:
            perm_samples = self.scores.get_sample_ids_with_scores(score_type, permanent_pgs)
            all_sample_ids.update(perm_samples)
        
        if temporary_pgs and user_id:
            temp_samples = self.temporary_scores.get_sample_ids_with_scores(score_type, temporary_pgs, user_id)
            all_sample_ids.update(temp_samples)
        
        return sorted(list(all_sample_ids))

    def get_score_statistics_with_outliers(self, score_type, pgs_ids, user_id=None, std_dev_threshold=None):
        """Calculate comprehensive statistics for scores from both sources."""
        if not isinstance(pgs_ids, list):
            pgs_ids = [pgs_ids]
        
        # Split into valid permanent and temporary IDs
        permanent_pgs = self.scores.get_valid_pgs_ids(pgs_ids)
        temporary_pgs = []
        
        if user_id:
            temporary_pgs = self.temporary_scores.get_valid_pgs_ids(pgs_ids, user_id)
        
        print(f"DEBUG: permanent scores: {permanent_pgs}\n temporary: {temporary_pgs}")

        # Collect all scores from both sources
        all_scores = []
        
        # Get scores from permanent data
        if permanent_pgs:
            perm_dict = self.scores.get_score_matrix(
                sample_ids=None, pgs_ids=permanent_pgs, score_type=score_type, 
                output_format="dict"
            )[0]
            for sample_scores in perm_dict.values():
                all_scores.extend(sample_scores.values())
        
        # Get scores from temporary data
        if temporary_pgs and user_id:
            temp_dict = self.temporary_scores.get_score_matrix(
                sample_ids=None, pgs_ids=temporary_pgs, score_type=score_type, user_id=user_id,
                output_format="dict"
            )[0]
            for sample_scores in temp_dict.values():
                all_scores.extend(sample_scores.values())
        
        # Return default if no scores found
        if not all_scores:
            default_stats = {
                'avg': 0, 'min': 0, 'max': 0, 'stdev': 1.0, 'count': 0, 'outlier_count': 0
            }
            if std_dev_threshold is not None:
                default_stats.update({
                    'upper_threshold': 0,
                    'lower_threshold': 0
                })
            return default_stats
        
        avg = np.mean(all_scores)
        min_score = np.min(all_scores)
        max_score = np.max(all_scores)
        stdev = np.std(all_scores)
        count = len(all_scores)
        
        stats = {
            'avg': avg,
            'min': min_score,
            'max': max_score,
            'stdev': stdev,
            'count': count
        }
        
        # Calculate outliers if threshold provided
        if std_dev_threshold:
            print(std_dev_threshold)
            upper_threshold = avg + (std_dev_threshold * stdev)
            lower_threshold = avg - (std_dev_threshold * stdev)
            
            outlier_count = sum(1 for score in all_scores if score > upper_threshold or score < lower_threshold)
            
            stats.update({
                'outlier_count': outlier_count,
                'upper_threshold': upper_threshold,
                'lower_threshold': lower_threshold
            })
        print(stats)
        return stats

    def get_score_statistics(self, score_type, pgs_ids, user_id=None):
        """Calculate basic statistics for scores (backward compatibility)."""
        stats = self.get_score_statistics_with_outliers(score_type, pgs_ids, user_id)
        return (stats['avg'], stats['min'], stats['max'], stats['stdev'])

    def count_outliers(self, score_type, pgs_ids, upper_threshold, lower_threshold, user_id=None):
        """Count outliers in the dataset from both sources."""
        if not isinstance(pgs_ids, list):
            pgs_ids = [pgs_ids]
        
        # Split into valid permanent and temporary IDs
        permanent_pgs = self.scores.get_valid_pgs_ids(pgs_ids)
        temporary_pgs = []
        
        if user_id:
            temporary_pgs = self.temporary_scores.get_valid_pgs_ids(pgs_ids, user_id)
        
        total_outliers = 0
        
        if permanent_pgs:
            total_outliers += self.scores.count_outliers(score_type, permanent_pgs, upper_threshold, lower_threshold)
        
        if temporary_pgs and user_id:
            total_outliers += self.temporary_scores.count_outliers(score_type, temporary_pgs, upper_threshold, lower_threshold, user_id)
        
        return total_outliers

    def fetch_pgs_ids(self, specific_pgs_ids=None, score_type=None, user_id=None):
        """Fetch PGS IDs from both permanent and temporary sources."""
        permanent_ids = self.scores.fetch_pgs_ids(specific_pgs_ids, score_type)
        
        if user_id:
            temp_ids = self.temporary_scores.fetch_pgs_ids(user_id, specific_pgs_ids, score_type)
            # Combine and deduplicate
            all_ids = list(set(permanent_ids + temp_ids))
            return sorted(all_ids)
        
        return permanent_ids

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