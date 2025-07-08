import React from 'react';
import {
  InstantSearch,
  Hits,
  SearchBox,
  Configure
} from "react-instantsearch";
import { instantMeiliSearch } from '@meilisearch/instant-meilisearch';

const { client } = instantMeiliSearch('https://pgs-search2.compgenlab.org:7700', 'aSampleMasterKey')


const App = () => (
  <div>
    <h1> test tbh </h1>

    
    <InstantSearch
      indexName="pgs-scores"
      client = { client } 
    >
    <SearchBox />
    <InfiniteHits hitComponent={Hit} />

  </InstantSearch>



  </div>
);

const Hit = ({ hit }) => (
  <article key={hit.id}>
    <img src={hit.image} alt={hit.name} />
    <h1>{hit.name}</h1>
    <p>${hit.description}</p>
  </article>
);

export default App