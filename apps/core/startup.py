# apps/core/startup.py
from fastapi import Request, HTTPException
from database import get_database_manager  # Updated import
import os

async def recover_abandoned_tasks():
    """Mark abandoned processing/queued tasks as failed"""
    try:
        # Get the database manager
        db_manager = get_database_manager()
        
        # If we have an active database, recover its tasks
        if db_manager.has_active_database:  # Changed from has_active_database()
            abandoned_count = db_manager.active_db.tasks.recover_abandoned_tasks()
            if abandoned_count > 0:
                print(f"Marked {abandoned_count} abandoned tasks as failed during startup")
        else:
            print("No database selected during startup - skipping task recovery")
        
    except Exception as e:
        print(f"Error during startup recovery: {str(e)}")

async def initialize_default_database():
    """Try to initialize a default database if available"""
    try:
        print("Step 1: Importing discover_existing_databases...")
        from database.connection import discover_existing_databases
        
        print("Step 2: Getting database manager...")
        db_manager = get_database_manager()
        
        print("Step 3: Checking if database is active...")
        print(f"has_active_database type: {type(db_manager.has_active_database)}")
        
        # If no database is currently selected, try to find and select one
        if not db_manager.has_active_database:
            print("Step 4: No active database, discovering databases...")
            databases = discover_existing_databases()
            
            if databases:
                # Select the first available database as default
                default_db = databases[0]
                print(f"Step 5: Auto-selecting default database: {default_db['name']}")
                db_manager.set_dataset(default_db['path'])
                
                print("Step 6: Recovering tasks...")
                # Now recover tasks for this database
                await recover_abandoned_tasks()
            else:
                print("No databases found - application will require manual database selection")
        else:
            print("Database already selected, recovering tasks...")
            await recover_abandoned_tasks()
            
    except Exception as e:
        import traceback
        print(f"Error initializing default database: {str(e)}")
        print("Full traceback:")
        traceback.print_exc()

def register_startup_events(app):
    """Register all startup events with the FastAPI app"""
    @app.on_event("startup")
    async def startup_event():
        print("Starting application initialization...")
        
        # Initialize database and recover tasks
        await initialize_default_database()
        
        print("Application startup complete")

# Database session management functions (for middleware/dependencies)
async def restore_database_selection(request: Request):
    """Function to call in endpoints that need database access"""
    db_manager = get_database_manager()
    
    if hasattr(request, 'session'):
        stored_path = request.session.get('current_database_path')
        if stored_path and os.path.exists(stored_path):
            try:
                current_info = db_manager.get_current_dataset_info()
                if not current_info or current_info['path'] != stored_path:
                    db_manager.set_dataset(stored_path)
            except Exception as e:
                print(f"Error restoring database session: {e}")

async def ensure_database_selected(request: Request):
    """FastAPI dependency to ensure database is selected"""
    await restore_database_selection(request)
    db_manager = get_database_manager()
    
    if not db_manager.has_active_database:  # Changed from has_active_database()
        raise HTTPException(
            status_code=400, 
            detail="No database selected. Please select a database first."
        )

