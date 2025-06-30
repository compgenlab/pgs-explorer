from fastapi import APIRouter, HTTPException, Form, File, UploadFile, Request, Depends
from fastapi.responses import JSONResponse
from typing import List, Optional
import os
import uuid
from .connection import create_database_from_upload, discover_existing_databases
from database import get_database_manager 

router = APIRouter(prefix="/api")

@router.get("/databases")
async def list_databases():
    """Get all available databases"""
    try:
        databases = discover_existing_databases()
        return databases
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/database/current")
async def get_current_database(db_manager=Depends(get_database_manager)):
    """Get currently selected database"""
    try:
        current_info = db_manager.get_current_dataset_info()
        if current_info:
            return {"database": current_info}
        else:
            return {"database": None}
    except Exception as e:
        return {"database": None}

@router.post("/database/select")
async def select_database(
    request: Request, 
    database_path: str = Form(...),
    db_manager=Depends(get_database_manager)
):
    """Select a database for the current session"""
    try:
        # Validate the database exists
        databases = discover_existing_databases()
        selected_db = next((db for db in databases if db['path'] == database_path), None)
        
        if not selected_db:
            raise HTTPException(status_code=404, detail="Database not found")
        
        # Update the DatabaseManager
        db_manager.set_dataset(database_path)
        
        # Store in session for persistence across requests
        request.session['current_database_path'] = database_path
        request.session['current_database'] = selected_db
        
        return {"success": True, "database": selected_db}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/databases/create")
async def create_database(
    name: str = Form(...),
    description: str = Form(""),
    score_files: List[UploadFile] = File(...),
    db_manager=Depends(get_database_manager)
):
    """Create a new database from uploaded files"""
    task_id = str(uuid.uuid4())
    
    # Save uploaded files temporarily
    temp_files = []
    try:
        for file in score_files:
            temp_path = f"/tmp/{task_id}_{file.filename}"
            with open(temp_path, "wb") as f:
                content = await file.read()
                f.write(content)
            temp_files.append(temp_path)
        
        # Create database
        result = create_database_from_upload(name, temp_files)
        
        if result['success']:
            # Clear the database cache so new database is recognized
            db_manager.clear_cache()
            
            return {
                "task_id": task_id,
                "database_name": result['name'],
                "database_path": result['path'],
                "message": f"Database created with {result['files_processed']} files"
            }
        else:
            raise HTTPException(status_code=400, detail=result['error'])
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Clean up temp files
        for temp_file in temp_files:
            if os.path.exists(temp_file):
                os.remove(temp_file)

@router.get("/databases/create/status/{task_id}")
async def get_database_creation_status(task_id: str):
    """Get status of database creation"""
    return {
        "status": "completed",
        "progress": 1.0,
        "message": "Database created successfully",
        "database_name": "New Database",
        "database_path": "db/new_database"
    }

# Helper endpoint to restore database selection from session
@router.post("/database/restore-session")
async def restore_database_from_session(
    request: Request,
    db_manager=Depends(get_database_manager)
):
    """Restore database selection from session"""
    try:
        stored_path = request.session.get('current_database_path')
        if stored_path and os.path.exists(stored_path):
            db_manager.set_dataset(stored_path)
            return {"success": True, "restored": stored_path}
        else:
            return {"success": False, "message": "No valid session database found"}
    except Exception as e:
        return {"success": False, "message": str(e)}