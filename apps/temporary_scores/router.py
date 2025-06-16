import uuid
import gzip
import tempfile
import os
from fastapi import APIRouter, Request, HTTPException, UploadFile, File, Form
from apps.session.service import SessionManager
from database import db

router = APIRouter(tags=["temporary_scores"])

@router.post("/api/temporary_scores/upload")
async def upload_temporary_scores(
    request: Request,
    pgs_id: str = Form(...),
    trait: str = Form(...),
    score_file: UploadFile = File(...)
):
    """Upload temporary score data."""
    user_id = SessionManager.get_or_create_user_id(request)
    
    try:
        # Read and process the uploaded file
        content = await score_file.read()
        
        # Handle gzipped files
        if score_file.filename.endswith('.gz'):
            content = gzip.decompress(content)
        
        # Parse the file content
        lines = content.decode('utf-8').strip().split('\n')
        header = lines[0].split('\t')
        
        # Validate expected columns exist
        expected_cols = ['sampleset', 'FID', 'IID', 'PGS', 'SUM', 'Z_MostSimilarPop', 'Z_norm1', 'Z_norm2', 'percentile_MostSimilarPop']
        if not all(col in header for col in expected_cols):
            raise HTTPException(status_code=400, detail="File missing required columns")
        
        # Find column indices
        iid_idx = header.index('IID')
        sum_idx = header.index('SUM')
        z_most_idx = header.index('Z_MostSimilarPop')
        z_norm1_idx = header.index('Z_norm1')
        z_norm2_idx = header.index('Z_norm2')
        percentile_idx = header.index('percentile_MostSimilarPop')
        
        # Prepare data for bulk insert
        scores_data = []
        for line in lines[1:]:  # Skip header
            fields = line.split('\t')
            sample_id = fields[iid_idx]
            
            # Add all score types for this sample
            score_types_data = [
                (user_id, pgs_id, 'SUM', sample_id, float(fields[sum_idx])),
                (user_id, pgs_id, 'Z_MostSimilarPop', sample_id, float(fields[z_most_idx])),
                (user_id, pgs_id, 'Z_norm1', sample_id, float(fields[z_norm1_idx])),
                (user_id, pgs_id, 'Z_norm2', sample_id, float(fields[z_norm2_idx])),
                (user_id, pgs_id, 'percentile_MostSimilarPop', sample_id, float(fields[percentile_idx]))
            ]
            scores_data.extend(score_types_data)
        
        # Insert all scores into database
        records_count = db.temporary_scores.create_temporary_score(user_id, pgs_id, trait, scores_data)
        
        # Track activity
        SessionManager.track_user_activity(request, "upload_temporary_scores", {
            "pgs_id": pgs_id,
            "trait": trait,
            "records_count": records_count
        })
        
        return {
            "status": "success",
            "pgs_id": pgs_id,
            "records_count": records_count
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

@router.get("/api/temporary_scores")
async def list_temporary_scores(request: Request):
    """List user's temporary scores."""
    user_id = SessionManager.get_or_create_user_id(request)
    temp_scores = db.temporary_scores.get_user_temporary_scores(user_id)
    return {"temporary_scores": temp_scores}

@router.delete("/api/temporary_scores/{temp_score_id}")
async def delete_temporary_score(request: Request, temp_score_id: str):
    """Delete a temporary score."""
    user_id = SessionManager.get_or_create_user_id(request)
    deleted = db.temporary_scores.delete_temporary_score(temp_score_id, user_id)
    
    if not deleted:
        raise HTTPException(status_code=404, detail="Temporary score not found")
    
    return {"status": "success", "message": "Temporary score deleted"}