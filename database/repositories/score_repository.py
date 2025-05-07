from ..base_repository import BaseRepository
import json
import numpy as np

class ScoreRepository(BaseRepository):
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
    

# Test functions
def test_score_repository():
    """Run tests for ScoreRepository methods"""
    from database import db_connection
    
    # Create a test repository
    test_repo = ScoreRepository(db_connection)
    
    # Test fetch_pgs_ids
    test_fetch_pgs_ids(test_repo)
    
    # Test get_scores_for_pgs
    test_get_scores_for_pgs(test_repo)
    
    # Test get_score_matrix
    test_get_score_matrix(test_repo)
    
    print("All tests passed!")

def test_fetch_pgs_ids(repo):
    """Test the fetch_pgs_ids method"""
    print("Testing fetch_pgs_ids...")
    
    # Test with no parameters (should return all PGS IDs)
    all_pgs_ids = repo.fetch_pgs_ids()
    assert isinstance(all_pgs_ids, list), "Expected a list of PGS IDs"
    assert len(all_pgs_ids) > 0, "Expected at least one PGS ID"
    print(f"  Found {len(all_pgs_ids)} total PGS IDs")
    
    # Test with score_type parameter
    score_type = "SUM"  # Adjust based on your data
    pgs_ids_by_score_type = repo.fetch_pgs_ids(score_type=score_type)
    assert isinstance(pgs_ids_by_score_type, list), "Expected a list of PGS IDs"
    print(f"  Found {len(pgs_ids_by_score_type)} PGS IDs with score type '{score_type}'")
    
    # Test with specific PGS IDs and score type
    if pgs_ids_by_score_type:
        specific_pgs_ids = pgs_ids_by_score_type[:2]  # Take first two PGS IDs
        filtered_pgs_ids = repo.fetch_pgs_ids(specific_pgs_ids=specific_pgs_ids, score_type=score_type)
        assert isinstance(filtered_pgs_ids, list), "Expected a list of PGS IDs"
        assert len(filtered_pgs_ids) <= len(specific_pgs_ids), "Expected fewer or equal number of PGS IDs"
        assert all(pgs_id in specific_pgs_ids for pgs_id in filtered_pgs_ids), "Expected all returned PGS IDs to be in the specific list"
        print(f"  Successfully filtered to {len(filtered_pgs_ids)} specific PGS IDs")

def test_get_scores_for_pgs(repo):
    """Test the get_scores_for_pgs method"""
    print("Testing get_scores_for_pgs...")
    
    # First get some PGS IDs to test with
    score_type = "SUM"  # Adjust based on your data
    pgs_ids = repo.fetch_pgs_ids(score_type=score_type)
    
    if not pgs_ids:
        print("  No PGS IDs available to test with")
        return
    
    # Test with a single PGS ID
    pgs_id = pgs_ids[0]
    scores = repo.get_scores_for_pgs(pgs_id, score_type)
    assert isinstance(scores, dict), "Expected a dictionary mapping sample IDs to scores"
    assert len(scores) > 0, "Expected at least one score"
    print(f"  Found {len(scores)} scores for PGS ID '{pgs_id}'")
    
    # Test with multiple PGS IDs
    if len(pgs_ids) >= 2:
        multiple_pgs_ids = pgs_ids[:2]
        scores = repo.get_scores_for_pgs(multiple_pgs_ids, score_type)
        assert isinstance(scores, dict), "Expected a dictionary mapping sample IDs to scores"
        print(f"  Found {len(scores)} scores for multiple PGS IDs")
    
    # Test with sample_ids filter
    if scores:
        sample_ids = list(scores.keys())[:5]  # Take first 5 sample IDs
        filtered_scores = repo.get_scores_for_pgs(pgs_id, score_type, sample_ids)
        assert isinstance(filtered_scores, dict), "Expected a dictionary mapping sample IDs to scores"
        assert len(filtered_scores) <= len(sample_ids), "Expected fewer or equal number of scores"
        assert all(sample_id in sample_ids for sample_id in filtered_scores), "Expected all returned sample IDs to be in the filter list"
        print(f"  Successfully filtered to {len(filtered_scores)} specific sample IDs")

def test_get_score_matrix(repo):
    """Test the get_score_matrix method"""
    print("Testing get_score_matrix...")
    
    # First get some PGS IDs and sample IDs to test with
    score_type = "SUM"  # Adjust based on your data
    pgs_ids = repo.fetch_pgs_ids(score_type=score_type)
    
    if not pgs_ids:
        print("  No PGS IDs available to test with")
        return
    
    # Get some sample IDs
    scores = repo.get_scores_for_pgs(pgs_ids[0], score_type)
    sample_ids = list(scores.keys())
    
    if not sample_ids:
        print("  No sample IDs available to test with")
        return
    
    # Test dict output
    matrix_dict, available_samples = repo.get_score_matrix(
        sample_ids[:10],  # Take first 10 sample IDs
        pgs_ids[:3],      # Take first 3 PGS IDs
        score_type,
        output_format="dict"
    )
    assert isinstance(matrix_dict, dict), "Expected a dictionary for matrix"
    assert isinstance(available_samples, list), "Expected a list for available samples"
    print(f"  Successfully created matrix dictionary with {len(matrix_dict)} samples")
    
    # Test numpy output
    matrix_numpy, available_pgs = repo.get_score_matrix(
        sample_ids[:10],  # Take first 10 sample IDs
        pgs_ids[:3],      # Take first 3 PGS IDs
        score_type,
        output_format="numpy"
    )
    assert isinstance(matrix_numpy, np.ndarray), "Expected a numpy array for matrix"
    assert isinstance(available_pgs, list), "Expected a list for available PGS IDs"
    print(f"  Successfully created numpy matrix with shape {matrix_numpy.shape}")
    
    # Test with missing value handling
    matrix_numpy_filled, _ = repo.get_score_matrix(
        sample_ids[:10],  # Take first 10 sample IDs
        pgs_ids[:3],      # Take first 3 PGS IDs
        score_type,
        output_format="numpy",
        handle_missing=True
    )
    assert isinstance(matrix_numpy_filled, np.ndarray), "Expected a numpy array for matrix"
    assert not np.isnan(matrix_numpy_filled).any(), "Expected no NaN values with handle_missing=True"
    print("  Successfully created numpy matrix with missing values handled")
    
    # Test with thresholds
    min_val, max_val = np.nanmin(matrix_numpy), np.nanmax(matrix_numpy)
    threshold_val = (max_val + min_val) / 2
    
    matrix_numpy_threshold, _ = repo.get_score_matrix(
        sample_ids[:10],  # Take first 10 sample IDs
        pgs_ids[:3],      # Take first 3 PGS IDs
        score_type,
        output_format="numpy",
        upper_threshold=threshold_val
    )
    assert isinstance(matrix_numpy_threshold, np.ndarray), "Expected a numpy array for matrix"
    assert np.nanmax(matrix_numpy_threshold) <= threshold_val, "Expected all values to be below upper threshold"
    print("  Successfully created numpy matrix with upper threshold applied")

# Add a function to run the tests if the file is executed directly
if __name__ == "__main__":
    test_score_repository()