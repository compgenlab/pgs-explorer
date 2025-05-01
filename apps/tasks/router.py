from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from typing import Optional
import sqlite3
from apps.core.app_config import templates
from apps.core.database import TASK_DB_PATH

router = APIRouter(tags=["tasks"])

@router.get("/tasks", response_class=HTMLResponse)
async def tasks_page(request: Request):
    return templates.TemplateResponse("tasks.html", {"request": request})

@router.get("/api/task_status/{task_id}")
async def get_task_status(task_id: str):
    conn = sqlite3.connect(TASK_DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM image_tasks WHERE task_id = ?", (task_id,))
    task = cursor.fetchone()
    conn.close()
    
    if not task:
        return {"error": "Task not found"}
    
    # Convert DB row to dictionary
    columns = ["task_id", "task_type", "name", "status", "created_at", 
               "completed_at", "result_path", "error", "request_data"]
    task_dict = {columns[i]: task[i] for i in range(len(columns))}
    
    return {
        "task_id": task_dict["task_id"],
        "task_type": task_dict["task_type"],
        "name": task_dict["name"],
        "status": task_dict["status"],
        "created_at": task_dict["created_at"],
        "completed_at": task_dict["completed_at"],
        "result_path": task_dict["result_path"] if task_dict["status"] == "completed" else None,
        "error": task_dict["error"] if task_dict["status"] == "failed" else None
    }

@router.get("/api/list_tasks")
async def list_tasks(task_type: Optional[str] = None, limit: int = 20, offset: int = 0):
    conn = sqlite3.connect(TASK_DB_PATH)
    cursor = conn.cursor()
    
    if task_type:
        cursor.execute(
            "SELECT task_id, task_type, name, status, created_at, completed_at FROM image_tasks WHERE task_type = ? ORDER BY created_at DESC LIMIT ? OFFSET ?", 
            (task_type, limit, offset)
        )
    else:
        cursor.execute(
            "SELECT task_id, task_type, name, status, created_at, completed_at FROM image_tasks ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
        )
    
    tasks = cursor.fetchall()
    conn.close()
    
    return [
        {
            "task_id": task[0],
            "task_type": task[1],
            "name": task[2],
            "status": task[3],
            "created_at": task[4],
            "completed_at": task[5]
        }
        for task in tasks
    ]

