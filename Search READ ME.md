Written 7/22/2025 by Ava Havrilesko

## Relevant Resources
* [Meilisearch Documentation](<https://www.meilisearch.com/docs/home>)
* [FastAPI](https://fastapi.tiangolo.com/)

## Purpose

The purpose of this page/widget is to offer an easier method for searching for, displaying, and selecting Polygenic Scores for use throughout the PGS Visualizer webpage. The page utilizes Meilisearch to do so by querying against a version of *pgs_all_metadata_scores.csv* combined with *pgs_all_metadata_efo_traits.csv* (from [Index of /pub/databases/spot/pgs/metadata](<https://ftp.ebi.ac.uk/pub/databases/spot/pgs/metadata/>)) joined on their EFO ID (columns named 'Mapped Trait(s) (EFO ID)' and 'Ontology Trait ID' respectively).

## Current Page Function

Currently, the page functions as follows:

1. Upon entering the search bar, users can query *single-word* terms or a full PGS ID such as PGS000001 to search for scores. When `SPACE` is pressed, the search is sent and the term is stored in a pill. 
	1. The form can also conditionally be submitted on `ENTER` if things need refreshed when removing terms (see: searching the terms "Breast" and "Hand", moving to page 2, and removing "Breast" - hit `ENTER` to refresh the search to see results for "Hand" (this is not intended but is not fixed yet)), however,`SPACE`  <u>must be pressed first to add a term to a pill, otherwise it will not work </u> as the search pulls the query keywords from the pills.
	2. `SPACE`-based searching may need to change so that we can include multi-word terms (e.g. "breast cancer"). The change should be made to a more live search.
	3. Pills can also be removed to remove related results. This is independent of the selected ID pill removal.
	4. Currently, all fields are *searchable*, but not all fields are *displayed.* This allows both keyword and ID search. For the difference between *searchable* and *displayed* fields, see [Displayed and searchable attributes](<https://www.meilisearch.com/docs/learn/relevancy/displayed_searchable_attributes>)
		1. Current Displayed fields include those on the UI cards, i.e.:
			* Polygenic Score (PGS) ID
			* Reported Trait
			* Mapped Trait(s) (EFO label) / Ontology Trait ID
		2. Current Searchable fields include:
		    * Polygenic Score (PGS) ID
			* PGS Name
			* Reported Trait
			* Mapped Trait(s) (EFO label) / Ontology Trait ID
			* PGS Development Method
			* PGS Development Details/Relevant Parameters
			* Original Genome Build
			* Number of Variants
			* Type of Variant Weight
			* PGS Publication (PGP) ID
			* Publication (PMID)
			* Publication (doi)
			* Score and results match the original publication
			* Ancestry Distribution (%) - Source of Variant Associations (GWAS)
			* Ancestry Distribution (%) - Score Development/Training
			* Ancestry Distribution (%) - PGS Evaluation
			* FTP link
			* Release Date
			* License/Terms of Use
			* Ontology Trait Label
			* Ontology Trait Description (technically, although not necessarily possible due to the one-word nature of the search at the moment)
			* Ontology URL
		3. By default, all attributes are automatically added to the `searchableAttributes` list in their order of appearance, but a strong case can be made for adjusting these fields to limit the search range. Changing the searchable fields would require a small amount of work. See [Searchable fields](<https://www.meilisearch.com/docs/learn/relevancy/displayed_searchable_attributes#searchable-fields>)

2. If the list of results is *greater than* 15 (the `LIMIT` chosen by me (Ava Havrilesko) but adjustable by editing the push to the `multiQueries` array), "Next" and "Previous" buttons allow users to navigate the result pages
	1. If the list is *less than* 15, users are not presented with navigation buttons. 
	2. If the first term has less than 15 results (e.g. the term "hand" will return 12 results currently) and consecutive terms increase the total result count to be *greater than* 15, then the buttons should appear. Similarly, if the term that brought the count past 15 is removed, the buttons should disappear.
	3. When the buttons are clicked, the list should be re-searched based on the `OFFSET`, calculated by multiplying the page number by the `LIMIT`; 'Next' should add by this number, 'Previous' should subtract. This is handled by `updatePageNumber`. 
	4. For more information on `LIMIT`, `OFFSET`, and `Pagination`, see Meilisearch's [Search result pagination](<https://www.meilisearch.com/docs/guides/front_end/pagination>)

3. When displayed, users should be able to click on a result which adds it to another set of pills.
	1. Currently, this *only* stores the PGS ID and should be changed later to send all the relevant data needed. This functionality was not implemented as I (Ava Havrilesko) wasn't sure what would be needed in every scenario that may require this code.
	2. Pills can also be removed. This is independent of the keyword pill removal. Cases can be made for both independent and dependent removals, though.
	3. Users should only be able to click each result once to avoid duplicate additions.

## Meilisearch

See [[#Relevant Resources]] at the top for a link to the main documentation page.

Currently, this use of Meilisearch utilizes Docker (see [Using Meilisearch with Docker](<https://www.meilisearch.com/docs/guides/docker>)) and a self-hosted approach (see [Getting started with self-hosted Meilisearch](<https://www.meilisearch.com/docs/learn/self_hosted/getting_started_with_self_hosted_meilisearch>)). It does *not* currently use Meilisearch Cloud.

#### Related Meilisearch functions and parts

Code includes parts such as:
* `create_PGS_index(client)`: Currently commented out, this passes the client connection to a function that reads in from the combined metadata file and stores the information in an array, `documents`, and utilizes `client.index('PGS').add_documents(documents)` to add information from the *array* `documents` to [documents](<https://www.meilisearch.com/docs/learn/getting_started/documents>) in the [index](https://www.meilisearch.com/docs/learn/getting_started/indexes) 'PGS'. Doing so [implicitly creates the index](https://www.meilisearch.com/docs/learn/getting_started/indexes#implicit-index-creation) 'PGS'. Read further for explicit index creation.
* `update_index_settings(client)`: Currently commented out, this passes the client connection into a function to change the index settings, which currently only utilizes `client.index('PGS').update_displayed_attributes` to update the displayed attributes. See [Settings](<https://www.meilisearch.com/docs/reference/api/settings>) for other options to adjust index settings.
* `update_primary_key(client)`: Currently commented out, this passes the client connection into a function to specifically change the 'PGS' index primary key. A whole function was probably not necessary, but see [Primary key](<https://www.meilisearch.com/docs/learn/getting_started/primary_key>) for relevant information
* `results = client.multi_search(**search_payload)`: calls Meilisearch's `multi_search` and sends `search_payload`, a payload set up for a non-federated search including `queries` (must be an array of objects. Here, the parameters line up with the Pydantic model `QueryItem`). Another section is commented out should there be a need to return for a federated search. See [Multi-search](https://www.meilisearch.com/docs/reference/api/multi_search) for details on federated searches.

### How to start the page

Currently, it only requires running the following:

1. Having a web server for the page running (say, a version of https://pgs-vis2.compgenlab.org/ that includes the code). Currently, I use uvicorn for this.
	1. ` venv/bin/python -m uvicorn app:app --host 0.0.0.0 --port 5001`
2. Running the connected Meilisearch server with Docker. Currently, we have no master key needed.
	1. `docker run -it --rm -p 7700:7700 -v $(pwd)/meili_data:/meili_data getmeili/meilisearch:v1.15`
3. Visiting the connected URL (e.g.  https://pgs-vis2.compgenlab.org/search).

## Known Bugs & Other Misfunctions

1. Issue with the list not refreshing/pagination from the Current Page Functions section: searching the terms "Breast" and "Hand", moving to page 2, and removing "Breast" - hit `ENTER` to refresh the search to see results for "Hand" (this is not intended but is not fixed yet). The fix should take users back to Page 1

2. Search results should (probably) be updated from searching on `SPACE` to on keydown/press.

3.  Typos such as `"hand` don't remove results. Results will show for *hand* but will not go away.


## Final Thoughts

#### Opinions on feasibility

I think in general having a search bar for this magnitude of results is a good idea, and I think Meilisearch seems to be working well enough—in any other case, the dropdown we have or any other kind of list would have been better for selectable items.

In terms of what I coded, I think it's *okay.* Personally, I'm not entirely sure how usable it is when integrated with other pages. By itself, I think it's pretty straightforward, but the entire site could use usability studies to make sure things function as *expected,* not just intended.

I say this because while I can break things up into pages when it's separated from the rest of the site and add buttons and a scrollbox, I see potential UI/UX issues when integrated into pages like Distribution. The way it's set up via dropdown is pretty clean on the outside, but completely overwhelming on the inside. Being able to search for things makes things a lot less laborious, but it's the display of the results that gets me. We'd have to add a whole new section to display them the way it's currently coded, especially if we also want to include the page buttons. I think it shouldn't be so bad—maybe we can have a section cover the screen temporarily to scroll on? I think instead of page buttons it could change to instead scroll vertically, but the next "page" loads when you get to the "bottom" of the first. However it gets displayed, there's a good few scores/terms that have over 100 results, any way we try to display that might be tough. 

#### Next Steps

Like I mentioned earlier:

1. Adjust the display of results to better integrate into the different pages where it's needed. The `LIMIT` was just a number of my own opinion and can be changed. Whether or not the search was federated was changed in order to accommodate my pill boxes (but as seen in my code, I went for a federated approach first and maybe it could still work).

2. Adjust the code so that it actually sends useful data for the page it's integrated into instead of only collecting the PGS ID

3.  Adjust the method in which the code populates the list, since we may need to include phrases. That is, how can we still specifically search for "ER-Positive Breast Cancer" if all we can type is "ER-Positive"? Maybe return to on `ENTER` or, as I mentioned earlier, we need a live update on key up/down instead.