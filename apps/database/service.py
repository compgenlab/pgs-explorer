from .models import SQLDatabase
import sqlite3
import json
import numpy as np

# Create a single instance to be imported
db = SQLDatabase()

def get_connection():
    """Get a connection to the database"""
    return sqlite3.connect(db.DB_PATH)

def fetch_pgs_ids(db, specific_pgs_ids, score_type):
    # TODO completely changing this - use validate pgs ids if populated and use get all if not (take out scoretype)
    """Fetch PGS IDs based on criteria"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get PGS IDs 
    if specific_pgs_ids:
        placeholders = ','.join(['?'] * len(specific_pgs_ids))
        cursor.execute(f"""
            SELECT DISTINCT PGS_ID 
            FROM scores 
            WHERE SCORE_TYPE = ?
            AND PGS_ID IN ({placeholders})
            ORDER BY PGS_ID
        """, [score_type] + specific_pgs_ids)
    else:
        cursor.execute("""
            SELECT DISTINCT PGS_ID 
            FROM scores 
            WHERE SCORE_TYPE = ?
            ORDER BY PGS_ID
        """, (score_type,))
    
    pgs_ids = [row[0] for row in cursor.fetchall()]
    conn.close()
    return pgs_ids

def sample_ids_by_cohort(cohort=None):
    """Fetch sample IDs based on criteria"""
    if cohort and cohort != "ALL":
        conn = get_connection()
        cursor = conn.cursor()
        
        # Query the ancestry table to get sample IDs for the specified population
        cursor.execute("SELECT sample_ids FROM ancestry_groups WHERE population = ?", (cohort,))
        cohort_result = cursor.fetchone()
        
        if cohort_result:
            # Parse the JSON array of sample IDs
            sample_ids = json.loads(cohort_result[0])
        else:
            raise Exception 

        conn.close()
    else:
        sample_ids = all_sample_ids()
    
    return sample_ids


def fetch_pgs_metadata(pgs_ids):
    """Fetch metadata for given PGS IDs from the SQLite database."""
    if pgs_ids:
        placeholders = ','.join('?' for _ in pgs_ids)
        query = f"""
            SELECT PGS_ID, PGS_Name, Reported_Trait, PGS_Publication_ID
            FROM pgs_metadata
            WHERE PGS_ID IN ({placeholders})
        """
    else:
        query = f"""
            SELECT PGS_ID, PGS_Name, Reported_Trait, PGS_Publication_ID
            FROM pgs_metadata
        """

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(query, pgs_ids)
        rows = cursor.fetchall()
    
    pgs_metadata = {}
    for row in rows:
        pgs_metadata[row[0]] = {
            "PGS_Name": row[1],
            "Reported_Trait": row[2],
            "Publication_ID": row[3]
        }

    # Check for missing metadata
    if pgs_ids:
        missing_metadata = set(pgs_ids) - set(pgs_metadata.keys())
        if missing_metadata:
            print(f"Warning: {len(missing_metadata)} PGS_IDs don't have metadata")
            for pgs_id in missing_metadata:
                pgs_metadata[pgs_id] = {
                    'PGS_Name': 'Unknown',
                    'Reported_Trait': 'Unknown',
                    'Publication_ID': 'Unknown'
                }

    # Convert to dictionary keyed by PGS_ID
    return pgs_metadata

def fetch_pgs_ids(specific_pgs_ids, score_type):
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get PGS IDs
    if not specific_pgs_ids:
        cursor.execute("""
            SELECT DISTINCT PGS_ID 
            FROM scores 
            WHERE SCORE_TYPE = ?
            ORDER BY PGS_ID
        """, (score_type,))
        pgs_ids = [row[0] for row in cursor.fetchall()]
    else:
        pgs_ids = specific_pgs_ids

    print(f"Selected {len(pgs_ids)} PGS_IDs.")
    conn.close()
    return pgs_ids

def all_pgs_ids():
    return

def all_sample_ids():
    conn = get_connection()
    cursor = conn.cursor()
    sample_ids = sum([json.loads(row[0]) for row in cursor.execute("SELECT sample_ids FROM ancestry_groups")], [])
    conn.close()
    return sample_ids

def valid_sample_ids(sample_ids):
    """
    Takes a list of provided sample IDs and returns the valid IDs present in score database.
    """
    return

def valid_pgs_ids(pgs_ids):
    """
    Takes a list of provided PGS IDs and returns the valid IDs present in score database.
    """
    return

def get_pgs_scores_for_comparison(score_type, pgs_ids, sample_ids=None):
    """
    Get scores for multiple PGS IDs and optionally filter by sample IDs.
    
    Parameters:
    -----------
    score_type : str
        Type of score to retrieve
    pgs_ids : list
        List of PGS IDs to retrieve scores for
    sample_ids : list, optional
        List of sample IDs to filter by
    
    Returns:
    --------
    list
        List of dictionaries containing PGS data with values, samples, etc.
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    result = []
    
    # For each PGS ID, retrieve the scores
    for i, pgs_id in enumerate(pgs_ids):
        # Build query
        if sample_ids:
            sample_placeholders = ','.join(['?'] * len(sample_ids))
            query = f"""
                SELECT SAMPLE_ID, SCORE
                FROM scores
                WHERE PGS_ID = ?
                AND SCORE_TYPE = ?
                AND SAMPLE_ID IN ({sample_placeholders})
            """
            params = [pgs_id, score_type] + sample_ids
        else:
            query = """
                SELECT SAMPLE_ID, SCORE
                FROM scores
                WHERE PGS_ID = ?
                AND SCORE_TYPE = ?
            """
            params = [pgs_id, score_type]
        
        # Execute query
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        if not rows:
            continue  # Skip if no data found for this PGS
        
        # Create sample data
        valid_samples = [{"SAMPLE_ID": row["SAMPLE_ID"], "SCORE": row["SCORE"]} for row in rows]
        scores = [sample["SCORE"] for sample in valid_samples]
        
        result.append({
            "values": scores,
            "samples": valid_samples,
            "name": pgs_id  # This will be replaced with the display name in the visualization service
        })
    
    conn.close()
    return result

def get_score_by_cohorts(pgs_id, score_type, cohorts):
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
        List of dictionaries containing cohort data with values, samples, etc.
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get all scores for this PGS ID and score type
    cursor.execute(
        "SELECT SAMPLE_ID, SCORE FROM scores WHERE PGS_ID = ? AND SCORE_TYPE = ?",
        (pgs_id, score_type)
    )
    rows = cursor.fetchall()
    
    # Create a dictionary mapping SAMPLE_ID to SCORE
    score_dict = {row["SAMPLE_ID"]: row["SCORE"] for row in rows}
    
    cohort_data = []
    for cohort in cohorts:
        if "name" not in cohort:
            continue
            
        if cohort["name"] != "ALL":
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

    conn.close()
    return cohort_data
    
def get_score_matrix(
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
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
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


# SAMPLE ID TESTING
afr = sample_ids_by_cohort("AFR")
print(f"Tested pulling AFR samples; received {len(afr)} back.")
all_samples = sample_ids_by_cohort("ALL")
print(f"Tested pulling ALL samples; received {len(all_samples)} back.")
all_samples = sample_ids_by_cohort()
print(f"Tested pulling ALL samples with no spec; received {len(all_samples)} back.")
