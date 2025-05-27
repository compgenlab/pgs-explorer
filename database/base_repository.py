# database/base_repository.py
class BaseRepository:
    def __init__(self, connection):
        """
        Initialize with a DatabaseConnection instance
        
        Parameters:
        -----------
        connection : DatabaseConnection
            Database connection manager
        """
        self.connection = connection
    
    def execute_query(self, query, params=None):
        """
        Execute a query and return all results
        
        Parameters:
        -----------
        query : str
            SQL query to execute
        params : tuple or list, optional
            Query parameters
            
        Returns:
        --------
        list
            List of sqlite3.Row objects
        """
        with self.connection.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params or [])
            return cursor.fetchall()
    
    def execute_query_single(self, query, params=None):
        """
        Execute a query and return the first result
        
        Parameters:
        -----------
        query : str
            SQL query to execute
        params : tuple or list, optional
            Query parameters
            
        Returns:
        --------
        sqlite3.Row or None
            First row of results or None if no results
        """
        with self.connection.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params or [])
            return cursor.fetchone()
    
    def execute_query_scalar(self, query, params=None):
        """
        Execute a query and return a single scalar value
        
        Parameters:
        -----------
        query : str
            SQL query to execute
        params : tuple or list, optional
            Query parameters
            
        Returns:
        --------
        Any
            First column of first row or None if no results
        """
        result = self.execute_query_single(query, params)
        return result[0] if result else None
