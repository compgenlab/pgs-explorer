import json
from datetime import datetime
from typing import Optional, Dict, Any
from ..base_repository import BaseRepository

class SessionRepository(BaseRepository):
    def create_session(self, session_id: str, user_id: str, session_data: Dict[str, Any]) -> None:
        """Create a new session record."""
        query = """
            INSERT INTO user_sessions (session_id, user_id, created_at, last_activity, session_data)
            VALUES (?, ?, datetime('now'), datetime('now'), ?)
        """
        with self.connection.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, [session_id, user_id, json.dumps(session_data)])
            conn.commit()
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session by ID."""
        query = "SELECT * FROM user_sessions WHERE session_id = ?"
        row = self.execute_query_single(query, [session_id])
        if row:
            data = dict(row)
            data['session_data'] = json.loads(data['session_data'])
            return data
        return None
    
    def update_session(self, session_id: str, session_data: Dict[str, Any]) -> None:
        """Update session data."""
        query = """
            UPDATE user_sessions 
            SET session_data = ?, last_activity = datetime('now')
            WHERE session_id = ?
        """
        with self.connection.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, [json.dumps(session_data), session_id])
            conn.commit()
    def update_last_activity(self, session_id: str) -> None:
        """Update the last_activity timestamp for a session."""
        query = """
            UPDATE user_sessions 
            SET last_activity = datetime('now')
            WHERE session_id = ?
        """
        with self.connection.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, [session_id])
            conn.commit()
            
    def delete_session(self, session_id: str) -> None:
        """Delete a session."""
        query = "DELETE FROM user_sessions WHERE session_id = ?"
        with self.connection.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, [session_id])
            conn.commit()