from ..base_repository import BaseRepository

class MetadataRepository(BaseRepository):
    def fetch_pgs_metadata(self, pgs_ids=None):
        """
        Fetch metadata for given PGS IDs
        
        Parameters:
        -----------
        pgs_ids : list, optional
            List of PGS IDs to fetch metadata for
            
        Returns:
        --------
        dict
            Dictionary mapping PGS IDs to their metadata
        """
        if pgs_ids:
            placeholders = ','.join(['?'] * len(pgs_ids))
            query = f"""
                SELECT PGS_ID, PGS_Name, Reported_Trait, PGS_Publication_ID
                FROM pgs_metadata
                WHERE PGS_ID IN ({placeholders})
            """
            params = pgs_ids
        else:
            query = """
                SELECT PGS_ID, PGS_Name, Reported_Trait, PGS_Publication_ID
                FROM pgs_metadata
            """
            params = []

        rows = self.execute_query(query, params)
        
        pgs_metadata = {}
        for row in rows:
            pgs_metadata[row[0]] = {
                "PGS_Name": row[1],
                "Reported_Trait": row[2],
                "Publication_ID": row[3]
            }

        # Check for missing metadata
        if pgs_ids:
            missing_metadata = set(pgs_ids) - set(pgs_metadata.keys())
            if missing_metadata:
                print(f"Warning: {len(missing_metadata)} PGS_IDs don't have metadata")
                for pgs_id in missing_metadata:
                    pgs_metadata[pgs_id] = {
                        'PGS_Name': 'Unknown',
                        'Reported_Trait': 'Unknown',
                        'Publication_ID': 'Unknown'
                    }

        return pgs_metadata

    # For my (ava) purposes:
    def fetch_pgs_metadata_extras(self, pgs_ids=None):
        """
        Fetch metadata for given PGS IDs
        
        Parameters:
        -----------
        pgs_ids : list, optional
            List of PGS IDs to fetch metadata for
            
        Returns:
        --------
        dict
            Dictionary mapping PGS IDs to their metadata
        """
        if pgs_ids:
            placeholders = ','.join(['?'] * len(pgs_ids))
            query = f"""
                SELECT PGS_ID, PGS_Name, Reported_Trait, Mapped_Trait_Label
                FROM pgs_metadata
                WHERE PGS_ID IN ({placeholders})
            """
            params = pgs_ids
        else:
            query = """
                SELECT PGS_ID PGS_Name, Reported_Trait, Mapped_Trait_Label
                FROM pgs_metadata
            """
            params = []

        rows = self.execute_query(query, params)
        
        pgs_metadata = {}
        for row in rows:
            pgs_metadata[row[0]] = {
                "PGS_Name": row[1],
                "Reported_Trait": row[2],
                "Mapped_Trait_Label": row[3]
            }

        # Check for missing metadata
        if pgs_ids:
            missing_metadata = set(pgs_ids) - set(pgs_metadata.keys())
            if missing_metadata:
                print(f"Warning: {len(missing_metadata)} PGS_IDs don't have metadata")
                for pgs_id in missing_metadata:
                    pgs_metadata[pgs_id] = {
                        'PGS_Name': 'Unknown',
                        'Reported_Trait': 'Unknown',
                        "Mapped_Trait_Label": 'Unknown'
                    }

        return pgs_metadata