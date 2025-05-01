import numpy as np
import sqlite3
from apps.core.database import DB_PATH

# Utility functions
def get_matrix(
    sample_ids, 
    pgs_ids, 
    score_type,
    output_format="dict",   # Options: "dict", "numpy"
    handle_missing=False,   # Whether to fill NaN values with column means
    upper_threshold=None,   # Cap scores above this value
    lower_threshold=None    # Cap scores below this value
):
    """
    Retrieve scores and construct a matrix using temporary tables for efficiency.
    
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
        Whether to replace missing values with column means (only for numpy output)
    upper_threshold : float, optional
        Maximum value for scores (scores above will be capped)
    lower_threshold : float, optional
        Minimum value for scores (scores below will be capped)
    
    Returns:
    --------
    dict or numpy.ndarray
        Either nested dictionary or numpy matrix of scores
    """
    # Establish connection to the database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        if sample_ids and pgs_ids:
            # Create the temp table with proper placeholders
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
            sample_placeholders = ','.join(['?'] * len(sample_ids))
            query = f"""
                SELECT SAMPLE_ID, PGS_ID, SCORE
                FROM scores
                WHERE SCORE_TYPE = ?
                AND PGS_ID IN ({pgs_placeholders})
            """
            params = [score_type] + pgs_ids
        else:
            query = f"""
                SELECT SAMPLE_ID, PGS_ID, SCORE
                FROM scores
                WHERE SCORE_TYPE = ?
            """
            params = [score_type]

        data_dict = {}
        scores_list = []
        print("Filling table")
        for i, (sample_id, pgs_id, score) in enumerate(cursor.execute(query, params)):
            # Apply thresholds if provided
            if upper_threshold is not None and score > upper_threshold:
                score = upper_threshold
            elif lower_threshold is not None and score < lower_threshold:
                score = lower_threshold
                
            if sample_id not in data_dict:
                data_dict[sample_id] = {}
            data_dict[sample_id][pgs_id] = score
            scores_list.append(score)

            if i % 1000000 == 0:
                print(f"Processed {i} rows.")
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
            return data_dict, data_dict.keys()
            
    finally:
        # # Clean up temp table and close connection
        conn.close()
