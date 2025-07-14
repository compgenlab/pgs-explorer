from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse
from typing import Optional
from apps.core.config import templates
from apps.session.service import SessionManager
from database import db

router = APIRouter(tags=["tasks"])

@router.get("/tasks", response_class=HTMLResponse)
async def tasks_page(request: Request):
    return templates.TemplateResponse("tasks.html", {"request": request})

@router.get("/api/task_status/{task_id}")
async def get_task_status(request: Request, task_id: str):
    """Get the status of a specific task (only if it belongs to this user)."""
    # Get the user's session ID
    user_id = SessionManager.get_or_create_user_id(request)
    
    task = db.active_db.tasks.get_task(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Check if this task belongs to the current user
    if task.get("user_id") != user_id:
        raise HTTPException(status_code=404, detail="Task not found")  
    
    return {
        "task_id": task["task_id"],
        "task_type": task["task_type"],
        "name": task["name"],
        "status": task["status"],
        "created_at": task["created_at"],
        "completed_at": task["completed_at"],
        "result_path": task["result_path"] if task["status"] == "completed" else None,
        "error": task["error"] if task["status"] == "failed" else None
    }

@router.get("/api/list_tasks")
async def list_tasks(
    request: Request,
    task_type: Optional[str] = None, 
    limit: int = 20, 
    offset: int = 0
):
    """List tasks for the current user only."""
    # Get the user's session ID
    user_id = SessionManager.get_or_create_user_id(request)
    
    if task_type:
        # Get tasks by type AND user with pagination
        tasks = db.active_db.tasks.get_user_tasks_by_type_paginated(user_id, task_type, limit, offset)
    else:
        # Get all tasks for this user with pagination
        tasks = db.active_db.tasks.get_user_tasks_paginated(user_id, limit, offset)
    
    # Format response
    return [
        {
            "task_id": task["task_id"],
            "task_type": task["task_type"],
            "name": task["name"],
            "status": task["status"],
            "created_at": task["created_at"],
            "completed_at": task["completed_at"]
        }
        for task in tasks
    ]