from fastapi import APIRouter, Request, BackgroundTasks
from fastapi.responses import HTMLResponse
from apps.core.config import templates
from apps.search.models import SearchRequest
# from apps.search.models import Federation
from apps.search.models import QueryItem

import meilisearch
import json
import csv  

# Router name
router = APIRouter(tags=["search"])

# Probably could rename from "distribution_view", doesn't cause an issue at the moment though
@router.get("/search", response_class=HTMLResponse)
async def distribution_view(request: Request):
    return templates.TemplateResponse("search.html", {"request": request})


@router.post('/api/submit_search')
def submit_search(request_data: SearchRequest):
    # search_term = request_data.search_term # FOR SINGLE SEARCH

    # LOAD FOR (now non-)FEDERATED MULTI-SEARCH
    search_payload = {
        "queries": [
            {
                "indexUid": query.indexUid, 
                "q": query.query,
                "limit": query.limit,
                "offset": query.offset
            } 
            for query in request_data.multi_queries
        ]#,
        # "federation": {
        #     "limit": request_data.federation.limit,
        #     "offset": request_data.federation.offset
        # }
    }

    
    # Unsure about the master key for now
    client = meilisearch.Client('http://localhost:7700', 'aSampleMasterKey')
    
    index = client.index('PGS')

    # Not sure if the following should be commented out by now

    ## CREATES PGS ##
    # create_PGS_index(client)

    ## UPDATES SETTINGS (not PK) ###

    # General Settings #
       # Use for updating displayed bits
    #update_index_settings(client)
    
    # UNCOMMENT IF YOU NEED TO UPDATE THE PRIMARY KEY. GO TO THE FUNCTION TO CHANGE THE KEY
    # update_primary_key(client)


    # Search for term (SINGLE SEARCH)
    # results = index.search(search_term, {"limit": request_data.limit, "offset": request_data.offset})

    results = client.multi_search(**search_payload) # MULTI-SEARCH
    return results

# Create the PGS index to place documents in
def create_PGS_index(client):
    documents = []

    # Opens a csv file with all score metadata + metadata from the EFO csv
    with open('pgs_all_metadata_scores_newenc.csv', mode='r', encoding='utf-8-sig') as file:
        reader = csv.DictReader(file)
        for row_num, row in enumerate(reader):
            try:
                documents.append(dict(row))
            except Exception as e:
                print(f"Error at row {row_num}: {e}")

    # Implicit index creation, aka, MeiliSearch will create
    # the index upon adding documents to an index that doesn't exist yet
    client.index('PGS').add_documents(documents)

# Update the index settings
# Currently, this is SPECIFICALLY for the index "PGS"
# However, I'm sure we'll want to make this generic later

def update_index_settings(client):
    client.index('PGS').update_displayed_attributes([
    'Polygenic Score (PGS) ID',
    'Reported Trait',
    'Mapped Trait(s) (EFO label)'
    ])

    client.index('PGS').update_settings({
        'pagination': {
            'maxTotalHits': 5000
        },
    })


# Update the primary key if necessary
# Currently, this is SPECIFICALLY for the index "PGS"
# with the PGS ID being the key
# However, I'm sure we'll want to make this generic later
def update_primary_key(client):
    client.index('PGS').update(primary_key='Polygenic Score (PGS) ID')
