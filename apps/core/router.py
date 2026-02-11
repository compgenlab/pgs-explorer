from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse
import json
from database import db
import os 
from pathlib import Path
from apps.session.service import SessionManager

router = APIRouter(tags=["core"])

@router.get("/api/metadata/{pgs_id}")
def get_metadata(pgs_id: str):
    """Fetches metadata for a given PGS_ID from the `pgs_metadata` table."""
    # Use the metadata repository method
    metadata_list = db.active_db.metadata.fetch_pgs_metadata([pgs_id])
    
    if not metadata_list or pgs_id not in metadata_list:
        raise HTTPException(status_code=404, detail=f"Metadata not found for PGS_ID '{pgs_id}'")
    
    return {"metadata": metadata_list[pgs_id]}

@router.get("/api/pgs_list")
def get_pgs_list(request: Request):
    """Fetches PGS IDs from both permanent and temporary sources."""
    user_id = SessionManager.get_or_create_user_id(request)
    pgs_list = db.active_db.get_all_pgs_ids(user_id=user_id)
    return {"pgs": pgs_list}

@router.get("/api/pgs_and_trait_list")
def get_pgs_and_trait_list(request: Request):
    """Fetches PGS IDs with traits from both permanent and temporary sources."""
    user_id = SessionManager.get_or_create_user_id(request)
    pgs_list = db.active_db.get_all_pgs_with_traits(user_id=user_id)
    return {"pgs": pgs_list}
    
@router.get("/api/score_types")
def get_score_types(request: Request):
    """Fetches all distinct score types available in the database."""
    # For now, just return permanent score types since temporary ones are standardized
    score_types = db.active_db.scores.get_all_score_types()
    return {"score_types": score_types}

@router.get("/api/score_types/{pgs_id}")
def get_score_types_for_pgs(request: Request, pgs_id: str):
    """Fetches distinct score types for a given PGS_ID from both permanent and temporary sources."""
    user_id = SessionManager.get_or_create_user_id(request)
    score_types = db.active_db.get_score_types_for_pgs(pgs_id, user_id)
    
    if not score_types:
        raise HTTPException(status_code=404, detail=f"No score types found for PGS_ID '{pgs_id}'")
    
    return {"score_types": score_types}

# @router.get("/api/pgs_data/{pgs_id}")
# def get_pgs_data(request: Request, pgs_id: str):
#     """Fetches sample scores from both permanent and temporary sources for a given PGS_ID."""
#     user_id = SessionManager.get_or_create_user_id(request)
#     scores_data = db.active_db.get_all_scores_for_pgs(pgs_id, user_id)
    
#     if not scores_data:
#         raise HTTPException(status_code=404, detail=f"No scores found for PGS_ID '{pgs_id}'")
    
#     return {"scores": scores_data}

@router.get("/api/permanent_cohorts")
async def get_permanent_cohorts(request: Request):
    """Get list of permanent cohorts from the ancestry groups."""
    try:
        # Get user ID from session
        user_id = SessionManager.get_or_create_user_id(request)
        
        # Get all cohorts (ancestry + user's custom cohorts)
        cohorts = db.active_db.get_all_cohorts(user_id)
        
        # Add "ALL" as the first option
        cohort_list = [{"name": "ALL", "id": "ALL", "sample_id_count": db.active_db.ancestry.get_cohort_sample_count()}]
        for cohort in cohorts:
            cohort_list.append({"name": cohort["name"], "id": cohort["id"], "sample_id_count": len(cohort["sample_ids"])})
        # cohort_list.extend(cohorts)
        
        return JSONResponse(
            {"cohorts": cohort_list},
            headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"}
        )
    
    except Exception as e:
        print(f"Error retrieving populations from database: {e}")
        return JSONResponse(
            {"cohorts": []},
            headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"}
        )

# @router.get("/api/switch_active_db")
# async def switch_active_db(db_path):
#     try:
#         db.switch_active_db(db_path)
#         return True
#     except Exception as e: 
#         print(f"Error switching the active database: {e}")
#         return False

# @router.get("/api/db_list")
# async def get_db_list():
#     try:
#         db_list = [x.db_path for x in db.all_databases]
#         return db_list
#     except Exception as e:
#         print(f"Error getting database list: {e}")
#         return []


# @router.post("/api/create_database")
# async def create_database(
#     database_name: str = Form(...),
#     scores_file: UploadFile = File(...),
#     metadata_file: UploadFile = File(None)
# ):
#     try:
#         # Validate database name
#         if not database_name or not database_name.replace('_', '').replace('-', '').isalnum():
#             raise HTTPException(status_code=400, detail="Invalid database name. Use only letters, numbers, hyphens, and underscores.")
        
#         # Create upload directory on the server
#         upload_dir = Path("data/dev/db")
#         upload_dir.mkdir(parents=True, exist_ok=True)
        
#         # Backend saves the uploaded scores file
#         scores_file_path = upload_dir / scores_file.filename
#         with open(scores_file_path, "wb") as f:
#             content = await scores_file.read()
#             f.write(content)
        
#         # Backend saves the uploaded metadata file if provided
#         metadata_file_path = None
#         if metadata_file and metadata_file.filename:
#             metadata_file_path = upload_dir / metadata_file.filename
#             with open(metadata_file_path, "wb") as f:
#                 content = await metadata_file.read()
#                 f.write(content)
        
#         # Use the saved file paths to create database
#         new_db_path = db.add_new_database(
#             scores_file_path=str(scores_file_path),
#             database_name=database_name,
#             metadata_csv_path=str(metadata_file_path) if metadata_file_path else None
#         )
        
#         if new_db_path:
#             return {
#                 "success": True,
#                 "database_name": database_name,
#                 "database_path": new_db_path
#             }
#         else:
#             raise HTTPException(status_code=500, detail="Failed to create database")
    
#     except HTTPException:
#         raise
#     except Exception as e:
#         print(f"Error creating database: {e}")
#         raise HTTPException(status_code=500, detail=f"Error creating database: {str(e)}")
