import json
from typing import List, Dict, Any, Optional
from ..base_repository import BaseRepository

class CohortRepository(BaseRepository):
    def create_cohort(self, cohort_id: str, user_id: str, cohort_name: str, sample_ids: List[str]) -> None:
        """Create a new user cohort."""
        query = """
            INSERT INTO user_cohorts (cohort_id, user_id, cohort_name, sample_ids, created_at)
            VALUES (?, ?, ?, ?, datetime('now'))
        """
        with self.connection.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, [cohort_id, user_id, cohort_name, json.dumps(sample_ids)])
            conn.commit()
    
    def get_user_cohorts(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all cohorts for a user."""
        query = """
            SELECT cohort_id, cohort_name, sample_ids, created_at 
            FROM user_cohorts 
            WHERE user_id = ? 
            ORDER BY created_at DESC
        """
        rows = self.execute_query(query, [user_id])
        
        return [
            {
                "cohort_id": row[0],
                "cohort_name": row[1], 
                "sample_ids": json.loads(row[2]),
                "created_at": row[3]
            }
            for row in rows
        ]
    
    def get_cohort(self, cohort_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Get specific cohort for user."""
        query = """
            SELECT cohort_id, cohort_name, sample_ids, created_at
            FROM user_cohorts 
            WHERE cohort_id = ? AND user_id = ?
        """
        row = self.execute_query_single(query, [cohort_id, user_id])
        
        if row:
            return {
                "cohort_id": row[0],
                "cohort_name": row[1],
                "sample_ids": json.loads(row[2]),
                "created_at": row[3]
            }
        return None
    
    def delete_cohort(self, cohort_id: str, user_id: str) -> bool:
        """Delete a cohort."""
        query = "DELETE FROM user_cohorts WHERE cohort_id = ? AND user_id = ?"
        with self.connection.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, [cohort_id, user_id])
            deleted = cursor.rowcount > 0
            conn.commit()
            return deleted

    def delete_user_cohorts(self, user_id: str) -> int:
        """Delete all cohorts for a user."""
        query = "DELETE FROM user_cohorts WHERE user_id = ?"
        with self.connection.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, [user_id])
            deleted_count = cursor.rowcount
            conn.commit()
            return deleted_count