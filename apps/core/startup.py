import sqlite3
from datetime import datetime
from apps.core.database import TASK_DB_PATH

async def recover_abandoned_tasks():
    """Mark abandoned processing/queued tasks as failed"""
    try:
        conn = sqlite3.connect(TASK_DB_PATH)
        cursor = conn.cursor()
        
        # Find all tasks in processing or queued state
        cursor.execute(
            "SELECT task_id FROM image_tasks WHERE status IN ('processing', 'queued')"
        )
        abandoned_tasks = cursor.fetchall()
        
        if abandoned_tasks:
            # Mark them as failed
            for task in abandoned_tasks:
                task_id = task[0]
                cursor.execute(
                    "UPDATE image_tasks SET status = ?, error = ?, completed_at = ? WHERE task_id = ?",
                    ("failed", "Task abandoned due to server restart", datetime.now().isoformat(), task_id)
                )
            
            conn.commit()
            print(f"Marked {len(abandoned_tasks)} abandoned tasks as failed during startup")
        
        conn.close()
    except Exception as e:
        print(f"Error during startup recovery: {str(e)}")

def register_startup_events(app):
    """Register all startup events with the FastAPI app"""
    @app.on_event("startup")
    async def startup_event():
        from apps.core.database import init_task_db
        
        # Initialize database
        init_task_db()
        
        # Recover abandoned tasks
        await recover_abandoned_tasks()