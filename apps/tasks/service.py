import os
import uuid
from typing import Optional
from datetime import datetime
from fastapi import BackgroundTasks, Request
from database import db
from apps.core.models import TaskResponse
from apps.session.service import SessionManager

# When running with a dedicated worker pod, set DISABLE_INLINE_TASKS=true
# so the web server only queues tasks and the worker executes them.
DISABLE_INLINE_TASKS = os.environ.get("DISABLE_INLINE_TASKS", "false").lower() == "true"

def process_background_task(task_id: str, request_data: dict, processing_function):
    """
    Process a background task and update its status.
    
    Parameters:
    -----------
    task_id : str
        Unique task identifier
    request_data : dict
        Request data for processing
    processing_function : callable
        Function that performs the actual processing
    """
    try:
        # Update status to "processing"
        db.active_db.tasks.update_task_status(task_id, "processing")
        
        # Call the actual processing function
        result_path = processing_function(request_data)
        
        # Update task with success status and result path
        db.active_db.tasks.update_task_status(
            task_id=task_id,
            status="completed",
            result_path=result_path
        )
        
    except Exception as e:
        # Update task with error status
        db.active_db.tasks.update_task_status(
            task_id=task_id,
            status="failed",
            error=str(e)
        )

async def process_image_request(
    request: Request,  # Add request parameter
    request_data: dict,
    task_type: str,
    task_name: Optional[str],
    processing_function,
    background_tasks: BackgroundTasks
) -> TaskResponse:
    """
    Generic function to handle image generation requests.
    
    Parameters:
    -----------
    request : Request
        FastAPI request object (needed for session)
    request_data : dict
        Dictionary containing the request parameters
    task_type : str
        Type of task (heatmap, clustering, etc.)
    task_name : str, optional
        User-provided name for the task
    processing_function : callable
        The function that will generate the image
    background_tasks : BackgroundTasks
        FastAPI BackgroundTasks object
    
    Returns:
    --------
    TaskResponse
        Object with task_id and status
    """
    # Get the user's session ID
    user_id = SessionManager.get_or_create_user_id(request)
    
    # Generate a unique task ID
    task_id = str(uuid.uuid4())
    created_at = datetime.now().isoformat()
    
    print(f"submitting image task {task_id} => {request_data}")

    # Store task in database with user_id
    db.active_db.tasks.create_task(
        task_id=task_id,
        task_type=task_type,
        name=task_name or f"{task_type} task",
        request_data=request_data,
        user_id=user_id  # Associate task with user
    )
    
    # Track this activity in the user's session
    SessionManager.track_user_activity(
        request,
        f"create_{task_type}_task",
        {
            "task_id": task_id,
            "task_name": task_name or f"{task_type} task",
            "task_type": task_type
        }
    )
    
    # Add task to background tasks (skipped when a dedicated worker pod is running)
    if not DISABLE_INLINE_TASKS:
        background_tasks.add_task(
            process_background_task,
            task_id,
            request_data,
            processing_function
        )
    
    # Return task ID and initial status to client
    return TaskResponse(
        task_id=task_id,
        task_type=task_type,
        name=task_name,
        status="queued",
        created_at=created_at
    )