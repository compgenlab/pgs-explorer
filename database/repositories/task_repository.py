import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from ..base_repository import BaseRepository

class TaskRepository(BaseRepository):
    def create_task(self, task_id: str, task_type: str, name: str, request_data: Dict[str, Any]) -> None:
        """
        Create a new task record.
        
        Parameters:
        -----------
        task_id : str
            Unique task identifier
        task_type : str
            Type of task (e.g., 'heatmap', 'pca', etc.)
        name : str
            Human-readable task name
        request_data : dict
            Request data as dictionary (will be JSON serialized)
        """
        query = """
            INSERT INTO image_tasks 
            (task_id, task_type, name, status, created_at, request_data)
            VALUES (?, ?, ?, 'pending', datetime('now'), ?)
        """
        params = [
            task_id,
            task_type,
            name,
            json.dumps(request_data)  # Serialize to JSON
        ]
        
        with self.connection.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
    
    def update_task_status(self, task_id: str, status: str, 
                          result_path: Optional[str] = None, 
                          error: Optional[str] = None) -> None:
        """
        Update task status.
        
        Parameters:
        -----------
        task_id : str
            Task identifier
        status : str
            New status ('pending', 'running', 'completed', 'failed')
        result_path : str, optional
            Path to result file (for completed tasks)
        error : str, optional
            Error message (for failed tasks)
        """
        if status == 'completed':
            query = """
                UPDATE image_tasks 
                SET status = ?, completed_at = datetime('now'), result_path = ?
                WHERE task_id = ?
            """
            params = [status, result_path, task_id]
        elif status == 'failed':
            query = """
                UPDATE image_tasks 
                SET status = ?, completed_at = datetime('now'), error = ?
                WHERE task_id = ?
            """
            params = [status, error, task_id]
        else:
            query = """
                UPDATE image_tasks 
                SET status = ?
                WHERE task_id = ?
            """
            params = [status, task_id]
        
        with self.connection.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
    
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get task by ID.
        
        Parameters:
        -----------
        task_id : str
            Task identifier
            
        Returns:
        --------
        dict or None
            Task data or None if not found
        """
        query = "SELECT * FROM image_tasks WHERE task_id = ?"
        row = self.execute_query_single(query, [task_id])
        
        if row:
            return self._format_task_row(row)
        return None
    
    def get_tasks_by_status(self, status: str) -> List[Dict[str, Any]]:
        """
        Get all tasks with a specific status.
        
        Parameters:
        -----------
        status : str
            Task status to filter by
            
        Returns:
        --------
        list
            List of task dictionaries
        """
        query = "SELECT * FROM image_tasks WHERE status = ? ORDER BY created_at DESC"
        rows = self.execute_query(query, [status])
        
        return [self._format_task_row(row) for row in rows]
    
    def get_recent_tasks(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent tasks.
        
        Parameters:
        -----------
        limit : int
            Maximum number of tasks to return
            
        Returns:
        --------
        list
            List of task dictionaries
        """
        query = """
            SELECT * FROM image_tasks 
            ORDER BY created_at DESC 
            LIMIT ?
        """
        rows = self.execute_query(query, [limit])
        
        return [self._format_task_row(row) for row in rows]
    
    def cleanup_old_tasks(self, days_to_keep: int = 7) -> int:
        """
        Remove tasks older than specified days.
        
        Parameters:
        -----------
        days_to_keep : int
            Number of days to keep tasks
            
        Returns:
        --------
        int
            Number of tasks deleted
        """
        query = """
            DELETE FROM image_tasks 
            WHERE created_at < datetime('now', '-' || ? || ' days')
        """
        
        with self.connection.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, [days_to_keep])
            deleted_count = cursor.rowcount
            conn.commit()
            
        return deleted_count
    
    def _format_task_row(self, row: Any) -> Dict[str, Any]:
        """
        Format a task row into a dictionary.
        
        Parameters:
        -----------
        row : sqlite3.Row
            Database row
            
        Returns:
        --------
        dict
            Formatted task data
        """
        task_dict = dict(row)
        
        # Parse request_data from JSON
        if task_dict.get('request_data'):
            try:
                task_dict['request_data'] = json.loads(task_dict['request_data'])
            except json.JSONDecodeError:
                task_dict['request_data'] = {}
        
        return task_dict

    def recover_abandoned_tasks(self) -> int:
        """
        Mark abandoned processing/queued tasks as failed.
        This is typically called during application startup.
        
        Returns:
        --------
        int
            Number of tasks marked as failed
        """
        query = """
            UPDATE image_tasks 
            SET status = 'failed', 
                error = 'Task abandoned due to server restart', 
                completed_at = datetime('now')
            WHERE status IN ('processing', 'queued')
        """
        
        with self.connection.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            affected_rows = cursor.rowcount
            conn.commit()
            
        return affected_rows

    def get_tasks_by_multiple_statuses(self, statuses: List[str]) -> List[Dict[str, Any]]:
        """
        Get all tasks with any of the specified statuses.
        
        Parameters:
        -----------
        statuses : list
            List of statuses to filter by
            
        Returns:
        --------
        list
            List of task dictionaries
        """
        if not statuses:
            return []
        
        placeholders = ','.join(['?'] * len(statuses))
        query = f"""
            SELECT * FROM image_tasks 
            WHERE status IN ({placeholders})
            ORDER BY created_at DESC
        """
        rows = self.execute_query(query, statuses)
        
        return [self._format_task_row(row) for row in rows]

    def update_task_status_bulk(self, task_ids: List[str], status: str, 
                            error: Optional[str] = None) -> int:
        """
        Update status for multiple tasks at once.
        
        Parameters:
        -----------
        task_ids : list
            List of task IDs to update
        status : str
            New status
        error : str, optional
            Error message (for failed tasks)
            
        Returns:
        --------
        int
            Number of tasks updated
        """
        if not task_ids:
            return 0
        
        placeholders = ','.join(['?'] * len(task_ids))
        
        if status == 'failed' and error:
            query = f"""
                UPDATE image_tasks 
                SET status = ?, error = ?, completed_at = datetime('now')
                WHERE task_id IN ({placeholders})
            """
            params = [status, error] + task_ids
        else:
            query = f"""
                UPDATE image_tasks 
                SET status = ?
                WHERE task_id IN ({placeholders})
            """
            params = [status] + task_ids
        
        with self.connection.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            affected_rows = cursor.rowcount
            conn.commit()
            
        return affected_rows

    def get_tasks_paginated(self, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Get tasks with pagination.
        
        Parameters:
        -----------
        limit : int
            Maximum number of tasks to return
        offset : int
            Number of tasks to skip
            
        Returns:
        --------
        list
            List of task dictionaries
        """
        query = """
            SELECT * FROM image_tasks 
            ORDER BY created_at DESC 
            LIMIT ? OFFSET ?
        """
        rows = self.execute_query(query, [limit, offset])
        
        return [self._format_task_row(row) for row in rows]

    def get_tasks_by_type_paginated(self, task_type: str, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Get tasks of a specific type with pagination.
        
        Parameters:
        -----------
        task_type : str
            Type of tasks to retrieve
        limit : int
            Maximum number of tasks to return
        offset : int
            Number of tasks to skip
            
        Returns:
        --------
        list
            List of task dictionaries
        """
        query = """
            SELECT * FROM image_tasks 
            WHERE task_type = ?
            ORDER BY created_at DESC 
            LIMIT ? OFFSET ?
        """
        rows = self.execute_query(query, [task_type, limit, offset])
        
        return [self._format_task_row(row) for row in rows]

    def count_tasks(self, task_type: Optional[str] = None) -> int:
        """
        Count total number of tasks.
        
        Parameters:
        -----------
        task_type : str, optional
            If provided, count only tasks of this type
            
        Returns:
        --------
        int
            Total count of tasks
        """
        if task_type:
            query = "SELECT COUNT(*) FROM image_tasks WHERE task_type = ?"
            params = [task_type]
        else:
            query = "SELECT COUNT(*) FROM image_tasks"
            params = []
        
        return self.execute_query_scalar(query, params) or 0

    def get_task_types(self) -> List[str]:
        """
        Get all unique task types.
        
        Returns:
        --------
        list
            List of task types
        """
        query = "SELECT DISTINCT task_type FROM image_tasks ORDER BY task_type"
        rows = self.execute_query(query)
        
        return [row[0] for row in rows]