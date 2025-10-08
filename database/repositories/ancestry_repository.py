from ..base_repository import BaseRepository
import json
from typing import List, Dict, Any

class AncestryRepository(BaseRepository):
    def get_cohort_sample_count(self, cohort=None): 
        return len(self.get_sample_ids_by_cohort(cohort))

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

    def get_sample_ancestry(self, sample_id):
        """
        Get ancestry information for a specific sample.
        
        Parameters:
        -----------
        sample_id : str
            The sample ID to look up
            
        Returns:
        --------
        str
            Ancestry/population information for the sample, or 'Unknown' if not found
        """
        query = """
            SELECT ag.population
            FROM ancestry_groups ag
            WHERE EXISTS (
                SELECT 1
                FROM json_each(ag.sample_ids) AS sample
                WHERE sample.value = ?
            )
        """
        
        result = self.execute_query_single(query, [sample_id])
        
        if result:
            return result['population']
        
        return 'Unknown'

    def get_all_cohorts(self) -> List[Dict[str, Any]]:
        """
        Get all cohorts/populations with their sample IDs.
        
        Returns:
        --------
        list
            List of dictionaries with name and sample_ids
        """
        query = """
            SELECT population, sample_ids 
            FROM ancestry_groups
            ORDER BY population
        """
        rows = self.execute_query(query)
        
        cohorts = []
        for row in rows:
            population = row["population"]
            sample_ids_json = row["sample_ids"]
            
            # Parse the JSON array of sample IDs
            try:
                sample_ids = json.loads(sample_ids_json) if sample_ids_json else []
                print(f"For {population} loading {len(sample_ids)} samples.")
                
                if sample_ids:
                    cohorts.append({
                        "name": population,
                        "id": population,
                        "sample_ids": sample_ids
                    })
            except json.JSONDecodeError as e:
                print(f"Error parsing sample_ids for {population}: {e}")
                continue
        
        return cohorts

    def get_cohort(self, name) -> Dict[str, Any]:
        """
        Get all cohorts/populations with their sample IDs.
        
        Returns:
        --------
        list
            List of dictionaries with name and sample_ids
        """
        query = """
            SELECT population, sample_ids 
            FROM ancestry_groups
            WHERE population = ?
        """
        result = self.execute_query_single(query, [name,])
        
        if result:
            population = result["population"]
            sample_ids_json = result["sample_ids"]
            
            # Parse the JSON array of sample IDs
            try:
                sample_ids = json.loads(sample_ids_json) if sample_ids_json else []
                print(f"For {population} loading {len(sample_ids)} samples.")
                
                if sample_ids:
                    return {
                        "cohort_name": population,
                        "cohort_id": population,
                        "sample_ids": sample_ids
                    }
            except json.JSONDecodeError as e:
                print(f"Error parsing sample_ids for {population}: {e}")

        return {}
