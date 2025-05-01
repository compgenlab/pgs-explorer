import sqlite3
import os

# Database paths
DB_PATH = "/data/dev/db/pgs_data.db"
TASK_DB_PATH = "/data/dev/db/tasks.db"

def init_task_db():
    # Ensure the directory exists
    os.makedirs(os.path.dirname(TASK_DB_PATH), exist_ok=True)

    conn = sqlite3.connect(TASK_DB_PATH)
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

def get_connection():
    """Get a connection to the main PGS database"""
    return sqlite3.connect(DB_PATH)

def get_task_connection():
    """Get a connection to the task database"""
    return sqlite3.connect(TASK_DB_PATH)
    
# def initialize_db():
#     """Initialize database if it doesn't exist"""
#     if os.path.exists(DB_PATH):
#         return

#     # Create db directory if it doesn't exist
#     os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

#     file_path = "data/samples/pgs_scores_output.tsv.gz"  

#     # Detect if the file is gzipped and read accordingly
#     if file_path.endswith(".gz"):
#         f = gzip.open(file_path, "rt")  
#     else:
#         f = open(file_path, "rt")

#     conn = sqlite3.connect(DB_PATH)
#     cursor = conn.cursor()

#     # Create the pgs_metadata table
#     cursor.execute("DROP TABLE IF EXISTS pgs_metadata")

#     cursor.execute("""
#         CREATE TABLE IF NOT EXISTS pgs_metadata (
#             PGS_ID TEXT PRIMARY KEY,
#             PGS_Name TEXT,
#             Reported_Trait TEXT,
#             Mapped_Trait_Label TEXT,
#             Mapped_Trait_ID TEXT,
#             PGS_Development_Method TEXT,
#             PGS_Development_Details TEXT,
#             Original_Genome_Build TEXT,
#             Number_of_Variants INTEGER,
#             Number_of_Interaction_Terms INTEGER,
#             Type_of_Variant_Weight TEXT,
#             PGS_Publication_ID TEXT,
#             Publication_PMID INTEGER,
#             Publication_DOI TEXT,
#             Score_Matches_Publication BOOLEAN,
#             Ancestry_Distribution_Variant_Associations TEXT,
#             Ancestry_Distribution_Score_Development TEXT,
#             Ancestry_Distribution_PGS_Evaluation TEXT,
#             FTP_Link TEXT,
#             Release_Date TEXT,
#             License_Terms TEXT
#         )
#     """)

#     # Drop old table if it exists
#     cursor.execute("DROP TABLE IF EXISTS scores")

#     # Create table in "long format"
#     cursor.execute("""
#         CREATE TABLE IF NOT EXISTS scores (
#             PGS_ID TEXT REFERENCES pgs_metadata(PGS_ID),
#             SCORE_TYPE TEXT,
#             SAMPLE_ID TEXT,
#             SCORE REAL
#         )
#     """)
#     cursor.execute("CREATE INDEX score_pgs_idx ON scores(PGS_ID)")

#     # Reshape data: Convert wide format (IDs as columns) → long format (one row per (ID, Score))
#     data = []
#     header = []
#     last_pgs=""
#     write=True
#     for line in f:
#         row = line.strip("\n").split("\t")
#         if row[0]=="PGS":
#             header = row
#             continue 
#         pgs = row[0]
#         if pgs != last_pgs:
#             if write:
#                 cursor.executemany("INSERT INTO scores (PGS_ID, SCORE_TYPE, SAMPLE_ID, SCORE) VALUES (?, ?, ?, ?)", data)
#                 # print(f"{last_pgs} written")
#             else:
#                 print(f"{last_pgs} failed")
#             data = []
#             write=True
#             last_pgs=pgs
#         score_type = row[1]
#         for index, score in enumerate(row):  # Iterate over all sample ID columns
#             if index < 2: 
#                 continue 
#             try:
#                 data.append((pgs, score_type, header[index], float(score)))
#             except: 
#                 write=False

#         # Insert Data
#     if data and write:
#         cursor.executemany("INSERT INTO scores (PGS_ID, SCORE_TYPE, SAMPLE_ID, SCORE) VALUES (?, ?, ?, ?)", data)

#     metadata_csv_path = "data/pgs/score_info.csv"

#     # Load the metadata CSV
#     df = pd.read_csv(metadata_csv_path)

#     # Rename columns to match the SQL schema
#     df.columns = [
#         "PGS_ID", "PGS_Name", "Reported_Trait", "Mapped_Trait_Label", "Mapped_Trait_ID",
#         "PGS_Development_Method", "PGS_Development_Details", "Original_Genome_Build",
#         "Number_of_Variants", "Number_of_Interaction_Terms", "Type_of_Variant_Weight",
#         "PGS_Publication_ID", "Publication_PMID", "Publication_DOI", 
#         "Score_Matches_Publication", "Ancestry_Distribution_Variant_Associations", 
#         "Ancestry_Distribution_Score_Development", "Ancestry_Distribution_PGS_Evaluation",
#         "FTP_Link", "Release_Date", "License_Terms"
#     ]

#     # Convert boolean column to actual boolean type
#     df["Score_Matches_Publication"] = df["Score_Matches_Publication"].apply(lambda x: x == "TRUE")

#     # Insert data into the SQLite database
#     df.to_sql("pgs_metadata", conn, if_exists="replace", index=False)

#     conn.commit()
#     conn.close()
#     f.close()

# # Initialize DB when application starts
# initialize_db()