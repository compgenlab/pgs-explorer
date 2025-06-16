from fastapi import APIRouter, HTTPException, Depends, Request
import json
from database import db, get_database, Database
from apps.session.service import SessionManager

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
def get_pgs_list(request: Request, database: Database = Depends(get_database)):
    """Fetches PGS IDs from both permanent and temporary sources."""
    user_id = SessionManager.get_or_create_user_id(request)
    pgs_list = db.get_all_pgs_ids(user_id=user_id)
    return {"pgs": pgs_list}

@router.get("/api/pgs_and_trait_list")
def get_pgs_and_trait_list(request: Request, database: Database = Depends(get_database)):
    """Fetches PGS IDs with traits from both permanent and temporary sources."""
    user_id = SessionManager.get_or_create_user_id(request)
    pgs_list = db.get_all_pgs_with_traits(user_id=user_id)
    return {"pgs": pgs_list}
    
@router.get("/api/score_types")
def get_score_types(request: Request, database: Database = Depends(get_database)):
    """Fetches all distinct score types available in the database."""
    # For now, just return permanent score types since temporary ones are standardized
    score_types = db.scores.get_all_score_types()
    return {"score_types": score_types}

@router.get("/api/score_types/{pgs_id}")
def get_score_types_for_pgs(request: Request, pgs_id: str, database: Database = Depends(get_database)):
    """Fetches distinct score types for a given PGS_ID from both permanent and temporary sources."""
    user_id = SessionManager.get_or_create_user_id(request)
    score_types = db.get_score_types_for_pgs(pgs_id, user_id)
    
    if not score_types:
        raise HTTPException(status_code=404, detail=f"No score types found for PGS_ID '{pgs_id}'")
    
    return {"score_types": score_types}

@router.get("/api/pgs_data/{pgs_id}")
def get_pgs_data(request: Request, pgs_id: str, database: Database = Depends(get_database)):
    """Fetches sample scores from both permanent and temporary sources for a given PGS_ID."""
    user_id = SessionManager.get_or_create_user_id(request)
    scores_data = db.get_all_scores_for_pgs(pgs_id, user_id)
    
    if not scores_data:
        raise HTTPException(status_code=404, detail=f"No scores found for PGS_ID '{pgs_id}'")
    
    return {"scores": scores_data}

@router.get("/api/permanent_cohorts")
async def get_permanent_cohorts(
    request: Request,
    database: Database = Depends(get_database)
):
    """Get list of permanent cohorts from the ancestry groups."""
    try:
        # Get user ID from session
        user_id = SessionManager.get_or_create_user_id(request)
        
        # Get all cohorts (ancestry + user's custom cohorts)
        cohorts = db.get_all_cohorts(user_id)
        
        # Add "ALL" as the first option
        cohort_list = [{"name": "ALL", "sample_ids": []}]
        cohort_list.extend(cohorts)
        
        return {"cohorts": cohort_list}
    
    except Exception as e:
        print(f"Error retrieving populations from database: {e}")
        return {"cohorts": []}
        