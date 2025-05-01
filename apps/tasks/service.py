import uuid
import json
import sqlite3
from typing import Optional
from datetime import datetime
from fastapi import BackgroundTasks
from apps.core.database import TASK_DB_PATH
from apps.core.models import TaskResponse

def process_background_task(task_id, request_data, processing_function):
    try:
        # Update status to "processing"
        update_task_status(task_id, "processing")
        
        # Call the actual processing function
        result_path = processing_function(request_data)
        
        # Update task with success status and result path
        update_task_status(
            task_id, 
            "completed",
            result_path=result_path,
            completed_at=datetime.now().isoformat()
        )
        
    except Exception as e:
        # Update task with error status
        update_task_status(
            task_id,
            "failed",
            error=str(e),
            completed_at=datetime.now().isoformat()
        )

async def process_image_request(
    request_data: dict,
    task_type: str,
    task_name: Optional[str],
    processing_function,
    background_tasks: BackgroundTasks
):
    """
    Generic function to handle image generation requests
    
    Args:
        request_data: Dict containing the request parameters
        task_type: Type of task (heatmap, clustering, etc.)
        task_name: Optional user-provided name
        processing_function: The function that will generate the image
        background_tasks: FastAPI BackgroundTasks object
    
    Returns:
        TaskResponse object with task_id and status
    """
    # Generate a unique task ID
    task_id = str(uuid.uuid4())
    created_at = datetime.now().isoformat()
    
    # Store task in database
    conn = sqlite3.connect(TASK_DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        "INSERT INTO image_tasks (task_id, task_type, name, status, created_at, request_data) VALUES (?, ?, ?, ?, ?, ?)",
        (task_id, task_type, task_name, "queued", created_at, json.dumps(request_data))
    )
    
    conn.commit()
    conn.close()
    
    # Add task to background tasks - pass the processing function as an argument
    background_tasks.add_task(process_background_task, task_id, request_data, processing_function)
    
    # Return task ID and initial status to client
    return TaskResponse(
        task_id=task_id,
        task_type=task_type,
        name=task_name,
        status="queued",
        created_at=created_at
    )

# Function to update task status in the database
def update_task_status(task_id, status, **kwargs):
    conn = sqlite3.connect(TASK_DB_PATH)
    cursor = conn.cursor()
    
    set_clause = f"status = ?"
    params = [status]
    
    for key, value in kwargs.items():
        set_clause += f", {key} = ?"
        params.append(value)
    
    params.append(task_id)
    
    cursor.execute(f"UPDATE image_tasks SET {set_clause} WHERE task_id = ?", params)
    conn.commit()
    conn.close()

