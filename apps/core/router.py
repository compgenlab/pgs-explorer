from fastapi import APIRouter, HTTPException, Depends
import json
from database import db, get_database, Database

router = APIRouter(tags=["core"])

@router.get("/api/metadata/{pgs_id}")
def get_metadata(pgs_id: str, database: Database = Depends(get_database)):
    """Fetches metadata for a given PGS_ID from the `pgs_metadata` table."""
    # Use the metadata repository method
    metadata_list = database.metadata.fetch_pgs_metadata([pgs_id])
    
    if not metadata_list or pgs_id not in metadata_list:
        raise HTTPException(status_code=404, detail=f"Metadata not found for PGS_ID '{pgs_id}'")
    
    return {"metadata": metadata_list[pgs_id]}

@router.get("/api/pgs_list")
def get_pgs_list(database: Database = Depends(get_database)):
    """Fetches PGS IDs from pgs_metadata."""
    # Get all PGS IDs using the score repository
    pgs_list = db.scores.get_all_pgs_ids()
    return {"pgs": pgs_list}

@router.get("/api/score_types")
def get_score_types(database: Database = Depends(get_database)):
    """Fetches all distinct score types available in the database."""
    # Get all score types using the score repository
    score_types = db.scores.get_all_score_types()
    return {"score_types": score_types}

@router.get("/api/score_types/{pgs_id}")
def get_score_types_for_pgs(pgs_id: str, database: Database = Depends(get_database)):
    """Fetches distinct score types for a given PGS_ID from the `scores` table."""
    # Get score types for specific PGS ID
    score_types = db.scores.get_score_types_for_pgs(pgs_id)
    
    if not score_types:
        raise HTTPException(status_code=404, detail=f"No score types found for PGS_ID '{pgs_id}'")
    
    return {"score_types": score_types}

@router.get("/api/pgs_data/{pgs_id}")
def get_pgs_data(pgs_id: str, database: Database = Depends(get_database)):
    """Fetches sample scores from `scores` for a given PGS_ID."""
    # Get all scores for a PGS ID across all score types
    scores_data = db.scores.get_all_scores_for_pgs(pgs_id)
    
    if not scores_data:
        raise HTTPException(status_code=404, detail=f"No scores found for PGS_ID '{pgs_id}'")
    
    return {"scores": scores_data}

@router.get("/api/permanent_cohorts")
async def get_permanent_cohorts(database: Database = Depends(get_database)):
    """Get list of permanent cohorts from the ancestry groups."""
    try:
        # Get all cohorts from ancestry repository
        cohorts = db.ancestry.get_all_cohorts()
        
        # Add "ALL" as the first option
        cohort_list = [{"name": "ALL", "sample_ids": []}]
        cohort_list.extend(cohorts)
        
        return {"cohorts": cohort_list}
    
    except Exception as e:
        print(f"Error retrieving populations from database: {e}")
        return {"cohorts": []}