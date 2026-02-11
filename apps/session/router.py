from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from typing import Dict, Any
from .service import SessionManager, SESSION_COOKIE_NAME, SESSION_MAX_AGE
from database import db

router = APIRouter(prefix="/api/session", tags=["session"])

@router.get("/info")
async def get_session_info(request: Request, response: Response) -> Dict[str, Any]:
    """Get current session information."""
    user_id = SessionManager.get_or_create_user_id(request)
    session_id = SessionManager.get_session_id(request)
    session_data = SessionManager.get_session_data(request)
    
    # # Set session cookie if not present
    # if not request.cookies.get(SESSION_COOKIE_NAME):
    #     print("creating new cookie???")
    #     response.set_cookie(
    #         key=SESSION_COOKIE_NAME,
    #         value=session_id,
    #         max_age=SESSION_MAX_AGE,
    #         httponly=False,
    #         samesite="lax",
    #         secure=False  # Set to True in production with HTTPS
    #     )
    
    return JSONResponse(
        {
            "user_id": user_id,
            "session_id": session_id,
            "created_at": session_data.get("created_at"),
            "last_activity": session_data.get("last_activity"),
            "preferences": SessionManager.get_user_preferences(request)
        },
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"}
    )

@router.post("/preferences")
async def update_preferences(request: Request, preferences: Dict[str, Any]) -> Dict[str, Any]:
    """Update user preferences."""
    SessionManager.save_user_preferences(request, preferences)
    return {"status": "success", "preferences": SessionManager.get_user_preferences(request)}

@router.get("/recent-activities")
async def get_recent_activities(request: Request) -> Dict[str, Any]:
    """Get recent user activities."""
    activities = SessionManager.get_session_value(request, "recent_activities", [])
    return {"activities": activities}

@router.post("/clear")
async def clear_session(request: Request, response: Response) -> Dict[str, Any]:
    """Clear the current session."""
    old_user_id = SessionManager.get_or_create_user_id(request)
    SessionManager.clear_session(request)
    new_user_id = SessionManager.get_or_create_user_id(request)
    new_session_id = SessionManager.get_session_id(request)

    return JSONResponse({
        "status": "success",
        "message": "Session cleared and reset",
        "old_user_id": old_user_id,
        "new_user_id": new_user_id,
        "new_session_id": new_session_id
    })

    # return {"status": "success", "message": "Session cleared"}

@router.get("/debug")
async def debug_session(request: Request):
    user_id = SessionManager.get_or_create_user_id(request)
    session_id = request.cookies.get("pgs_explorer_session")
    
    return {
        "user_id": user_id,
        "session_cookie": session_id,
        "cookies": dict(request.cookies)
    }

@router.post("/clear-all")
async def clear_all_session_data(request: Request, response: Response) -> Dict[str, Any]:
    """Clear all session data including cohorts and tasks."""
    old_user_id = SessionManager.get_or_create_user_id(request)

    # Delete user's tasks
    deleted_tasks = db.active_db.tasks.delete_user_tasks(old_user_id)
    
    # Delete user's custom cohorts  
    deleted_cohorts = db.active_db.cohorts.delete_user_cohorts(old_user_id)
    
    # Clear session
    SessionManager.clear_session(request)
    new_user_id = SessionManager.get_or_create_user_id(request)
    new_session_id = SessionManager.get_session_id(request)

    resp = JSONResponse({
        "status": "success", 
        "message": f"Session cleared: {deleted_tasks} tasks and {deleted_cohorts} cohorts deleted",
        "old_user_id": old_user_id,
        "new_user_id": new_user_id,
        "new_session_id": new_session_id
    })

    return resp

    # return {
    #     "status": "success", 
    #     "message": f"Session cleared: {deleted_tasks} tasks and {deleted_cohorts} cohorts deleted"
    # }
