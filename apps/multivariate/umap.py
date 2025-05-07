import os
import json
import hashlib
import sqlite3
import numpy as np
from datetime import datetime
import plotly.graph_objects as go
import umap
# from apps.core.database import DB_PATH
# from apps.database.service import fetch_pgs_ids, fetch_pgs_metadata, sample_ids_by_cohort
from apps.multivariate.service import get_matrix

def process_umap(request_data):
    try:
        # Create temp directory if it doesn't exist
        os.makedirs("temp", exist_ok=True)
        
        # Extract parameters from request_data
        score_type = request_data["score_type"]
        n_neighbors = request_data["n_neighbors"]
        min_dist = request_data["min_dist"]
        pgs_ids = request_data.get("pgs_ids", None)
        cohort = request_data["cohort"]
        view_type = request_data["view_type"]
        
        # Generate hash based on request parameters
        request_hash = generate_umap_hash(
            score_type,
            n_neighbors,
            min_dist,
            pgs_ids,
            cohort,
            view_type  
        )

        print(f"Request hash: {request_hash}")

        # Check if we already have a file with this hash
        for filename in os.listdir("temp"):
            if filename.endswith(".html") and request_hash in filename and "umap" in filename:
                # Found a cached file, update its access time
                cached_filepath = os.path.join("temp", filename)
                os.utime(cached_filepath)
                
                print(f"Using cached UMAP: {filename}")
                
                # Return file path
                return f"/temp/{filename}"

        # Parameters for hash
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        score_type_safe = score_type.replace("/", "_").replace("\\", "_")
        cohort_indicator = f"{cohort}_" if cohort and cohort != "ALL" else ""
        view_indicator = f"{view_type}_"  # Add view type to filename
        filename = f"umap_{cohort_indicator}{view_indicator}{score_type_safe}_{request_hash}_{timestamp}.html"
        filepath = os.path.join("temp", filename)
        
        # Generate UMAP
        fig, stats = generate_umap_html(
            score_type=score_type,
            n_neighbors=n_neighbors,
            min_dist=min_dist,
            specific_pgs_ids=pgs_ids,
            cohort=cohort,
            view_type=view_type
        )
        
        # Save the visualization
        fig.write_html(
            filepath,
            include_plotlyjs='cdn',    
            include_mathjax=False,    
            config={
                'displayModeBar': False,  
                'responsive': True        
            }
        )
        
        # Return the file path
        return f"/temp/{filename}"
        
    except Exception as e:
        # Log the error
        print(f"Error generating UMAP: {str(e)}")
        raise e

def generate_umap_html(score_type, n_neighbors=15, min_dist=0.1, specific_pgs_ids=None, cohort=None, view_type="sample"):
    """
    Generate a UMAP visualization for PGS score data.
    
    Parameters:
    - score_type: The SCORE_TYPE to filter on
    - n_neighbors: Number of neighbors for UMAP (default: 15)
    - min_dist: Minimum distance for UMAP (default: 0.1)
    - specific_pgs_ids: List of specific PGS IDs to include
    - cohort: Name of cohort to filter samples (optional)
    
    Returns:
    - fig: Plotly figure object
    - stats: Tuple containing statistics about the data
    """
    print(f"=== Generating UMAP Visualization ===")
    print(len(specific_pgs_ids))
    print(f"View Type: {view_type}")
    print(f"Score Type: {score_type}")
    
    # Database connection and data retrieval 
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get PGS IDs 
    pgs_ids = fetch_pgs_ids(specific_pgs_ids, score_type)

    # Get metadata for PGS IDs
    pgs_metadata = fetch_pgs_metadata(pgs_ids)
    
    # Modified sample ID fetching with cohort filtering
    print("Getting all SAMPLE_IDs for the selected PGS_IDs...")
    
    # Get sample IDs
    sample_ids = sample_ids_by_cohort(cohort)
    print(f"Found {len(sample_ids)} unique SAMPLE_IDs.")
    
    if cohort and cohort != "ALL":
        print(f"Using {len(sample_ids)} samples from {cohort} cohort.")
    
    data_dict, _ = get_matrix(
        sample_ids=sample_ids,
        pgs_ids=pgs_ids,
        score_type=score_type,
        output_format="dict"  
    )

    # Close database connection
    conn.close()

    # Branch based on view_type
    if view_type == "sample":
        # Original sample-based UMAP - mostly unchanged
        return generate_sample_based_umap(
            sample_ids, pgs_ids, data_dict, n_neighbors, min_dist, 
            score_type, cohort
        )
    else:  # "score" view type
        # New score-based UMAP
        return generate_score_based_umap(
            sample_ids, pgs_ids, data_dict, n_neighbors, min_dist, 
            score_type, cohort, pgs_metadata
        )

def generate_sample_based_umap(sample_ids, pgs_ids, data_dict, n_neighbors, min_dist, score_type, cohort):
    print("Creating matrix for clustering...")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create a numpy matrix with NaN for missing values
    matrix = np.full((len(sample_ids), len(pgs_ids)), np.nan)
    for i, sample_id in enumerate(sample_ids):
        for j, pgs_id in enumerate(pgs_ids):
            if pgs_id in data_dict[sample_id]:
                matrix[i, j] = data_dict[sample_id][pgs_id]
    
    # Apply UMAP for dimensionality reduction
    print("Applying UMAP dimensionality reduction...")
    
    # Handle missing values before UMAP
    matrix_for_umap = np.copy(matrix)
    for j in range(matrix_for_umap.shape[1]):
        col_mean = np.nanmean(matrix_for_umap[:, j])
        mask = np.isnan(matrix_for_umap[:, j])
        matrix_for_umap[mask, j] = col_mean
    
    # Import and create UMAP
    reducer = umap.UMAP(
        n_neighbors=n_neighbors,
        min_dist=min_dist,
        n_components=2,
        random_state=42
    )
    
    # Apply UMAP to get 2D embedding
    embedding = reducer.fit_transform(matrix_for_umap)
    
    # Calculate statistics for color mapping
    all_scores = [score for sample in data_dict.values() for score in sample.values()]
    min_score = min(all_scores)
    max_score = max(all_scores)
    
    # Create hover text for points
    hover_text = []
    for i, sample_id in enumerate(sample_ids):
        avg_score = np.nanmean([data_dict[sample_id].get(pgs_id, np.nan) for pgs_id in pgs_ids])
        cursor.execute('SELECT population FROM ancestry WHERE sample_id = ?', (sample_id,))
        result = cursor.fetchone()
        ancestry = result[0] if result else 'Unknown'
        hover_info = f"Sample: {sample_id}<br>Ancestry: {ancestry}<br>Avg Score: {avg_score:.4f}"
        hover_text.append(hover_info)
    
    # Create UMAP scatter plot
    print("Creating UMAP visualization...")
    cohort_text = f" - {cohort} Cohort" if cohort and cohort != "ALL" else ""
    title = f'UMAP of {score_type} Scores{cohort_text}<br>({len(pgs_ids)} PGS_IDs, {len(sample_ids)} Samples)'
    print(f"embedding: {embedding.shape}")
    print(f"PGS_IDs count: {len(pgs_ids)}, Sample count: {len(sample_ids)}")

    # Create a color scale based on average score per sample
    avg_scores = [np.nanmean([data_dict[sample_id].get(pgs_id, np.nan) for pgs_id in pgs_ids]) for sample_id in sample_ids]
    
    fig = go.Figure(data=go.Scatter(
        x=embedding[:, 0],
        y=embedding[:, 1],
        mode='markers',
        marker=dict(
            size=5,
            color=avg_scores,
            colorscale='Viridis',
            colorbar=dict(
                title=f'Avg {score_type} Score'
            ),
            showscale=True
        ),
        text=hover_text,
        hoverinfo='text'
    ))
    
    # Configure layout
    fig.update_layout(
        title=title,
        xaxis=dict(
            title='UMAP Dimension 1',
            showgrid=True,
            zeroline=False,
        ),
        yaxis=dict(
            title='UMAP Dimension 2',
            showgrid=True,
            zeroline=False,
        ),
        width=1000,
        height=800,
        autosize=False,
        margin=dict(l=20, r=20, t=80, b=20),
        plot_bgcolor='white',
        paper_bgcolor='white',
        hovermode='closest'
    )
    
    # Add customized hover behavior
    fig.update_layout(
        hoverlabel=dict(
            bgcolor="white",
            font_size=12,
            font_family="Arial"
        )
    )
    
    # Close database connection
    conn.close()

    # Return statistics (keeping the same structure as your original function)
    stats = (None)
    return fig, stats

def generate_score_based_umap(sample_ids, pgs_ids, data_dict, n_neighbors, min_dist, score_type, cohort, pgs_metadata):
    """Generate UMAP where each point is a PGS score"""
    print("Creating matrix for score-based clustering...")
    
    # Transpose the matrix - now rows are PGS IDs and columns are samples
    matrix = np.full((len(pgs_ids), len(sample_ids)), np.nan)
    for i, pgs_id in enumerate(pgs_ids):
        for j, sample_id in enumerate(sample_ids):
            if pgs_id in data_dict[sample_id]:
                matrix[i, j] = data_dict[sample_id][pgs_id]
    
    # Handle missing values
    matrix_for_umap = np.copy(matrix)
    for j in range(matrix_for_umap.shape[1]):
        col_mean = np.nanmean(matrix_for_umap[:, j])
        mask = np.isnan(matrix_for_umap[:, j])
        matrix_for_umap[mask, j] = col_mean
    
    # Apply UMAP
    reducer = umap.UMAP(
        n_neighbors=min(n_neighbors, len(pgs_ids) - 1),  # Adjust neighbors if needed
        min_dist=min_dist,
        n_components=2,
        random_state=42
    )
    
    embedding = reducer.fit_transform(matrix_for_umap)
    
    # Create hover text for points
    hover_text = []
    for i, pgs_id in enumerate(pgs_ids):
        # Get metadata for this PGS ID
        metadata = pgs_metadata.get(pgs_id, {
            'PGS_Name': 'Unknown',
            'Reported_Trait': 'Unknown',
            'Publication_ID': 'Unknown'
        })
        
        # Calculate average score for this PGS ID across samples
        scores = [data_dict[sample_id].get(pgs_id, np.nan) for sample_id in sample_ids]
        avg_score = np.nanmean([s for s in scores if not np.isnan(s)])
        
        hover_info = (
            f"PGS ID: {pgs_id}<br>"
            f"Name: {metadata['PGS_Name']}<br>"
            f"Trait: {metadata['Reported_Trait']}<br>"
            f"Publication: {metadata['Publication_ID']}<br>"
            f"Avg Score: {avg_score:.4f}"
        )
        hover_text.append(hover_info)
    
    # Create UMAP scatter plot
    cohort_text = f" - {cohort} Cohort" if cohort and cohort != "ALL" else ""
    title = f'Score-based UMAP of {score_type} Scores{cohort_text}<br>({len(pgs_ids)} PGS_IDs across {len(sample_ids)} Samples)'
    
    # Get traits for coloring 
    traits = [pgs_metadata.get(pgs_id, {}).get('Reported_Trait', 'Unknown') for pgs_id in pgs_ids]
    unique_traits = list(set(traits))
    
    # Create a colormap
    color_indices = [unique_traits.index(trait) for trait in traits]
    
    fig = go.Figure(data=go.Scatter(
        x=embedding[:, 0],
        y=embedding[:, 1],
        mode='markers',
        marker=dict(
            size=8,
            color=color_indices,
            colorscale='Rainbow',  # Different colorscale for scores
            showscale=False
        ),
        text=hover_text,
        hoverinfo='text'
    ))
    
    # Configure layout
    fig.update_layout(
        title=title,
        xaxis=dict(title='UMAP Dimension 1', showgrid=True, zeroline=False),
        yaxis=dict(title='UMAP Dimension 2', showgrid=True, zeroline=False),
        width=1000, height=800, autosize=False,
        margin=dict(l=20, r=20, t=80, b=20),
        plot_bgcolor='white', paper_bgcolor='white',
        hovermode='closest',
        hoverlabel=dict(bgcolor="white", font_size=12, font_family="Arial")
    )
    
    stats = (None)
    return fig, stats

def generate_umap_hash(score_type, n_neighbors, min_dist, pgs_ids, cohort, view_type):
    """Generate a consistent hash based on UMAP request parameters."""
    params = {
        "score_type": score_type,
        "n_neighbors": n_neighbors,
        "min_dist": min_dist,
        "pgs_ids": sorted(pgs_ids) if pgs_ids else [],
        "cohort": cohort,
        "view_type": view_type  
    }

    # Convert to JSON string
    param_str = json.dumps(params, sort_keys=True)
    
    # Generate hash
    hash_obj = hashlib.md5(param_str.encode())
    return hash_obj.hexdigest()
