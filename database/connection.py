import sqlite3
import os
import gzip
import pandas as pd
from contextlib import contextmanager
from typing import List, Optional
import tempfile
import shutil

class DatabaseConnection:
    def __init__(self, db_path, is_task_db=False):
        self.db_path = db_path
        self.is_task_db = is_task_db
        
        # Only initialize if database doesn't exist
        if not os.path.exists(db_path):
            if is_task_db:
                self._init_task_db()
            else:
                self._create_empty_tables()
    
    def _init_task_db(self):
        """Initialize task database if it doesn't exist"""
        # Ensure the directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create tasks table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS image_tasks (
            task_id TEXT PRIMARY KEY,
            task_type TEXT,
            name TEXT,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            completed_at TEXT,
            result_path TEXT,
            error TEXT,
            request_data TEXT NOT NULL
        )
        ''')
        
        conn.commit()
        conn.close()

    def _create_empty_tables(self):
        """Create empty database tables"""
        # Ensure the directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create pgs_metadata table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pgs_metadata (
                PGS_ID TEXT PRIMARY KEY,
                PGS_Name TEXT,
                Reported_Trait TEXT,
                Mapped_Trait_Label TEXT,
                Mapped_Trait_ID TEXT,
                PGS_Development_Method TEXT,
                PGS_Development_Details TEXT,
                Original_Genome_Build TEXT,
                Number_of_Variants INTEGER,
                Number_of_Interaction_Terms INTEGER,
                Type_of_Variant_Weight TEXT,
                PGS_Publication_ID TEXT,
                Publication_PMID INTEGER,
                Publication_DOI TEXT,
                Score_Matches_Publication BOOLEAN,
                Ancestry_Distribution_Variant_Associations TEXT,
                Ancestry_Distribution_Score_Development TEXT,
                Ancestry_Distribution_PGS_Evaluation TEXT,
                FTP_Link TEXT,
                Release_Date TEXT,
                License_Terms TEXT
            )
        """)
        
        # Create scores table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scores (
                PGS_ID TEXT REFERENCES pgs_metadata(PGS_ID),
                SCORE_TYPE TEXT,
                SAMPLE_ID TEXT,
                SCORE REAL
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS score_pgs_idx ON scores(PGS_ID)")
        
        # Create ancestry_groups table if needed
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ancestry_groups (
                population TEXT PRIMARY KEY,
                sample_ids TEXT
            )
        """)
        
        # Create lookup tables
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pgs_id_lookup (
                pgs_id TEXT PRIMARY KEY
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS score_type_lookup (
                score_type TEXT PRIMARY KEY
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sample_id_lookup (
                sample_id TEXT PRIMARY KEY
            )
        """)
        
        conn.commit()
        conn.close()

    @classmethod
    def create_database_from_uploads(
        cls, 
        dataset_name: str, 
        uploaded_files: List[str], 
        metadata_file: Optional[str] = None,
        base_db_dir: str = "db"
    ) -> str:
        """
        Create a new database from uploaded score files
        
        Args:
            dataset_name: Name for the dataset (will be sanitized for directory name)
            uploaded_files: List of paths to uploaded score files
            metadata_file: Optional path to metadata CSV file
            base_db_dir: Base directory for databases (default: "db")
            
        Returns:
            Path to the created database directory
        """
        # Sanitize dataset name for directory
        safe_name = cls._sanitize_dataset_name(dataset_name)
        dataset_dir = os.path.join(base_db_dir, safe_name)
        
        # Create dataset directory
        os.makedirs(dataset_dir, exist_ok=True)
        
        # Database paths
        pgs_db_path = os.path.join(dataset_dir, "pgs_data.db")
        tasks_db_path = os.path.join(dataset_dir, "tasks.db")
        
        # Create the databases
        pgs_db = cls(pgs_db_path, is_task_db=False)
        tasks_db = cls(tasks_db_path, is_task_db=True)
        
        # Process uploaded files into the database
        pgs_db._process_uploaded_files(uploaded_files, metadata_file)
        
        return dataset_dir
    
    @staticmethod
    def _sanitize_dataset_name(name: str) -> str:
        """Convert dataset name to safe directory name"""
        import re
        # Replace spaces and special chars with underscores, convert to lowercase
        safe_name = re.sub(r'[^\w\-_]', '_', name.strip())
        safe_name = re.sub(r'_+', '_', safe_name)  # Replace multiple underscores with single
        return safe_name.lower().strip('_')
    
    def _process_uploaded_files(self, uploaded_files: List[str], metadata_file: Optional[str] = None):
        """Process uploaded score files and populate the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Clear existing data
        cursor.execute("DELETE FROM scores")
        cursor.execute("DELETE FROM pgs_metadata")
        
        # Process each uploaded file
        for file_path in uploaded_files:
            if not os.path.exists(file_path):
                print(f"Warning: File {file_path} not found, skipping.")
                continue
                
            print(f"Processing file: {file_path}")
            self._load_scores_from_file(file_path, cursor)
        
        # Load metadata if provided
        if metadata_file and os.path.exists(metadata_file):
            self._load_metadata_from_file(metadata_file, conn)
        else:
            # Create basic metadata entries for any PGS IDs we found
            self._create_basic_metadata(cursor)
        
        # Update lookup tables
        self._update_lookup_tables(cursor)
        
        conn.commit()
        conn.close()
        print(f"Database created successfully with {len(uploaded_files)} files processed.")
    
    def _load_scores_from_file(self, file_path: str, cursor):
        """Load scores data from a single file"""
        # Detect if the file is gzipped and read accordingly
        if file_path.endswith(".gz"):
            f = gzip.open(file_path, "rt")
        else:
            f = open(file_path, "rt")
        
        try:
            data = []
            header = []
            last_pgs = ""
            write = True
            
            for line in f:
                row = line.strip("\n").split("\t")
                if row[0] == "PGS" or row[0].startswith("#"):  # Header or comment
                    header = row
                    continue
                
                if len(row) < 3:  # Skip incomplete rows
                    continue
                
                pgs = row[0]
                if pgs != last_pgs:
                    # Insert previous batch
                    if write and data:
                        cursor.executemany(
                            "INSERT INTO scores (PGS_ID, SCORE_TYPE, SAMPLE_ID, SCORE) VALUES (?, ?, ?, ?)", 
                            data
                        )
                    elif last_pgs:  # Don't print on first iteration
                        print(f"Warning: {last_pgs} had parsing errors, skipped")
                        
                    data = []
                    write = True
                    last_pgs = pgs
                
                score_type = row[1]
                for index, score in enumerate(row):
                    if index < 2:  # Skip PGS and SCORE_TYPE columns
                        continue
                    if index >= len(header):  # No header for this column
                        continue
                        
                    try:
                        score_val = float(score)
                        data.append((pgs, score_type, header[index], score_val))
                    except (ValueError, TypeError):
                        write = False
                        break
            
            # Insert final batch
            if data and write:
                cursor.executemany(
                    "INSERT INTO scores (PGS_ID, SCORE_TYPE, SAMPLE_ID, SCORE) VALUES (?, ?, ?, ?)", 
                    data
                )
        finally:
            f.close()
    
    def _load_metadata_from_file(self, metadata_file: str, conn):
        """Load metadata from uploaded CSV file"""
        try:
            df = pd.read_csv(metadata_file)
            
            # Try to map columns to our schema (flexible mapping)
            column_mapping = {
                'PGS_ID': ['PGS_ID', 'pgs_id', 'id'],
                'PGS_Name': ['PGS_Name', 'name', 'pgs_name'],
                'Reported_Trait': ['Reported_Trait', 'trait', 'reported_trait'],
                # Add more mappings as needed
            }
            
            # Rename columns to match our schema where possible
            for our_col, possible_names in column_mapping.items():
                for possible_name in possible_names:
                    if possible_name in df.columns:
                        df.rename(columns={possible_name: our_col}, inplace=True)
                        break
            
            # Ensure we have required columns, fill missing ones
            required_columns = [
                "PGS_ID", "PGS_Name", "Reported_Trait", "Mapped_Trait_Label", "Mapped_Trait_ID",
                "PGS_Development_Method", "PGS_Development_Details", "Original_Genome_Build",
                "Number_of_Variants", "Number_of_Interaction_Terms", "Type_of_Variant_Weight",
                "PGS_Publication_ID", "Publication_PMID", "Publication_DOI", 
                "Score_Matches_Publication", "Ancestry_Distribution_Variant_Associations", 
                "Ancestry_Distribution_Score_Development", "Ancestry_Distribution_PGS_Evaluation",
                "FTP_Link", "Release_Date", "License_Terms"
            ]
            
            for col in required_columns:
                if col not in df.columns:
                    df[col] = None
            
            # Convert boolean column if it exists
            if "Score_Matches_Publication" in df.columns:
                df["Score_Matches_Publication"] = df["Score_Matches_Publication"].apply(
                    lambda x: x == "TRUE" if pd.notna(x) else False
                )
            
            # Insert data into the database
            df[required_columns].to_sql("pgs_metadata", conn, if_exists="replace", index=False)
            print(f"Loaded metadata for {len(df)} PGS entries")
            
        except Exception as e:
            print(f"Error loading metadata file {metadata_file}: {e}")
            print("Creating basic metadata entries instead")
            self._create_basic_metadata(conn.cursor())
    
    def _create_basic_metadata(self, cursor):
        """Create basic metadata entries for PGS IDs found in scores"""
        # Get unique PGS IDs from scores table
        cursor.execute("SELECT DISTINCT PGS_ID FROM scores")
        pgs_ids = [row[0] for row in cursor.fetchall()]
        
        # Create basic metadata entries
        for pgs_id in pgs_ids:
            cursor.execute("""
                INSERT OR IGNORE INTO pgs_metadata (PGS_ID, PGS_Name, Reported_Trait) 
                VALUES (?, ?, ?)
            """, (pgs_id, f"Uploaded PGS {pgs_id}", "Unknown Trait"))
        
        print(f"Created basic metadata for {len(pgs_ids)} PGS entries")
    
    def _update_lookup_tables(self, cursor):
        """Update lookup tables with current data"""
        # Update PGS ID lookup
        cursor.execute("DELETE FROM pgs_id_lookup")
        cursor.execute("INSERT INTO pgs_id_lookup (pgs_id) SELECT DISTINCT PGS_ID FROM scores")
        
        # Update score type lookup
        cursor.execute("DELETE FROM score_type_lookup")
        cursor.execute("INSERT INTO score_type_lookup (score_type) SELECT DISTINCT SCORE_TYPE FROM scores")
        
        # Update sample ID lookup
        cursor.execute("DELETE FROM sample_id_lookup")
        cursor.execute("INSERT INTO sample_id_lookup (sample_id) SELECT DISTINCT SAMPLE_ID FROM scores")

    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  
        try:
            yield conn
        finally:
            conn.close()
            
    async def get_db(self):
        """Async connection provider for FastAPI dependency injection"""
        with self.get_connection() as conn:
            yield conn


# Usage functions for the web interface
def create_database_from_upload(dataset_name: str, uploaded_file_paths: List[str], metadata_path: Optional[str] = None) -> dict:
    """
    Create a new database from uploaded files (called from your FastAPI endpoint)
    
    Returns:
        dict with database info: {
            'name': dataset_name,
            'path': dataset_dir,
            'pgs_db_path': pgs_db_path,
            'tasks_db_path': tasks_db_path,
            'files_processed': len(uploaded_file_paths)
        }
    """
    try:
        dataset_dir = DatabaseConnection.create_database_from_uploads(
            dataset_name=dataset_name,
            uploaded_files=uploaded_file_paths,
            metadata_file=metadata_path
        )
        
        return {
            'success': True,
            'name': dataset_name,
            'path': dataset_dir,
            'pgs_db_path': os.path.join(dataset_dir, 'pgs_data.db'),
            'tasks_db_path': os.path.join(dataset_dir, 'tasks.db'),
            'files_processed': len(uploaded_file_paths)
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

def discover_existing_databases(base_dir: str = "/data/dev/db") -> List[dict]:
    """
    Discover existing database directories
    
    Returns:
        List of database info dicts
    """
    databases = []
    
    if not os.path.exists(base_dir):
        return databases
    
    for item in os.listdir(base_dir):
        dataset_path = os.path.join(base_dir, item)
        if os.path.isdir(dataset_path):
            pgs_db = os.path.join(dataset_path, 'pgs_data.db')
            tasks_db = os.path.join(dataset_path, 'tasks.db')
            print("Found database...")
            if os.path.exists(pgs_db):
                # Get some basic info about the database
                try:
                    with sqlite3.connect(pgs_db) as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT COUNT(*) FROM pgs_metadata")
                        pgs_count = cursor.fetchone()[0]
                        cursor.execute("SELECT COUNT(DISTINCT SAMPLE_ID) FROM scores")
                        sample_count = cursor.fetchone()[0]
                except:
                    pgs_count = 0
                    sample_count = 0
                
                databases.append({
                    'name': item.replace('_', ' ').title(),
                    'path': dataset_path,
                    'pgs_db_path': pgs_db,
                    'tasks_db_path': tasks_db,
                    'has_tasks_db': os.path.exists(tasks_db),
                    'pgs_count': pgs_count,
                    'sample_count': sample_count,
                    'created': os.path.getctime(dataset_path)
                })
    
    return sorted(databases, key=lambda x: x['created'], reverse=True)