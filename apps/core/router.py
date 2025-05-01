from fastapi import APIRouter, HTTPException
import sqlite3
import json
from apps.core.database import DB_PATH

router = APIRouter(tags=["core"])

@router.get("/api/metadata/{pgs_id}")
def get_metadata(pgs_id: str):
    """Fetches metadata for a given PGS_ID from the `pgs_metadata` table."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Fetch metadata for the given PGS_ID
    cursor.execute("SELECT * FROM pgs_metadata WHERE PGS_ID = ?", (pgs_id,))
    metadata = cursor.fetchone()

    # Fetch column names
    cursor.execute("PRAGMA table_info(pgs_metadata);")
    columns = [col[1] for col in cursor.fetchall()]

    conn.close()

    if not metadata:
        raise HTTPException(status_code=404, detail=f"Metadata not found for PGS_ID '{pgs_id}'")

    # Combine column names and metadata into a dictionary
    metadata_dict = dict(zip(columns, metadata))

    return {"metadata": metadata_dict}

@router.get("/api/pgs_list")
def get_pgs_list():
    """Fetches PGS IDs from pgs_metadata."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT PGS_ID FROM pgs_metadata ORDER BY PGS_ID")
    pgs_list = [row[0] for row in cursor.fetchall()]
    
    conn.close()
    return {"pgs": pgs_list}

@router.get("/api/score_types")
def get_score_types():
    """Fetches all distinct score types available in the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT DISTINCT SCORE_TYPE FROM scores ORDER BY SCORE_TYPE")
    score_types = [row[0] for row in cursor.fetchall()]
    
    conn.close()
    return {"score_types": score_types}

@router.get("/api/score_types/{pgs_id}")
def get_score_types_for_pgs(pgs_id: str):
    """Fetches distinct score types for a given PGS_ID from the `scores` table."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get unique score types for the given PGS_ID
    cursor.execute(
        "SELECT DISTINCT SCORE_TYPE FROM scores WHERE PGS_ID = ? ORDER BY SCORE_TYPE", 
        (pgs_id,)
    )
    score_types = [row[0] for row in cursor.fetchall()]

    conn.close()

    if not score_types:
        raise HTTPException(status_code=404, detail=f"No score types found for PGS_ID '{pgs_id}'")

    return {"score_types": score_types}

@router.get("/api/pgs_data/{pgs_id}")
def get_pgs_data(pgs_id: str):
    """Fetches sample scores from `scores` for a given PGS_ID."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Fetch sample score data
    cursor.execute(
        "SELECT SAMPLE_ID, SCORE_TYPE, SCORE FROM scores WHERE PGS_ID = ?", 
        (pgs_id,)
    )
    scores = cursor.fetchall()

    # Convert scores to list of dictionaries
    scores_list = [
        {"SAMPLE_ID": row[0], "SCORE_TYPE": row[1], "SCORE": row[2]} 
        for row in scores
    ]

    conn.close()

    return {"scores": scores_list}

@router.get("/api/permanent_cohorts")
async def get_permanent_cohorts():
    """Get list of permanent cohorts from the ancestry groups."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Query all populations and their sample IDs from ancestry_groups
        cursor.execute("SELECT population, sample_ids FROM ancestry_groups")
        rows = cursor.fetchall()
        cohort_list = [{"name": "ALL", "sample_ids": []}]
        
        for population, sample_ids_json in rows:
            # Parse the JSON array of sample IDs
            sample_ids = json.loads(sample_ids_json)
            print(f"For {population} loading {len(sample_ids)} samples.")
            if sample_ids:
                cohort_list.append({
                    "name": population,
                    "sample_ids": sample_ids
                })
        
        return {"cohorts": cohort_list}
    
    except Exception as e:
        print(f"Error retrieving populations from database: {e}")
        return {"cohorts": []}
