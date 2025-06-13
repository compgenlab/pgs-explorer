import json
import gzip
import numpy as np
from typing import List, Dict, Any, Optional
from ..base_repository import BaseRepository

class TemporaryScoreRepository(BaseRepository):
    
    def create_temporary_score(self, user_id: str, pgs_id: str, trait: str, scores_data: List[Dict]) -> int:
        """Bulk insert temporary score records."""
        query = """
            INSERT INTO user_temporary_scores (user_id, PGS_ID, SCORE_TYPE, SAMPLE_ID, SCORE, created_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
        """
        
        with self.connection.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(query, scores_data)
            records_count = cursor.rowcount
            conn.commit()
            return records_count
    
    def get_user_temporary_scores(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all PGS IDs uploaded by a user with record counts."""
        query = """
            SELECT PGS_ID, COUNT(*) as record_count, MIN(created_at) as first_upload
            FROM user_temporary_scores 
            WHERE user_id = ? 
            GROUP BY PGS_ID
            ORDER BY first_upload DESC
        """
        rows = self.execute_query(query, [user_id])
        
        return [
            {
                "pgs_id": row[0],
                "record_count": row[1],
                "created_at": row[2]
            }
            for row in rows
        ]
    
    def delete_temporary_pgs(self, pgs_id: str, user_id: str) -> bool:
        """Delete all scores for a specific PGS ID for a user."""
        query = "DELETE FROM user_temporary_scores WHERE PGS_ID = ? AND user_id = ?"
        with self.connection.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, [pgs_id, user_id])
            deleted = cursor.rowcount > 0
            conn.commit()
            return deleted

    def delete_user_temporary_scores(self, user_id: str) -> int:
        """Delete all temporary scores for a user."""
        query = "DELETE FROM user_temporary_scores WHERE user_id = ?"
        with self.connection.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, [user_id])
            deleted_count = cursor.rowcount
            conn.commit()
            return deleted_count

    def get_all_pgs_ids(self, user_id: str) -> List[str]:
        """Get all PGS IDs for user's temporary scores."""
        query = """
            SELECT DISTINCT PGS_ID 
            FROM user_temporary_scores 
            WHERE user_id = ?
            ORDER BY PGS_ID
        """
        rows = self.execute_query(query, [user_id])
        return [row[0] for row in rows]

    def get_all_pgs_with_traits(self, user_id: str) -> List[Dict[str, str]]:
        """Get all PGS IDs with traits for user's temporary scores."""
        query = """
            SELECT DISTINCT PGS_ID 
            FROM user_temporary_scores 
            WHERE user_id = ?
            ORDER BY PGS_ID
        """
        rows = self.execute_query(query, [user_id])
        return [{"id": row[0], "trait": "Temporary"} for row in rows]

    def get_score_types_for_pgs(self, pgs_id: str, user_id: str) -> List[str]:
        """Get distinct score types for a PGS ID from temporary scores."""
        query = """
            SELECT DISTINCT SCORE_TYPE 
            FROM user_temporary_scores 
            WHERE PGS_ID = ? AND user_id = ?
            ORDER BY SCORE_TYPE
        """
        rows = self.execute_query(query, [pgs_id, user_id])
        return [row[0] for row in rows]

    def get_scores_for_pgs(self, pgs_ids, score_type, sample_ids=None, user_id=None):
        """Get scores for one or more PGS IDs."""
        if not isinstance(pgs_ids, list):
            pgs_ids = [pgs_ids]
        
        pgs_placeholders = ','.join(['?'] * len(pgs_ids))
        
        if sample_ids:
            sample_placeholders = ','.join(['?'] * len(sample_ids))
            query = f"""
                SELECT SAMPLE_ID, SCORE
                FROM user_temporary_scores
                WHERE PGS_ID IN ({pgs_placeholders})
                AND SCORE_TYPE = ?
                AND user_id = ?
                AND SAMPLE_ID IN ({sample_placeholders})
            """
            params = pgs_ids + [score_type, user_id] + sample_ids
        else:
            query = f"""
                SELECT SAMPLE_ID, SCORE
                FROM user_temporary_scores
                WHERE PGS_ID IN ({pgs_placeholders})
                AND SCORE_TYPE = ?
                AND user_id = ?
            """
            params = pgs_ids + [score_type, user_id]
        
        rows = self.execute_query(query, params)
        return {row["SAMPLE_ID"]: row["SCORE"] for row in rows}

    def get_all_scores_for_pgs(self, pgs_id: str, user_id: str) -> List[Dict[str, Any]]:
        """Get all scores for a PGS ID across all score types and samples."""
        query = """
            SELECT SAMPLE_ID, SCORE_TYPE, SCORE 
            FROM user_temporary_scores 
            WHERE PGS_ID = ? AND user_id = ?
            ORDER BY SCORE_TYPE, SAMPLE_ID
        """
        rows = self.execute_query(query, [pgs_id, user_id])
        
        return [
            {
                "SAMPLE_ID": row[0],
                "SCORE_TYPE": row[1],
                "SCORE": row[2]
            }
            for row in rows
        ]

    def get_score_matrix(self, sample_ids, pgs_ids, score_type, user_id,
                         output_format="dict", handle_missing=False,
                         upper_threshold=None, lower_threshold=None):
        """Retrieve scores and construct a matrix."""
        if sample_ids and pgs_ids:
            sample_placeholders = ','.join(['?'] * len(sample_ids))
            pgs_placeholders = ','.join(['?'] * len(pgs_ids))
            query = f"""
                SELECT SAMPLE_ID, PGS_ID, SCORE
                FROM user_temporary_scores
                WHERE SCORE_TYPE = ?
                AND user_id = ?
                AND SAMPLE_ID IN ({sample_placeholders})
                AND PGS_ID IN ({pgs_placeholders})
            """
            params = [score_type, user_id] + sample_ids + pgs_ids
        elif sample_ids:
            sample_placeholders = ','.join(['?'] * len(sample_ids))
            query = f"""
                SELECT SAMPLE_ID, PGS_ID, SCORE
                FROM user_temporary_scores
                WHERE SCORE_TYPE = ?
                AND user_id = ?
                AND SAMPLE_ID IN ({sample_placeholders})
            """
            params = [score_type, user_id] + sample_ids
        elif pgs_ids:
            pgs_placeholders = ','.join(['?'] * len(pgs_ids))
            query = f"""
                SELECT SAMPLE_ID, PGS_ID, SCORE
                FROM user_temporary_scores
                WHERE SCORE_TYPE = ?
                AND user_id = ?
                AND PGS_ID IN ({pgs_placeholders})
            """
            params = [score_type, user_id] + pgs_ids
        else:
            query = """
                SELECT SAMPLE_ID, PGS_ID, SCORE
                FROM user_temporary_scores
                WHERE SCORE_TYPE = ?
                AND user_id = ?
            """
            params = [score_type, user_id]

        # Execute query and build dictionary
        data_dict = {}
        rows = self.execute_query(query, params)
        
        for row in rows:
            sample_id = row[0]
            pgs_id = row[1]
            score = row[2]
            
            # Apply thresholds if provided
            if upper_threshold is not None and score > upper_threshold:
                score = upper_threshold
            elif lower_threshold is not None and score < lower_threshold:
                score = lower_threshold
                
            if sample_id not in data_dict:
                data_dict[sample_id] = {}
            data_dict[sample_id][pgs_id] = score
        
        # Rest of the numpy conversion logic stays the same...
        if output_format == "numpy":
            available_samples = list(data_dict.keys())
            available_pgs = set()
            for sample_scores in data_dict.values():
                available_pgs.update(sample_scores.keys())
            available_pgs = list(available_pgs)
            
            if sample_ids:
                final_samples = [s for s in sample_ids if s in available_samples]
            else:
                final_samples = available_samples
            
            if pgs_ids:
                final_pgs = [p for p in pgs_ids if p in available_pgs]
            else:
                final_pgs = available_pgs
            
            sample_to_index = {sample_id: i for i, sample_id in enumerate(final_samples)}
            pgs_to_index = {pgs_id: j for j, pgs_id in enumerate(final_pgs)}
                
            matrix = np.full((len(final_samples), len(final_pgs)), np.nan)
    
            for sample_id, pgs_scores in data_dict.items():
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
            return data_dict, list(data_dict.keys())

def get_score_by_cohorts(self, pgs_id, score_type, cohorts, user_id):
    """Get scores for a PGS ID, grouped by cohorts."""
    score_dict = self.get_scores_for_pgs(pgs_id, score_type, user_id=user_id)
    
    cohort_data = []
    for cohort in cohorts:
        if "name" not in cohort:
            continue
            
        if cohort["name"] != "ALL":
            if "sample_ids" not in cohort:
                print(f"Warning: cohort '{cohort['name']}' missing sample_ids")
                continue
                
            valid_samples = [
                {"SAMPLE_ID": sample_id, "SCORE": score_dict[sample_id]}
                for sample_id in cohort["sample_ids"]
                if sample_id in score_dict
            ]
        else:
            valid_samples = [
                {"SAMPLE_ID": sample_id, "SCORE": score}
                for sample_id, score in score_dict.items()
            ]
            
        cohort_scores = [sample["SCORE"] for sample in valid_samples]
        
        cohort_data.append({
            "color": cohort.get("color", "#000000"),
            "values": cohort_scores,
            "samples": valid_samples,
            "name": cohort["name"]
        })

    return cohort_data

def get_sample_ids_with_scores(self, score_type, pgs_ids, user_id):
    """Get all sample IDs that have scores for the given PGS IDs and score type."""
    if not isinstance(pgs_ids, list):
        pgs_ids = [pgs_ids]
    
    pgs_placeholders = ','.join(['?'] * len(pgs_ids))
    query = f"""
        SELECT DISTINCT SAMPLE_ID 
        FROM user_temporary_scores 
        WHERE SCORE_TYPE = ? 
        AND user_id = ?
        AND PGS_ID IN ({pgs_placeholders})
        ORDER BY SAMPLE_ID
    """
    params = [score_type, user_id] + pgs_ids
    rows = self.execute_query(query, params)
    return [row[0] for row in rows]

def get_score_statistics_with_outliers(self, score_type, pgs_ids, user_id, std_dev_threshold=None):
    """Calculate comprehensive statistics for scores including outlier counts."""
    if not isinstance(pgs_ids, list):
        pgs_ids = [pgs_ids]
    
    pgs_placeholders = ','.join(['?'] * len(pgs_ids))
    
    # Get basic statistics
    query = f"""
        SELECT 
            AVG(SCORE) as avg, 
            MIN(SCORE) as min, 
            MAX(SCORE) as max, 
            SQRT(AVG(SCORE * SCORE) - AVG(SCORE) * AVG(SCORE)) AS stdev,
            COUNT(*) as count
        FROM user_temporary_scores
        WHERE SCORE_TYPE = ? 
        AND user_id = ?
        AND PGS_ID IN ({pgs_placeholders})
    """
    params = [score_type, user_id] + pgs_ids
    row = self.execute_query_single(query, params)
    
    if not row or row['count'] == 0:
        return {
            'avg': 0,
            'min': 0,
            'max': 0,
            'stdev': 1.0,
            'count': 0,
            'outlier_count': 0
        }
    
    stats = {
        'avg': row['avg'],
        'min': row['min'],
        'max': row['max'],
        'stdev': row['stdev'] if row['stdev'] is not None else 1.0,
        'count': row['count']
    }
    
    # Calculate outliers if threshold provided
    if std_dev_threshold is not None:
        upper_threshold = stats['avg'] + (std_dev_threshold * stats['stdev'])
        lower_threshold = stats['avg'] - (std_dev_threshold * stats['stdev'])
        
        # Count outliers
        outlier_query = f"""
            SELECT COUNT(*)
            FROM user_temporary_scores
            WHERE SCORE_TYPE = ? 
            AND user_id = ?
            AND PGS_ID IN ({pgs_placeholders})
            AND (SCORE > ? OR SCORE < ?)
        """
        outlier_params = [score_type, user_id] + pgs_ids + [upper_threshold, lower_threshold]
        outlier_count = self.execute_query_scalar(outlier_query, outlier_params) or 0
        
        stats.update({
            'outlier_count': outlier_count,
            'upper_threshold': upper_threshold,
            'lower_threshold': lower_threshold
        })
    
    return stats

def get_score_statistics(self, score_type, pgs_ids, user_id):
    """Calculate basic statistics for scores (backward compatibility)."""
    stats = self.get_score_statistics_with_outliers(score_type, pgs_ids, user_id)
    return (stats['avg'], stats['min'], stats['max'], stats['stdev'])

def count_outliers(self, score_type, pgs_ids, upper_threshold, lower_threshold, user_id):
    """Count outliers in the dataset (backward compatibility)."""
    if not isinstance(pgs_ids, list):
        pgs_ids = [pgs_ids]
    
    pgs_placeholders = ','.join(['?'] * len(pgs_ids))
    query = f"""
        SELECT COUNT(*)
        FROM user_temporary_scores
        WHERE SCORE_TYPE = ? 
        AND user_id = ?
        AND PGS_ID IN ({pgs_placeholders})
        AND (SCORE > ? OR SCORE < ?)
    """
    params = [score_type, user_id] + pgs_ids + [upper_threshold, lower_threshold]
    return self.execute_query_scalar(query, params) or 0