from database import db

async def recover_abandoned_tasks():
    """Mark abandoned processing/queued tasks as failed"""
    try:
        # Use the new bulk recovery method
        abandoned_count = db.tasks.recover_abandoned_tasks()
        
        if abandoned_count > 0:
            print(f"Marked {abandoned_count} abandoned tasks as failed during startup")
        
    except Exception as e:
        print(f"Error during startup recovery: {str(e)}")

def register_startup_events(app):
    """Register all startup events with the FastAPI app"""
    @app.on_event("startup")
    async def startup_event():
        # Recover abandoned tasks
        await recover_abandoned_tasks()
        
        print("Application startup complete")