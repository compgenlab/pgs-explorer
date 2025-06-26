from fastapi import APIRouter, HTTPException, Form, File, UploadFile, Request
from fastapi.responses import JSONResponse
from typing import List, Optional
import os
import uuid
from .connection import create_database_from_upload, discover_existing_databases

router = APIRouter(prefix="/api")

@router.get("/databases")
async def list_databases():
    """Get all available databases"""
    try:
        databases = discover_existing_databases("/data/dev/db/")
        return databases
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/database/current")
async def get_current_database(request: Request):
    """Get currently selected database"""
    current_db = request.session.get('current_database')
    if current_db:
        return {"database": current_db}
    else:
        return {"database": None}

@router.post("/database/select")
async def select_database(request: Request, database_path: str = Form(...)):
    """Select a database for the current session"""
    try:
        # Validate the database exists
        databases = discover_existing_databases()
        selected_db = next((db for db in databases if db['path'] == database_path), None)
        
        if not selected_db:
            raise HTTPException(status_code=404, detail="Database not found")
        
        # Store in session
        request.session['current_database'] = selected_db
        
        # TODO: Update your DatabaseManager here when you implement it
        # db_manager.set_dataset(database_path)
        
        return {"success": True, "database": selected_db}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/databases/create")
async def create_database(
    name: str = Form(...),
    description: str = Form(""),
    score_files: List[UploadFile] = File(...)
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
    # Since we're doing synchronous creation for now, just return completed
    # Later you can implement actual async task tracking
    return {
        "status": "completed",
        "progress": 1.0,
        "message": "Database created successfully",
        "database_name": "New Database",
        "database_path": "db/new_database"
    }