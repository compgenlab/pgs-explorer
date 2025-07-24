import os
import json
import meilisearch
import json
from typing import List, Dict, Any



## MOVED TO ROUTER.PY




# def process_search(request_data: Dict[str, Any]) -> str:
#     try:
#         existing, html_path, json_path = generate_request_hash(request_data)
#         if existing:
#             return f"/{html_path}"

#         query = request_data.get("name")
#         index = client.index('PGS')


#         # Unsure about the master key for now
#         client = meilisearch.Client('http://localhost:7700', 'aSampleMasterKey')
#         create_PGS_index(client)
#         update_index_settings(client)
#         update_primary_key(client)

#         results = index.search(query)
#         return results

#     except Exception as e:
#         print(f"Error in process_search: {str(e)}")
#         import traceback
#         traceback.print_exc()
#         raise e


# # called function from process_search
# # fill with meili.py things

# # Create the PGS index to place documents in
# def create_PGS_index(client):
#     documents = []

#     # Opens a csv file with all score metadata + metadata from the EFO csv
#     with open('pgs_all_metadata_scores_newenc.csv', mode='r', encoding='utf-8-sig') as file:
#         reader = csv.DictReader(file)
#         for row_num, row in enumerate(reader):
#             try:
#                 documents.append(dict(row))
#             except Exception as e:
#                 print(f"Error at row {row_num}: {e}")

#     # Implicit index creation, aka, MeiliSearch will create
#     # the index upon adding documents to an index that doesn't exist yet
#     client.index('PGS').add_documents(documents)
#     serach(request_data: Dict[str, Any], client)

# # Update the index settings
# # Currently, this is SPECIFICALLY for the index "PGS"
# # However, I'm sure we'll want to make this generic later

# def update_index_settings(client):
#     client.index('PGS').update_displayed_attributes([
#     'Polygenic Score (PGS) ID',
#     'Reported Trait',
#     'Mapped Trait(s) (EFO label)',
#     'Ontology Trait Description'
#     ])


# # Update the primary key if necessary
# # Currently, this is SPECIFICALLY for the index "PGS"
# # with the PGS ID being the key
# # However, I'm sure we'll want to make this generic later
# def update_primary_key(client):
#     client.index('PGS').update(primary_key='Polygenic Score (PGS) ID')