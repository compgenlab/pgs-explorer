import os
import secrets
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import Request, Response, HTTPException
from starlette.middleware.sessions import SessionMiddleware
from database import db
import json
from typing import Dict, Any, List
from apps.core.config import SESSION_SECRET_KEY, SESSION_COOKIE_NAME, SESSION_MAX_AGE

class SessionManager:
    """Manages user sessions for the application using database storage."""
    
    @staticmethod
    def _get_session_id_from_request(request: Request) -> Optional[str]:
        return request.session["session_id"]

    #     """Get session ID from cookie."""
    #     return request.cookies.get(SESSION_COOKIE_NAME)
    
    @staticmethod
    def _get_or_create_session(request: Request) -> Dict[str, Any]:
        """Get existing session or create new one."""
        session_id = SessionManager._get_session_id_from_request(request)

        # print(f"Current session: {session_id}")
        if session_id:
            session = db.active_db.sessions.get_session(session_id)
            if session:
                # Update last_activity whenever session is accessed
                # print("Session found!")
                db.active_db.sessions.update_last_activity(session_id)
                return session
            # print("Session not found")
        
        # Create new session
        if not session_id:
            session_id = secrets.token_urlsafe(32)
            print(f"New session: {session_id}")
        user_id = secrets.token_urlsafe(16)
        # print(f"Created new user_id2: {user_id}")
        session_data = {
            "created_at": datetime.now().isoformat(),
            "preferences": {},
            "recent_activities": []
        }
        
        db.active_db.sessions.create_session(session_id, user_id, session_data)
        
        return {
            "session_id": session_id,
            "user_id": user_id,
            "session_data": session_data
        }
    
    @staticmethod
    def _update_session(session_id: str, session_data: Dict[str, Any]) -> None:
        """Update session in database."""
        db.active_db.sessions.update_session(session_id, session_data)
    
    @staticmethod
    def get_session_data(request: Request) -> Dict[str, Any]:
        """Get session data from the database."""
        session = SessionManager._get_or_create_session(request)
        return session["session_data"]
    
    @staticmethod
    def set_session_data(request: Request, key: str, value: Any) -> None:
        """Set a value in the session."""
        session = SessionManager._get_or_create_session(request)
        session_data = session["session_data"]
        session_data[key] = value
        SessionManager._update_session(session["session_id"], session_data)
    
    @staticmethod
    def get_session_value(request: Request, key: str, default: Any = None) -> Any:
        """Get a specific value from the session."""
        session_data = SessionManager.get_session_data(request)
        return session_data.get(key, default)
    
    @staticmethod
    def delete_session_value(request: Request, key: str) -> None:
        """Delete a value from the session."""
        session = SessionManager._get_or_create_session(request)
        session_data = session["session_data"]
        if key in session_data:
            del session_data[key]
            SessionManager._update_session(session["session_id"], session_data)
    
    @staticmethod
    def clear_session(request: Request) -> None:
        """Clear all session data."""
        session_id = SessionManager._get_session_id_from_request(request)
        if session_id:
            db.active_db.sessions.delete_session(session_id)
    
    @staticmethod
    def get_or_create_user_id(request: Request) -> str:
        """Get user ID, using session cookie as the key to database lookup."""
        
        # Use request.session to get/set a simple session_id
        session_id = request.session.get("session_id")
        # print(f"get_or_create_user_id => {session_id}")
        
        if not session_id:
            # Create new session_id in cookie
            session_id = secrets.token_urlsafe(32)
            request.session["session_id"] = session_id
            print(f"get_or_create_user_id - creating new sessionid {session_id}")
        
        # Look up actual data in database using this session_id
        session_record = db.active_db.sessions.get_session(session_id)
        # print(f"get_or_create_user_id - record {session_record}")
        
        if not session_record:
            # Create new database record
            user_id = secrets.token_urlsafe(16)
            # print(f"Created new user_id1: {user_id}")
            session_data = {
                "created_at": datetime.now().isoformat(),
                "preferences": {},
                "recent_activities": []
            }
            db.active_db.sessions.create_session(session_id, user_id, session_data)
            return user_id
        
        return session_record["user_id"]

    
    @staticmethod
    def get_session_id(request: Request) -> str:
        """Get the session ID, creating session if needed."""
        session = SessionManager._get_or_create_session(request)
        return session["session_id"]
    
    @staticmethod
    def save_user_preferences(request: Request, preferences: Dict[str, Any]) -> None:
        """Save user preferences to session."""
        session = SessionManager._get_or_create_session(request)
        session_data = session["session_data"]
        current_prefs = session_data.get("preferences", {})
        current_prefs.update(preferences)
        session_data["preferences"] = current_prefs
        SessionManager._update_session(session["session_id"], session_data)
    
    @staticmethod
    def get_user_preferences(request: Request) -> Dict[str, Any]:
        """Get user preferences from session."""
        session_data = SessionManager.get_session_data(request)
        return session_data.get("preferences", {})
    
    @staticmethod
    def track_user_activity(request: Request, activity_type: str, details: Dict[str, Any]) -> None:
        """Track user activity in session."""
        session = SessionManager._get_or_create_session(request)
        session_data = session["session_data"]
        
        # Get or create activity list
        activities = session_data.get("recent_activities", [])
        
        # Add new activity
        activity = {
            "type": activity_type,
            "timestamp": datetime.now().isoformat(),
            "details": details
        }
        activities.append(activity)
        
        # Keep only last 50 activities
        activities = activities[-50:]
        
        session_data["recent_activities"] = activities
        session_data["last_activity"] = datetime.now().isoformat()
        
        SessionManager._update_session(session["session_id"], session_data)

def add_session_middleware(app):
    """
    Add session middleware to the FastAPI app.
    
    Parameters:
    -----------
    app : FastAPI
        The FastAPI application instance
    """
    app.add_middleware(
        SessionMiddleware,
        secret_key=SESSION_SECRET_KEY,
        session_cookie=SESSION_COOKIE_NAME,
        max_age=SESSION_MAX_AGE,
        same_site="lax",
        https_only=False  
    )