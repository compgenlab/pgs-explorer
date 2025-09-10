from fastapi import Depends
from .connection import DatabaseConnection
from .repositories.score_repository import ScoreRepository
from .repositories.ancestry_repository import AncestryRepository
from .repositories.metadata_repository import MetadataRepository
from .repositories.task_repository import TaskRepository
from .repositories.session_repository import SessionRepository
from .repositories.cohort_repository import CohortRepository
from .repositories.temporary_score_repository import TemporaryScoreRepository
from apps.core.config import DB_PATH, TASK_DB_PATH
import numpy as np
import os
import sqlite3
from pathlib import Path
from typing import List, Tuple

class Database:
    """Master database object that provides access to all repositories"""
    
    def __init__(self, db_path=None, task_db_path=None):
        """
        Initialize the Database with all repositories
        
        Parameters:
        -----------
        db_path : str, optional
            Path to the database. Defaults to DB_PATH if not provided
        """
        self.db_path = db_path or DB_PATH
        self.task_db_path = task_db_path or TASK_DB_PATH

        self.connection = DatabaseConnection(self.db_path)
        self.tasks_connection = DatabaseConnection(self.task_db_path, is_task_db=True)

        # Initialize repositories
        self.scores = ScoreRepository(self.connection)
        self.ancestry = AncestryRepository(self.connection)
        self.metadata = MetadataRepository(self.connection)
        self.tasks = TaskRepository(self.tasks_connection)
        self.sessions = SessionRepository(self.tasks_connection)
        self.cohorts = CohortRepository(self.tasks_connection)  
        self.temporary_scores = TemporaryScoreRepository(self.tasks_connection)  

    def get_connection(self):
        """Get the underlying database connection manager"""
        return self.connection

    def get_all_cohorts(self, user_id: str = None):
        """Get all cohorts available (ancestry + custom), formatted consistently."""
        all_cohorts = []
        
        # Get ancestry cohorts
        ancestry_cohorts = self.ancestry.get_all_cohorts()
        all_cohorts.extend(ancestry_cohorts)
        
        if user_id:
            print(f"Getting cohorts for {user_id}")
            custom_cohorts = self.cohorts.get_user_cohorts(user_id)
            
            # Format to match ancestry cohort structure
            formatted_custom = [
                {
                    "name": cohort["cohort_name"],
                    "sample_ids": cohort["sample_ids"]
                }
                for cohort in custom_cohorts
            ]
            
            all_cohorts.extend(formatted_custom)
        
        return all_cohorts
    
    def get_sample_ids_by_cohort(self, cohort: str, user_id: str = None):
        """Get sample IDs for any cohort type (ancestry or custom)."""
        
        # Handle "ALL" case
        if cohort == "ALL":
            return self.ancestry.get_all_sample_ids()
        
        # Try custom cohort first (if user_id provided)
        if user_id:
            print(f"Looking for custom cohort... {cohort}")
            custom_cohort = self.cohorts.get_cohort(cohort, user_id)
            if custom_cohort:
                return custom_cohort["sample_ids"]
        
        # Try ancestry cohort
        try:
            return self.ancestry.get_sample_ids_by_cohort(cohort)
        except ValueError:
            pass
        
        # If nothing found, raise error
        raise ValueError(f"Cohort '{cohort}' not found")

    def get_all_pgs_with_traits(self, user_id: str = None):
        """Get all PGS IDs with traits (permanent + temporary), formatted consistently."""
        all_pgs = []
        
        # Get permanent PGS from main database
        permanent_pgs = self.scores.get_all_pgs_with_traits()  
        all_pgs.extend(permanent_pgs)
        print(f"Fetched {len(permanent_pgs)} permanent PGS from the lookup table.")

        # Get temporary PGS for this user
        if user_id:
            temp_pgs = self.temporary_scores.get_all_pgs_with_traits(user_id)
            print(f"Fetched {len(temp_pgs)} temporary PGS from the user session.")
            all_pgs.extend(temp_pgs)
        
        return all_pgs

    def get_all_pgs_ids(self, user_id: str = None):
        """Get all PGS IDs (permanent + temporary)."""
        all_pgs_with_traits = self.get_all_pgs_with_traits(user_id)
        return [pgs["id"] for pgs in all_pgs_with_traits]

    def get_score_types_for_pgs(self, pgs_id: str, user_id: str = None):
        """Get distinct score types for a given PGS_ID from both permanent and temporary sources."""
        # Check permanent scores first
        permanent_valid = self.scores.get_valid_pgs_ids([pgs_id])
        if permanent_valid:
            return self.scores.get_score_types_for_pgs(pgs_id)
        
        # If not found in permanent and user_id provided, try temporary
        if user_id:
            temporary_valid = self.temporary_scores.get_valid_pgs_ids([pgs_id], user_id)
            if temporary_valid:
                return self.temporary_scores.get_score_types_for_pgs(pgs_id, user_id)
        
        return []

    def get_scores_for_pgs(self, pgs_ids, score_type, sample_ids=None, user_id=None):
        """Get scores for one or more PGS IDs from both permanent and temporary sources."""
        if not isinstance(pgs_ids, list):
            pgs_ids = [pgs_ids]
        
        all_scores = {}
        
        # Split into valid permanent and temporary IDs
        permanent_pgs = self.scores.get_valid_pgs_ids(pgs_ids)
        temporary_pgs = []
        
        if user_id:
            temporary_pgs = self.temporary_scores.get_valid_pgs_ids(pgs_ids, user_id)
        
        # Get scores from permanent repository
        if permanent_pgs:
            pgs_scores = self.scores.get_scores_for_pgs(permanent_pgs, score_type, sample_ids)
            all_scores.update(pgs_scores)
        
        # Get scores from temporary repository
        if temporary_pgs and user_id:
            print(f"Detected temporary scores for: {temporary_pgs}")
            temp_scores = self.temporary_scores.get_scores_for_pgs(temporary_pgs, score_type, sample_ids, user_id)
            all_scores.update(temp_scores)
        
        return all_scores

    def get_all_scores_for_pgs(self, pgs_id: str, user_id: str = None):
        """Get all scores for a PGS ID across all score types and samples from both sources."""
        # Check permanent scores first
        permanent_valid = self.scores.get_valid_pgs_ids([pgs_id])
        if permanent_valid:
            return self.scores.get_all_scores_for_pgs(pgs_id)
        
        # If not found in permanent and user_id provided, try temporary
        if user_id:
            temporary_valid = self.temporary_scores.get_valid_pgs_ids([pgs_id], user_id)
            if temporary_valid:
                return self.temporary_scores.get_all_scores_for_pgs(pgs_id, user_id)
        
        return []

    def get_score_matrix(self, sample_ids, pgs_ids, score_type, user_id=None,
                        output_format="dict", handle_missing=False,
                        upper_threshold=None, lower_threshold=None):
        """Get score matrix combining permanent and temporary data."""
        if not isinstance(pgs_ids, list):
            pgs_ids = [pgs_ids]
        
        # Split into valid permanent and temporary IDs
        permanent_pgs = self.scores.get_valid_pgs_ids(pgs_ids)
        temporary_pgs = []
        
        if user_id:
            temporary_pgs = self.temporary_scores.get_valid_pgs_ids(pgs_ids, user_id)
        
        # Get data from both sources
        combined_dict = {}
        sample_pgs = []
        
        if permanent_pgs:
            perm_dict, _ = self.scores.get_score_matrix(
                sample_ids, permanent_pgs, score_type, "dict", 
                handle_missing, upper_threshold, lower_threshold
            )
            if perm_dict:
                sample_pgs = list(list(perm_dict.values())[0].keys())
            combined_dict.update(perm_dict)
        
        if temporary_pgs and user_id:
            temp_dict, _ = self.temporary_scores.get_score_matrix(
                sample_ids, temporary_pgs, score_type, user_id, "dict",
                handle_missing, upper_threshold, lower_threshold
            )
            if temp_dict:
                sample_pgs = list(list(temp_dict.values())[0].keys())
            
            # Merge temporary data into combined dict
            for sample_id, pgs_scores in temp_dict.items():
                if sample_id not in combined_dict:
                    combined_dict[sample_id] = {}
                combined_dict[sample_id].update(pgs_scores)
        
        if combined_dict:
            sample_pgs = list(list(combined_dict.values())[0].keys())
        
        if output_format == "numpy":
            # Convert combined dict to numpy matrix
            available_samples = list(combined_dict.keys())
            available_pgs = set()
            for sample_scores in combined_dict.values():
                available_pgs.update(sample_scores.keys())
            available_pgs = list(available_pgs)
            
            if sample_ids:
                final_samples = [s for s in sample_ids if s in available_samples]
            else:
                final_samples = available_samples
            
            final_pgs = [p for p in pgs_ids if p in available_pgs]
            sample_to_index = {sample_id: i for i, sample_id in enumerate(final_samples)}
            pgs_to_index = {pgs_id: j for j, pgs_id in enumerate(final_pgs)}
                
            matrix = np.full((len(final_samples), len(final_pgs)), np.nan)

            for sample_id, pgs_scores in combined_dict.items():
                i = sample_to_index.get(sample_id)
                if i is not None:
                    for pgs_id, score in pgs_scores.items():
                        j = pgs_to_index.get(pgs_id)
                        if j is not None:
                            matrix[i, j] = score

            if handle_missing:
                for j in range(matrix.shape[1]):
                    col_values = matrix[:, j]
                    non_nan_values = col_values[~np.isnan(col_values)]
                    if len(non_nan_values) > 0:
                        col_mean = np.mean(non_nan_values)
                        mask = np.isnan(col_values)
                        if mask.any():
                            matrix[mask, j] = col_mean

            return matrix, final_pgs
        else:
            return combined_dict, list(combined_dict.keys())

    def get_score_by_cohorts(self, pgs_id, score_type, cohorts, user_id=None):
        """Get scores for a PGS ID, grouped by cohorts from both sources."""
        # Check permanent scores first
        permanent_valid = self.scores.get_valid_pgs_ids([pgs_id])
        if permanent_valid:
            print(f"Score {pgs_id} is a permanent score.")
            return self.scores.get_score_by_cohorts(pgs_id, score_type, cohorts)
        
        # If not permanent and user_id provided, try temporary
        if user_id:
            temporary_valid = self.temporary_scores.get_valid_pgs_ids([pgs_id], user_id)
            if temporary_valid:
                print(f"Score {pgs_id} is a temporary score.")
                return self.temporary_scores.get_score_by_cohorts(pgs_id, score_type, cohorts, user_id)
        
        return []

    def get_sample_ids_with_scores(self, score_type, pgs_ids, user_id=None):
        """Get all sample IDs that have scores for the given PGS IDs and score type."""
        if not isinstance(pgs_ids, list):
            pgs_ids = [pgs_ids]
        
        all_sample_ids = set()
        
        # Split into valid permanent and temporary IDs
        permanent_pgs = self.scores.get_valid_pgs_ids(pgs_ids)
        temporary_pgs = []
        
        if user_id:
            temporary_pgs = self.temporary_scores.get_valid_pgs_ids(pgs_ids, user_id)
        
        # Get sample IDs from both sources (only if we have valid IDs)
        if permanent_pgs:
            perm_samples = self.scores.get_sample_ids_with_scores(score_type, permanent_pgs)
            all_sample_ids.update(perm_samples)
        
        if temporary_pgs and user_id:
            temp_samples = self.temporary_scores.get_sample_ids_with_scores(score_type, temporary_pgs, user_id)
            all_sample_ids.update(temp_samples)
        
        return sorted(list(all_sample_ids))

    def get_score_statistics_with_outliers(self, score_type, pgs_ids, user_id=None, std_dev_threshold=None):
        """Calculate comprehensive statistics for scores from both sources."""
        if not isinstance(pgs_ids, list):
            pgs_ids = [pgs_ids]
        
        # Split into valid permanent and temporary IDs
        permanent_pgs = self.scores.get_valid_pgs_ids(pgs_ids)
        temporary_pgs = []
        
        if user_id:
            temporary_pgs = self.temporary_scores.get_valid_pgs_ids(pgs_ids, user_id)
        
        print(f"DEBUG: permanent scores: {permanent_pgs}\n temporary: {temporary_pgs}")

        # Collect all scores from both sources
        all_scores = []
        
        # Get scores from permanent data
        if permanent_pgs:
            perm_dict = self.scores.get_score_matrix(
                sample_ids=None, pgs_ids=permanent_pgs, score_type=score_type, 
                output_format="dict"
            )[0]
            for sample_scores in perm_dict.values():
                all_scores.extend(sample_scores.values())
        
        # Get scores from temporary data
        if temporary_pgs and user_id:
            temp_dict = self.temporary_scores.get_score_matrix(
                sample_ids=None, pgs_ids=temporary_pgs, score_type=score_type, user_id=user_id,
                output_format="dict"
            )[0]
            for sample_scores in temp_dict.values():
                all_scores.extend(sample_scores.values())
        
        # Return default if no scores found
        if not all_scores:
            default_stats = {
                'avg': 0, 'min': 0, 'max': 0, 'stdev': 1.0, 'count': 0, 'outlier_count': 0
            }
            if std_dev_threshold is not None:
                default_stats.update({
                    'upper_threshold': 0,
                    'lower_threshold': 0
                })
            return default_stats
        
        avg = np.mean(all_scores)
        min_score = np.min(all_scores)
        max_score = np.max(all_scores)
        stdev = np.std(all_scores)
        count = len(all_scores)
        
        stats = {
            'avg': avg,
            'min': min_score,
            'max': max_score,
            'stdev': stdev,
            'count': count
        }
        
        # Calculate outliers if threshold provided
        if std_dev_threshold:
            print(std_dev_threshold)
            upper_threshold = avg + (std_dev_threshold * stdev)
            lower_threshold = avg - (std_dev_threshold * stdev)
            
            outlier_count = sum(1 for score in all_scores if score > upper_threshold or score < lower_threshold)
            
            stats.update({
                'outlier_count': outlier_count,
                'upper_threshold': upper_threshold,
                'lower_threshold': lower_threshold
            })
        print(stats)
        return stats

    def get_score_statistics(self, score_type, pgs_ids, user_id=None):
        """Calculate basic statistics for scores (backward compatibility)."""
        stats = self.get_score_statistics_with_outliers(score_type, pgs_ids, user_id)
        return (stats['avg'], stats['min'], stats['max'], stats['stdev'])

    def count_outliers(self, score_type, pgs_ids, upper_threshold, lower_threshold, user_id=None):
        """Count outliers in the dataset from both sources."""
        if not isinstance(pgs_ids, list):
            pgs_ids = [pgs_ids]
        
        # Split into valid permanent and temporary IDs
        permanent_pgs = self.scores.get_valid_pgs_ids(pgs_ids)
        temporary_pgs = []
        
        if user_id:
            temporary_pgs = self.temporary_scores.get_valid_pgs_ids(pgs_ids, user_id)
        
        total_outliers = 0
        
        if permanent_pgs:
            total_outliers += self.scores.count_outliers(score_type, permanent_pgs, upper_threshold, lower_threshold)
        
        if temporary_pgs and user_id:
            total_outliers += self.temporary_scores.count_outliers(score_type, temporary_pgs, upper_threshold, lower_threshold, user_id)
        
        return total_outliers

    def fetch_pgs_ids(self, specific_pgs_ids=None, score_type=None, user_id=None):
        """Fetch PGS IDs from both permanent and temporary sources."""
        permanent_ids = self.scores.fetch_pgs_ids(specific_pgs_ids, score_type)
        
        if user_id:
            temp_ids = self.temporary_scores.fetch_pgs_ids(user_id, specific_pgs_ids, score_type)
            # Combine and deduplicate
            all_ids = list(set(permanent_ids + temp_ids))
            return sorted(all_ids)
        
        return permanent_ids

class DatabaseManager: 
    def __init__(self, db_directory=None):
        # TODO: make this configurable
        self.db_directory = db_directory or '/data/dev/db/'
        self.all_databases = self.initialize_all_dbs(self.db_directory)
        self.active_db = self.all_databases[0]
        
    def switch_active_db(self, db_path):
        for database in self.all_databases:
            if database.db_path == db_path:
                self.active_db = database
                return
        print(f"Error: Requested Database at: {db_path} not found")

    def initialize_all_dbs(self, db_directory):
        """Initialize all Database objects"""
        databases = []

        for pgs_path, tasks_path in self._search_directory_for_db(db_directory):
            databases.append(Database(db_path=pgs_path, task_db_path=tasks_path))

        return databases
        
    def add_new_database(self, scores_file_path: str, database_name: str, metadata_csv_path: str = None):
        """
        Create a new database from a scores file.
        
        Args:
            scores_file_path: Path to the scores file (can be .tsv, .tsv.gz, etc.)
            database_name: Name for the new database directory
            metadata_csv_path: Optional path to metadata CSV file
            
        Returns:
            str: Path to the created database file, or None if failed
        """
        try:
            # Create new database directory
            db_dir = Path(self.db_directory) / database_name
            db_dir.mkdir(parents=True, exist_ok=True)
            
            pgs_db_path = db_dir / f"{database_name}.db"
            tasks_db_path = db_dir / "tasks.db"
            
            print(f"Creating new database: {pgs_db_path}")
            
            self._create_pgs_database_from_file(scores_file_path, str(pgs_db_path), metadata_csv_path)
            self._get_or_create_tasks_db(db_dir)
            self.all_databases.append(Database(db_path=str(pgs_db_path), task_db_path=str(tasks_db_path)))

            print(f"Successfully created database: {database_name}")
            return str(pgs_db_path)
            
        except Exception as e:
            print(f"Error creating new database {database_name}: {e}")
            return None

    def _create_pgs_database_from_file(self, scores_file_path: str, db_path: str, metadata_csv_path: str = None):
        """Create PGS database from scores file (based on old initialize_db logic)."""
        try:
            # Detect if the file is gzipped and read accordingly
            if scores_file_path.endswith(".gz"):
                f = gzip.open(scores_file_path, "rt")
            else:
                f = open(scores_file_path, "rt")

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # # Create the pgs_metadata table
            # cursor.execute("DROP TABLE IF EXISTS pgs_metadata")
            # cursor.execute('''
            #     CREATE TABLE IF NOT EXISTS pgs_metadata (
            #         PGS_ID TEXT PRIMARY KEY,
            #         PGS_Name TEXT,
            #         Reported_Trait TEXT,
            #         Mapped_Trait_Label TEXT,
            #         Mapped_Trait_ID TEXT,
            #         PGS_Development_Method TEXT,
            #         PGS_Development_Details TEXT,
            #         Original_Genome_Build TEXT,
            #         Number_of_Variants INTEGER,
            #         Number_of_Interaction_Terms INTEGER,
            #         Type_of_Variant_Weight TEXT,
            #         PGS_Publication_ID TEXT,
            #         Publication_PMID INTEGER,
            #         Publication_DOI TEXT,
            #         Score_Matches_Publication BOOLEAN,
            #         Ancestry_Distribution_Variant_Associations TEXT,
            #         Ancestry_Distribution_Score_Development TEXT,
            #         Ancestry_Distribution_PGS_Evaluation TEXT,
            #         FTP_Link TEXT,
            #         Release_Date TEXT,
            #         License_Terms TEXT
            #     )
            # ''')

            # Drop old table if it exists
            cursor.execute("DROP TABLE IF EXISTS scores")

            # Create table in "long format"
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS scores (
                    PGS_ID TEXT REFERENCES pgs_metadata(PGS_ID),
                    SCORE_TYPE TEXT,
                    SAMPLE_ID TEXT,
                    SCORE REAL
                )
            ''')
            cursor.execute("CREATE INDEX score_pgs_idx ON scores(PGS_ID)")

            # Reshape data: Convert wide format (IDs as columns) → long format (one row per (ID, Score))
            data = []
            header = []
            last_pgs = ""
            write = True
            
            print("Processing scores file...")
            for line_num, line in enumerate(f):
                if line_num % 10000 == 0 and line_num > 0:
                    print(f"  Processed {line_num} lines...")
                    
                row = line.strip("\n").split("\t")
                if row[0] == "PGS":
                    header = row
                    continue
                    
                pgs = row[0]
                if pgs != last_pgs:
                    if write and data:
                        cursor.executemany("INSERT INTO scores (PGS_ID, SCORE_TYPE, SAMPLE_ID, SCORE) VALUES (?, ?, ?, ?)", data)
                        print(f"  Written {last_pgs}")
                    elif not write:
                        print(f"  Failed {last_pgs}")
                    data = []
                    write = True
                    last_pgs = pgs
                    
                score_type = row[1]
                for index, score in enumerate(row):  # Iterate over all sample ID columns
                    if index < 2:
                        continue
                    try:
                        data.append((pgs, score_type, header[index], float(score)))
                    except:
                        write = False

            # Insert final batch
            if data and write:
                cursor.executemany("INSERT INTO scores (PGS_ID, SCORE_TYPE, SAMPLE_ID, SCORE) VALUES (?, ?, ?, ?)", data)
                print(f"  Written {last_pgs} (final)")

            # # Load metadata if provided
            # if metadata_csv_path and os.path.exists(metadata_csv_path):
            #     print("Loading metadata...")
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
            #     print("  Metadata loaded successfully")

            conn.commit()
            conn.close()
            f.close()

            # Create additional tables and indexes
            # self._create_additional_tables(cursor)
            self._ensure_optional_tables_exist(db_path)

            print(f"Successfully created PGS database: {db_path}")
            return True
            
        except Exception as e:
            print(f"Error creating PGS database from file: {e}")
            return False

    def _search_directory_for_db(self, db_directory):
        """Search directory for valid database pairs."""
        valid_pairs = []
        
        for subdir in self._get_subdirectories(db_directory):
            db_files = self._find_db_files(subdir)
            pgs_db = self._find_pgs_database(db_files, subdir)
            if pgs_db:
                tasks_db = self._get_or_create_tasks_db(subdir)
                if tasks_db:
                    valid_pairs.append([pgs_db, tasks_db])
        
        return valid_pairs

    def _get_subdirectories(self, db_directory):
        """Get all subdirectories in the given directory."""
        root_path = Path(db_directory)
        if not root_path.exists():
            return []
        return [d for d in root_path.iterdir() if d.is_dir()]

    def _find_db_files(self, subdir):
        """Find all .db files in a subdirectory."""
        return list(Path(subdir).glob("*.db"))

    def _find_pgs_database(self, db_files, subdir):
        """Find and validate the PGS database in the subdirectory."""
        pgs_databases = []
        
        for db_file in db_files:
            if self._is_pgs_database(str(db_file)):
                pgs_databases.append(str(db_file))
        
        if len(pgs_databases) > 1:
            raise ValueError(f"Multiple PGS databases found in {subdir}: {pgs_databases}")
        
        return pgs_databases[0] if pgs_databases else None

    def _is_pgs_database(self, db_path):
        """Check if database has PGS schema and add missing tables."""
        # Check for minimum required tables
        required_tables = ['scores']
        if not self._has_required_tables(db_path, required_tables):
            return False
        
        # If it's a valid PGS database, ensure all optional tables exist
        self._ensure_optional_tables_exist(db_path)
        return True

    def _ensure_optional_tables_exist(self, db_path):
        """Add missing optional tables to the PGS database."""
        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                
                # Test if we can write to the database
                cursor.execute("CREATE TEMP TABLE test_write (id INTEGER)")
                cursor.execute("DROP TABLE test_write")
                
                # Get existing tables
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                existing_tables = {row[0] for row in cursor.fetchall()}
                lookup = False

                # Create missing tables
                if 'pgs_metadata' not in existing_tables:
                    self._create_pgs_metadata_table(cursor)
                
                if 'ancestry' not in existing_tables:
                    self._create_ancestry_table(cursor)
                
                if 'ancestry_groups' not in existing_tables:
                    self._create_ancestry_groups_table(cursor)
                
                if 'pgs_id_lookup' not in existing_tables:
                    self._create_pgs_id_lookup_table(cursor)
                    lookup = True
                
                if 'score_type_lookup' not in existing_tables:
                    self._create_score_type_lookup_table(cursor)
                    lookup = True


                if 'sample_id_lookup' not in existing_tables:
                    self._create_sample_id_lookup_table(cursor)
                    lookup = True 

                if 'pgs_trait_lookup' not in existing_tables:
                    self._create_pgs_trait_lookup_table(cursor)
                    lookup = True
                # Create indexes and populate lookup tables
                if lookup:
                    self._create_indexes_only(cursor)
                    self._populate_lookup_tables(cursor)

                conn.commit()
                print(f"Updated database schema: {db_path}")
                
        except sqlite3.OperationalError as e:
            if "database or disk is full" in str(e):
                print(f"Warning: Cannot update {db_path} - disk full or database corrupted. Skipping schema updates.")
            else:
                print(f"Database error for {db_path}: {e}")
        except Exception as e:
            print(f"Error updating database schema {db_path}: {e}")
   

    def _create_pgs_metadata_table(self, cursor):
        """Create pgs_metadata table."""
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS "pgs_metadata" (
                "PGS_ID" TEXT PRIMARY KEY,
                "PGS_Name" TEXT,
                "Reported_Trait" TEXT,
                "Mapped_Trait_Label" TEXT,
                "Mapped_Trait_ID" TEXT,
                "PGS_Development_Method" TEXT,
                "PGS_Development_Details" TEXT,
                "Original_Genome_Build" TEXT,
                "Number_of_Variants" INTEGER,
                "Number_of_Interaction_Terms" INTEGER,
                "Type_of_Variant_Weight" TEXT,
                "PGS_Publication_ID" TEXT,
                "Publication_PMID" REAL,
                "Publication_DOI" TEXT,
                "Score_Matches_Publication" INTEGER,
                "Ancestry_Distribution_Variant_Associations" TEXT,
                "Ancestry_Distribution_Score_Development" TEXT,
                "Ancestry_Distribution_PGS_Evaluation" TEXT,
                "FTP_Link" TEXT,
                "Release_Date" TEXT,
                "License_Terms" TEXT
            )
        ''')
    
    def _create_ancestry_table(self, cursor):
        """Create ancestry table."""
        cursor.execute('''
            CREATE TABLE ancestry (
                sample_id TEXT PRIMARY KEY,
                population TEXT NOT NULL
            )
        ''')
    
    def _create_ancestry_groups_table(self, cursor):
        """Create ancestry_groups table."""
        cursor.execute('''
            CREATE TABLE ancestry_groups (
                population TEXT PRIMARY KEY,
                sample_ids JSON
            )
        ''')
    
    def _create_pgs_id_lookup_table(self, cursor):
        """Create pgs_id_lookup table."""
        cursor.execute('''
            CREATE TABLE pgs_id_lookup (
                pgs_id TEXT PRIMARY KEY
            )
        ''')
    
    def _create_score_type_lookup_table(self, cursor):
        """Create score_type_lookup table."""
        cursor.execute('''
            CREATE TABLE score_type_lookup (
                score_type TEXT PRIMARY KEY
            )
        ''')
    
    def _create_sample_id_lookup_table(self, cursor):
        """Create sample_id_lookup table."""
        cursor.execute('''
            CREATE TABLE sample_id_lookup (
                sample_id TEXT PRIMARY KEY
            )
        ''')
    
    def _create_pgs_trait_lookup_table(self, cursor):
        """Create pgs_trait_lookup table."""
        cursor.execute('''
            CREATE TABLE pgs_trait_lookup (
                pgs_id TEXT PRIMARY KEY,
                trait TEXT NOT NULL
            )
        ''')
    
    def _create_indexes_only(self, cursor):
        """Create indexes without triggers."""
        cursor.execute('CREATE INDEX IF NOT EXISTS score_pgs_idx ON scores(PGS_ID)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_scores_sample_id ON scores(SAMPLE_ID)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_scores_value_type ON scores(SCORE, SCORE_TYPE)')
    
    def _populate_lookup_tables(self, cursor):
        """Populate lookup tables from existing data (same logic as triggers)."""
        try:
            # Populate pgs_id_lookup
            cursor.execute('''
                INSERT OR IGNORE INTO pgs_id_lookup (pgs_id)
                SELECT DISTINCT PGS_ID FROM scores WHERE PGS_ID IS NOT NULL
            ''')
            
            # Populate score_type_lookup  
            cursor.execute('''
                INSERT OR IGNORE INTO score_type_lookup (score_type)
                SELECT DISTINCT SCORE_TYPE FROM scores WHERE SCORE_TYPE IS NOT NULL
            ''')
            
            # Populate sample_id_lookup
            cursor.execute('''
                INSERT OR IGNORE INTO sample_id_lookup (sample_id)
                SELECT DISTINCT SAMPLE_ID FROM scores WHERE SAMPLE_ID IS NOT NULL
            ''')
            
            # Populate pgs_trait_lookup (same logic as the trigger)
            cursor.execute('''
                INSERT OR IGNORE INTO pgs_trait_lookup (pgs_id, trait)
                SELECT DISTINCT s.PGS_ID, COALESCE(m.Reported_Trait, 'Unknown') as trait
                FROM scores s
                LEFT JOIN pgs_metadata m ON s.PGS_ID = m.PGS_ID
                WHERE s.PGS_ID IS NOT NULL
            ''')
            
            print("  Populated lookup tables from existing data")
            
        except Exception as e:
            print(f"  Warning: Could not populate lookup tables: {e}")

    def _get_or_create_tasks_db(self, subdir):
        """Get existing tasks DB or create a new one."""
        # Look for existing tasks database
        for db_file in self._find_db_files(subdir):
            if self._is_tasks_database(str(db_file)):
                return str(db_file)
        
        # Create new tasks database
        tasks_db_path = Path(subdir) / "tasks.db"
        if self._create_tasks_database(str(tasks_db_path)):
            return str(tasks_db_path)
        
        return None

    def _is_tasks_database(self, db_path):
        """Check if database has tasks schema."""
        required_tables = ['image_tasks', 'user_sessions', 'user_cohorts', 
                          'user_temporary_scores', 'user_temporary_uploads']
        return self._has_required_tables(db_path, required_tables)

    def _has_required_tables(self, db_path, required_tables):
        """Check if database has all required tables."""
        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                existing_tables = {row[0] for row in cursor.fetchall()}
                return all(table in existing_tables for table in required_tables)
        except:
            return False

    def _create_tasks_database(self, tasks_db_path):
        """Create tasks database with required schema."""
        try:
            os.makedirs(os.path.dirname(tasks_db_path), exist_ok=True)
            
            with sqlite3.connect(tasks_db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    CREATE TABLE image_tasks (
                        task_id TEXT PRIMARY KEY,
                        task_type TEXT,
                        name TEXT,
                        status TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        completed_at TEXT,
                        result_path TEXT,
                        error TEXT,
                        request_data TEXT NOT NULL,
                        user_id TEXT
                    )
                ''')
                
                cursor.execute('''
                    CREATE TABLE user_sessions (
                        session_id TEXT PRIMARY KEY,
                        user_id TEXT,
                        created_at DATETIME,
                        last_activity DATETIME,
                        session_data TEXT
                    )
                ''')
                
                cursor.execute('''
                    CREATE TABLE user_cohorts (
                        cohort_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        cohort_name TEXT NOT NULL,
                        sample_ids TEXT NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES user_sessions(user_id)
                    )
                ''')
                
                cursor.execute('''
                    CREATE TABLE user_temporary_scores (
                        user_id TEXT NOT NULL,
                        PGS_ID TEXT,
                        SCORE_TYPE TEXT,
                        SAMPLE_ID TEXT,
                        SCORE REAL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES user_sessions(user_id)
                    )
                ''')
                
                cursor.execute('''
                    CREATE TABLE user_temporary_uploads (
                        upload_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        pgs_id TEXT NOT NULL,
                        trait TEXT NOT NULL,
                        records_count INTEGER,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES user_sessions(user_id)
                    )
                ''')
                
                conn.commit()
                return True
        except Exception as e:
            print(f"Error creating tasks database: {e}")
            return False

# Create a default instance
# TODO: pass config options here.
db = DatabaseManager('/data2/mbreese/working/pgs-db')

# FastAPI dependency functions
async def get_db():
    """FastAPI dependency for database connection"""
    with db.connection.get_connection() as conn:
        yield conn

def get_database():
    """Get the Database instance for FastAPI"""
    return db

def get_score_repository():
    """Get ScoreRepository instance"""
    return db.scores

def get_ancestry_repository():
    """Get AncestryRepository instance"""
    return db.ancestry

def get_metadata_repository():
    """Get MetadataRepository instance"""
    return db.metadata

def get_task_repository():
    """Get TaskRepository instance"""
    return db.tasks