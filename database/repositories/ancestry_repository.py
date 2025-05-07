from ..base_repository import BaseRepository
import json

class AncestryRepository(BaseRepository):
    def get_sample_ids_by_cohort(self, cohort=None):
        """
        Fetch sample IDs for a specific cohort
        
        Parameters:
        -----------
        cohort : str, optional
            Cohort/population name, or "ALL" for all samples
            
        Returns:
        --------
        list
            List of sample IDs
        """
        if cohort and cohort != "ALL":
            query = "SELECT sample_ids FROM ancestry_groups WHERE population = ?"
            result = self.execute_query_single(query, (cohort,))
            
            if result:
                # Parse the JSON array of sample IDs
                return json.loads(result[0])
            else:
                raise ValueError(f"Cohort '{cohort}' not found")
        else:
            return self.get_all_sample_ids()
    
    def get_all_sample_ids(self):
        """
        Get all sample IDs from all cohorts
        
        Returns:
        --------
        list
            List of all sample IDs
        """
        query = "SELECT sample_ids FROM ancestry_groups"
        rows = self.execute_query(query)
        return sum([json.loads(row[0]) for row in rows], [])
    
    def get_valid_sample_ids(self, sample_ids):
        """
        Filter a list of sample IDs to only those present in the database
        
        Parameters:
        -----------
        sample_ids : list
            List of sample IDs to check
            
        Returns:
        --------
        list
            List of valid sample IDs
        """
        placeholders = ','.join(['?'] * len(sample_ids))
        query = f"""
            SELECT DISTINCT SAMPLE_ID 
            FROM scores 
            WHERE SAMPLE_ID IN ({placeholders})
        """
        rows = self.execute_query(query, sample_ids)
        return [row[0] for row in rows]