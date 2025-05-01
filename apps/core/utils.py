import sqlite3
import json  
from apps.core.database import DB_PATH

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
        placeholders = ','.join('?' for _ in pgs_ids)
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
    conn = sqlite3.connect(DB_PATH)
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

def fetch_sample_ids(cohort, pgs_ids, score_type):    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    print("Getting all SAMPLE_IDs for the selected PGS_IDs...")

    if cohort and cohort != "ALL":
        # Query the ancestry table to get sample IDs for the specified population
        cursor.execute("SELECT sample_ids FROM ancestry_groups WHERE population = ?", (cohort,))
        cohort_result = cursor.fetchone()
        sample_ids = json.loads(cohort_result[0])
        print(f"Filtering to {len(sample_ids)} samples from {cohort} population")
    else:
        # No population filtering
        cursor.execute(f"""
            SELECT DISTINCT SAMPLE_ID 
            FROM scores 
            WHERE SCORE_TYPE = ? 
            AND PGS_ID IN ({','.join(['?']*len(pgs_ids))})
            ORDER BY SAMPLE_ID
        """, [score_type] + pgs_ids)
        sample_ids = [row[0] for row in cursor.fetchall()]    
    
    conn.close()
    return sample_ids
