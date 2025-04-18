# TODO - nadia

## Top priority
- [ ]   Move plotly filter py file into app.py
- [ ]   Expand filter logic to work for pca, tsne
- [ ]   Add tsne, basic pca (instead of biplot) 
- [ ]   Add hover texts for svd, pca, tsne

## OR
- [x]   Verify OR calculations - is dongbing method same as method 1?
- [x]   Finish moving OR to backend
- [x]   Hide plot placeholder
- [ ]   Change PlotRequest and PlotResponse (make plot response the consistent return perhaps?)

## Performance 
- [ ]   Speed up mtx calculations
- [ ]   Streamline temp directory size restrictions (one spot for var setting)
- [ ]   Remove "All Samples" option and only use ALL (but this shouldn't be actually querying each id...)
 
## Features
- [ ]   Implement zhiqi score calculation
- [ ]   Add "add data" button + functionality on site
- [ ]   Add match percentage (if data is available)
- [ ]   Create user interface for loading recent cached images
- [ ]   Add sample ids on outlier points in boxplot
- [ ]   Add cohort #s to distribution plot

## Documentation
- [ ]   Add page & function detailed explanations
- [ ]   Implement contextual help (ex: OR functions displayed when selected)

## Repo 
- [ ]   sample/demo database for testing
- [ ]   db to to iu jetstream?