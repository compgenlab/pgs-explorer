import meilisearch
import json
import csv  

# Unsure about the master key for now
client = meilisearch.Client('http://localhost:7700', 'aSampleMasterKey')

# The block below was opening the csv file and parsing it to add the rows as 
# documents to the index called 'scores'

# documents = []

# with open('pgs_all_metadata_scores_newenc.csv', mode='r', encoding='utf-8-sig') as file:
#     reader = csv.DictReader(file)
#     for row_num, row in enumerate(reader):
#         try:
#             documents.append(dict(row))
#         except Exception as e:
#             print(f"Error at row {row_num}: {e}")

# client.index('PGS').update(primary_key='Polygenic Score (PGS) ID')
# client.index('PGS').add_documents(documents)

# Check status of task, mainly I used this to see if documents were being added
# status = client.get_task(127)
# print(status)

# We will want to trim the results displayed, though; use CSV columns
# client.index('PGS').update_displayed_attributes([
#     'Polygenic Score (PGS) ID',
#     'Reported Trait',
#     'Mapped Trait(s) (EFO label)',
#     'Ontology Trait Description'
# ])

# Print the search results
# p = client.index('PGS').search('breast') # Typo tolerance is on by default
# print(p)


