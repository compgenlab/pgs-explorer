from ..base_repository import BaseRepository
from .ancestry_repository import AncestryRepository
import json
import numpy as np
# for testing
import time 
from ..connection import DatabaseConnection

class ScoreRepository(BaseRepository):
    def get_all_pgs_ids(self):
        query = """
            SELECT pgs_id 
            FROM pgs_id_lookup
            ORDER BY pgs_id
        """
        params = []        
        rows = self.execute_query(query, params)
        return [row[0] for row in rows]
    
    def get_all_score_types(self):
        query = """
            SELECT score_type
            FROM score_type_lookup
            ORDER BY score_type
        """
        params = []        
        rows = self.execute_query(query, params)
        return [row[0] for row in rows]

    def get_all_sample_ids(self):
        query = """
            SELECT sample_id
            FROM sample_id_lookup
            ORDER BY sample_id
        """
        params = []        
        rows = self.execute_query(query, params)
        return [row[0] for row in rows]

    # TODO get rid of 
    def fetch_pgs_ids(self, specific_pgs_ids=None, score_type=None):
        """
        Fetch PGS IDs based on criteria
        
        Parameters:
        -----------
        specific_pgs_ids : list, optional
            Specific PGS IDs to filter by
        score_type : str, optional
            Type of score to filter by
            
        Returns:
        --------
        list
            List of PGS IDs
        """
        if specific_pgs_ids and score_type:
            placeholders = ','.join(['?'] * len(specific_pgs_ids))
            query = f"""
                SELECT DISTINCT PGS_ID 
                FROM scores 
                WHERE SCORE_TYPE = ?
                AND PGS_ID IN ({placeholders})
                ORDER BY PGS_ID
            """
            params = [score_type] + specific_pgs_ids
        elif score_type:
            query = """
                SELECT DISTINCT PGS_ID 
                FROM scores 
                WHERE SCORE_TYPE = ?
                ORDER BY PGS_ID
            """
            params = [score_type]
        else:
            query = """
                SELECT DISTINCT PGS_ID 
                FROM scores
                ORDER BY PGS_ID
            """
            params = []
        
        rows = self.execute_query(query, params)
        return [row[0] for row in rows]
    
    # TODO get rid of 
    def get_scores_for_pgs(self, pgs_ids, score_type, sample_ids=None):
        """
        Get scores for one or more PGS IDs.
        
        Parameters:
        -----------
        pgs_ids : list or str
            PGS ID(s) to retrieve scores for
        score_type : str
            Type of score to retrieve
        sample_ids : list, optional
            List of sample IDs to filter by
        
        Returns:
        --------
        dict
            Dictionary mapping sample IDs to scores
        """
        # Ensure pgs_ids is a list
        if not isinstance(pgs_ids, list):
            pgs_ids = [pgs_ids]
        
        # Build query with placeholders for PGS IDs
        pgs_placeholders = ','.join(['?'] * len(pgs_ids))
        
        if sample_ids:
            sample_placeholders = ','.join(['?'] * len(sample_ids))
            query = f"""
                SELECT SAMPLE_ID, SCORE
                FROM scores
                WHERE PGS_ID IN ({pgs_placeholders})
                AND SCORE_TYPE = ?
                AND SAMPLE_ID IN ({sample_placeholders})
            """
            params = pgs_ids + [score_type] + sample_ids
        else:
            query = f"""
                SELECT SAMPLE_ID, SCORE
                FROM scores
                WHERE PGS_ID IN ({pgs_placeholders})
                AND SCORE_TYPE = ?
            """
            params = pgs_ids + [score_type]
        
        rows = self.execute_query(query, params)
        return {row["SAMPLE_ID"]: row["SCORE"] for row in rows}
    
    def get_score_matrix(self, sample_ids, pgs_ids, score_type, 
                         output_format="dict", handle_missing=False,
                         upper_threshold=None, lower_threshold=None):
        """
        Retrieve scores and construct a matrix.
        
        Parameters:
        -----------
        sample_ids : list
            List of sample IDs to include
        pgs_ids : list
            List of PGS IDs to include
        score_type : str
            Type of score to retrieve
        output_format : str, optional
            Format of output, either "dict" or "numpy"
        handle_missing : bool, optional
            Whether to replace missing values with column means
        upper_threshold : float, optional
            Maximum value for scores (scores above will be capped)
        lower_threshold : float, optional
            Minimum value for scores (scores below will be capped)
        
        Returns:
        --------
        dict or tuple
            Either nested dictionary or (numpy matrix, pgs_ids list)
        """
        # Build the query based on conditions
        if sample_ids and pgs_ids:
            sample_placeholders = ','.join(['?'] * len(sample_ids))
            pgs_placeholders = ','.join(['?'] * len(pgs_ids))
            query = f"""
                SELECT SAMPLE_ID, PGS_ID, SCORE
                FROM scores
                WHERE SCORE_TYPE = ?
                AND SAMPLE_ID IN ({sample_placeholders})
                AND PGS_ID IN ({pgs_placeholders})
            """
            params = [score_type] + sample_ids + pgs_ids
        elif sample_ids:
            sample_placeholders = ','.join(['?'] * len(sample_ids))
            query = f"""
                SELECT SAMPLE_ID, PGS_ID, SCORE
                FROM scores
                WHERE SCORE_TYPE = ?
                AND SAMPLE_ID IN ({sample_placeholders})
            """
            params = [score_type] + sample_ids
        elif pgs_ids:
            pgs_placeholders = ','.join(['?'] * len(pgs_ids))
            query = f"""
                SELECT SAMPLE_ID, PGS_ID, SCORE
                FROM scores
                WHERE SCORE_TYPE = ?
                AND PGS_ID IN ({pgs_placeholders})
            """
            params = [score_type] + pgs_ids
        else:
            query = """
                SELECT SAMPLE_ID, PGS_ID, SCORE
                FROM scores
                WHERE SCORE_TYPE = ?
            """
            params = [score_type]

        # Execute query and build dictionary
        data_dict = {}
        rows = self.execute_query(query, params)
        
        for row in rows:
            sample_id = row["SAMPLE_ID"]
            pgs_id = row["PGS_ID"]
            score = row["SCORE"]
            
            # Apply thresholds if provided
            if upper_threshold is not None and score > upper_threshold:
                score = upper_threshold
            elif lower_threshold is not None and score < lower_threshold:
                score = lower_threshold
                
            if sample_id not in data_dict:
                data_dict[sample_id] = {}
            data_dict[sample_id][pgs_id] = score
        
        # Return dictionary or convert to numpy matrix
        if output_format == "numpy":
            # Get all unique sample IDs and PGS IDs from the dictionary
            available_samples = list(data_dict.keys())
            
            # Get all unique PGS IDs by combining all dictionaries
            available_pgs = set()
            for sample_scores in data_dict.values():
                available_pgs.update(sample_scores.keys())
            available_pgs = list(available_pgs)
            
            # If specific sample_ids or pgs_ids were requested, filter to those that exist in the data
            if sample_ids:
                final_samples = [s for s in sample_ids if s in available_samples]
            else:
                final_samples = available_samples
            
            if pgs_ids:
                final_pgs = [p for p in pgs_ids if p in available_pgs]
            else:
                final_pgs = available_pgs
            
            # Create the index mappings
            sample_to_index = {sample_id: i for i, sample_id in enumerate(final_samples)}
            pgs_to_index = {pgs_id: j for j, pgs_id in enumerate(final_pgs)}
                
            matrix = np.full((len(final_samples), len(final_pgs)), np.nan)
    
            # Fill the matrix
            for sample_id, pgs_scores in data_dict.items():
                i = sample_to_index.get(sample_id)
                if i is not None:
                    for pgs_id, score in pgs_scores.items():
                        j = pgs_to_index.get(pgs_id)
                        if j is not None:  # Safety check
                            matrix[i, j] = score

            # Handle missing values if requested
            if handle_missing:
                for j in range(matrix.shape[1]):
                    col_values = matrix[:, j]
                    non_nan_values = col_values[~np.isnan(col_values)]
                    if len(non_nan_values) > 0:  # Only calculate mean if there are non-NaN values
                        col_mean = np.mean(non_nan_values)
                        mask = np.isnan(col_values)
                        if mask.any():  # Only fill if there are NaNs
                            matrix[mask, j] = col_mean

            return matrix, final_pgs
        else:
            return data_dict, list(data_dict.keys())
    
    def get_score_by_cohorts(self, pgs_id, score_type, cohorts):
        """
        Get scores for a PGS ID, grouped by cohorts.
        
        Parameters:
        -----------
        pgs_id : str
            PGS ID to retrieve scores for
        score_type : str
            Type of score to retrieve
        cohorts : list
            List of cohort dictionaries with name, color, and sample_ids

        Returns:
        --------
        list
            List of dictionaries containing cohort data
        """
        ancestry_repository = AncestryRepository()
        
        # Get all scores for this PGS ID
        score_dict = self.get_scores_for_pgs(pgs_id, score_type)
        
        cohort_data = []
        for cohort in cohorts:
            if "name" not in cohort:
                continue
                
            if cohort["name"] != "ALL":
                # If sample_ids not provided, get them from ancestry repository
                if "sample_ids" not in cohort:
                    cohort["sample_ids"] = ancestry_repository.get_sample_ids_by_cohort(cohort["name"])
                    
                # Filter to include only samples that exist in our data
                valid_samples = [
                    {"SAMPLE_ID": sample_id, "SCORE": score_dict[sample_id]}
                    for sample_id in cohort["sample_ids"]
                    if sample_id in score_dict
                ]
            else:
                # For 'ALL' cohort, include all samples
                valid_samples = [
                    {"SAMPLE_ID": sample_id, "SCORE": score}
                    for sample_id, score in score_dict.items()
                ]
                
            cohort_scores = [sample["SCORE"] for sample in valid_samples]
            
            cohort_data.append({
                "color": cohort.get("color", "#000000"),
                "values": cohort_scores,
                "samples": valid_samples,
                "name": cohort["name"]
            })

        return cohort_data


DB_PATH = '/data/dev/db/pgs_data.db' 
db_connection = DatabaseConnection(DB_PATH)
test_run = ScoreRepository(db_connection)
start_time = time.time()
print(f"Found {len(test_run.get_all_pgs_ids())} unique PGS IDs in {time.time()-start_time} seconds.")
start_time = time.time()
print(f"Found {len(test_run.get_all_score_types())} unique score types in {time.time()-start_time} seconds.")
start_time = time.time()
print(f"Found {len(test_run.get_all_sample_ids())} unique sample IDs in {time.time()-start_time} seconds.")