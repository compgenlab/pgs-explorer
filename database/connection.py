import sqlite3
import os
import gzip
import pandas as pd
from contextlib import contextmanager

class DatabaseConnection:
    def __init__(self, db_path, is_task_db=False):
        self.db_path = db_path
        self.is_task_db = is_task_db
        
        print(f"Connecting to db: {db_path}")

        # Initialize the appropriate database
        if is_task_db:
            self._init_task_db()
        else:
            self._initialize_db()
    
    def _init_task_db(self):
        """Initialize task database if it doesn't exist"""
        if os.path.exists(self.db_path):
            return

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

    def _initialize_db(self):
        """Initialize main database if it doesn't exist"""
        if os.path.exists(self.db_path):
            return

        # Create db directory if it doesn't exist
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        file_path = "data/samples/pgs_scores_output.tsv.gz"
        
        # Check if the data file exists
        if not os.path.exists(file_path):
            print(f"Warning: Data file {file_path} not found. Database will be empty.")
            # Create empty tables
            self._create_empty_tables()
            return

        # Detect if the file is gzipped and read accordingly
        if file_path.endswith(".gz"):
            f = gzip.open(file_path, "rt")
        else:
            f = open(file_path, "rt")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create the pgs_metadata table
        cursor.execute("DROP TABLE IF EXISTS pgs_metadata")
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

        # Drop old table if it exists
        cursor.execute("DROP TABLE IF EXISTS scores")

        # Create table in "long format"
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scores (
                PGS_ID TEXT REFERENCES pgs_metadata(PGS_ID),
                SCORE_TYPE TEXT,
                SAMPLE_ID TEXT,
                SCORE REAL
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS score_pgs_idx ON scores(PGS_ID)")

        # Load scores data
        self._load_scores_data(f, cursor)
        
        # Load metadata
        self._load_metadata(conn)

        conn.commit()
        conn.close()
        f.close()
    
    def _create_empty_tables(self):
        """Create empty database tables"""
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
    
    def _load_scores_data(self, f, cursor):
        """Load scores data from file"""
        data = []
        header = []
        last_pgs = ""
        write = True
        
        for line in f:
            row = line.strip("\n").split("\t")
            if row[0] == "PGS":
                header = row
                continue
            
            pgs = row[0]
            if pgs != last_pgs:
                if write and data:
                    cursor.executemany(
                        "INSERT INTO scores (PGS_ID, SCORE_TYPE, SAMPLE_ID, SCORE) VALUES (?, ?, ?, ?)", 
                        data
                    )
                else:
                    print(f"{last_pgs} failed")
                data = []
                write = True
                last_pgs = pgs
            
            score_type = row[1]
            for index, score in enumerate(row):
                if index < 2:
                    continue
                try:
                    data.append((pgs, score_type, header[index], float(score)))
                except:
                    write = False

        # Insert last batch
        if data and write:
            cursor.executemany(
                "INSERT INTO scores (PGS_ID, SCORE_TYPE, SAMPLE_ID, SCORE) VALUES (?, ?, ?, ?)", 
                data
            )
    
    def _load_metadata(self, conn):
        """Load metadata from CSV file"""
        metadata_csv_path = "data/pgs/score_info.csv"
        
        if not os.path.exists(metadata_csv_path):
            print(f"Warning: Metadata file {metadata_csv_path} not found.")
            return
        
        # Load the metadata CSV
        df = pd.read_csv(metadata_csv_path)

        # Rename columns to match the SQL schema
        df.columns = [
            "PGS_ID", "PGS_Name", "Reported_Trait", "Mapped_Trait_Label", "Mapped_Trait_ID",
            "PGS_Development_Method", "PGS_Development_Details", "Original_Genome_Build",
            "Number_of_Variants", "Number_of_Interaction_Terms", "Type_of_Variant_Weight",
            "PGS_Publication_ID", "Publication_PMID", "Publication_DOI", 
            "Score_Matches_Publication", "Ancestry_Distribution_Variant_Associations", 
            "Ancestry_Distribution_Score_Development", "Ancestry_Distribution_PGS_Evaluation",
            "FTP_Link", "Release_Date", "License_Terms"
        ]

        # Convert boolean column to actual boolean type
        df["Score_Matches_Publication"] = df["Score_Matches_Publication"].apply(lambda x: x == "TRUE")

        # Insert data into the SQLite database
        df.to_sql("pgs_metadata", conn, if_exists="replace", index=False)
 
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