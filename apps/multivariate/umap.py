import os
import json
import hashlib
import numpy as np
from datetime import datetime
import plotly.graph_objects as go
import umap
from database import db

def process_umap(request_data):
    """Main entry point for UMAP visualization generation."""
    try:
        # Create temp directory if it doesn't exist
        os.makedirs("temp", exist_ok=True)
        
        # Extract and validate parameters
        params = extract_umap_parameters(request_data)
        
        # Generate hash for caching
        request_hash = generate_umap_hash(**params)
        print(f"Request hash: {request_hash}")
        
        # Check for cached result
        cached_file = check_umap_cache(request_hash)
        if cached_file:
            return cached_file
        
        # Generate UMAP visualization
        fig, stats = generate_umap_visualization(**params)
        
        # Save and return file path
        filepath = save_umap_visualization(fig, params, request_hash)
        return filepath
        
    except Exception as e:
        print(f"Error generating UMAP: {str(e)}")
        raise e

def extract_umap_parameters(request_data):
    """Extract and validate UMAP parameters from request data."""
    return {
        'score_type': request_data["score_type"],
        'n_neighbors': request_data["n_neighbors"],
        'min_dist': request_data["min_dist"],
        'specific_pgs_ids': request_data.get("pgs_ids"),
        'cohort': request_data["cohort"],
        'view_type': request_data["view_type"],
        'user_id': request_data['user_id']
    }

def generate_umap_hash(score_type, n_neighbors, min_dist, specific_pgs_ids, cohort, view_type, user_id):
    """Generate a hash for the UMAP request parameters."""
    hash_input = json.dumps({
        "score_type": score_type,
        "pgs_ids": sorted(specific_pgs_ids) if specific_pgs_ids else "all",
        "cohort": cohort if cohort else "ALL",
        "view_type": view_type,
        "n_neighbors": n_neighbors,
        "min_dist": min_dist,
        "user_id": user_id
    }, sort_keys=True)
    
    return hashlib.md5(hash_input.encode()).hexdigest()

def check_umap_cache(request_hash):
    """Check if UMAP visualization is already cached."""
    for filename in os.listdir("temp"):
        if filename.endswith(".html") and request_hash in filename and "umap" in filename:
            cached_filepath = os.path.join("temp", filename)
            os.utime(cached_filepath)
            print(f"Using cached UMAP visualization: {filename}")
            return f"/temp/{filename}"
    return None

def save_umap_visualization(fig, params, request_hash):
    """Save UMAP visualization to HTML file."""
    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    score_type_safe = params['score_type'].replace("/", "_").replace("\\", "_")
    cohort_indicator = f"{params['cohort']}_" if params['cohort'] and params['cohort'] != "ALL" else ""
    view_indicator = f"{params['view_type']}_"
    filename = f"umap_{cohort_indicator}{view_indicator}{score_type_safe}_{request_hash}_{timestamp}.html"
    filepath = os.path.join("temp", filename)
    
    # Save figure
    fig.write_html(
        filepath,
        include_plotlyjs='cdn',
        include_mathjax=False,
        config={
            'displayModeBar': False,
            'responsive': True
        }
    )
    
    return f"/temp/{filename}"

def generate_umap_visualization(score_type, n_neighbors, min_dist, specific_pgs_ids, cohort, view_type, user_id=None):
    """
    Generate a UMAP visualization for PGS score data.
    
    Returns:
    --------
    tuple
        (fig, stats) - Plotly figure and statistics
    """
    print(f"=== Generating UMAP Visualization ===")
    print(f"View Type: {view_type}")
    print(f"Score Type: {score_type}")
    
    # Fetch required data
    data = fetch_umap_data(score_type, specific_pgs_ids, cohort, user_id=user_id)
    
    # Get the score matrix as dictionary
    data_dict = fetch_score_dictionary(
        data['sample_ids'],
        data['pgs_ids'],
        score_type,
        user_id
    )
    
    # Route to appropriate visualization based on view type
    if view_type == "sample":
        return generate_sample_based_umap(
            data['sample_ids'],
            data['pgs_ids'],
            data_dict,
            n_neighbors,
            min_dist,
            score_type,
            cohort
        )
    else:
        return generate_score_based_umap(
            data['sample_ids'],
            data['pgs_ids'],
            data_dict,
            n_neighbors,
            min_dist,
            score_type,
            cohort,
            data['pgs_metadata']
        )

def fetch_umap_data(score_type, specific_pgs_ids, cohort, user_id=None):
    """Fetch all required data for UMAP visualization."""
    # Get PGS IDs
    pgs_ids = db.fetch_pgs_ids(specific_pgs_ids, score_type, user_id)
    print(f"Selected {len(pgs_ids)} PGS_IDs.")
    
    # Get metadata for PGS IDs
    pgs_metadata = db.metadata.fetch_pgs_metadata(pgs_ids)
    
    # Get sample IDs
    sample_ids = db.ancestry.get_sample_ids_by_cohort(cohort)
    print(f"Found {len(sample_ids)} unique SAMPLE_IDs.")
    
    if cohort and cohort != "ALL":
        print(f"Using {len(sample_ids)} samples from {cohort} cohort.")
    
    return {
        'pgs_ids': pgs_ids,
        'pgs_metadata': pgs_metadata,
        'sample_ids': sample_ids
    }

def fetch_score_dictionary(sample_ids, pgs_ids, score_type, user_id):
    """Fetch score data as a dictionary."""
    data_dict, _ = db.get_score_matrix(
        sample_ids=sample_ids,
        pgs_ids=pgs_ids,
        score_type=score_type,
        output_format="dict",
        user_id=user_id
    )
    return data_dict

def generate_sample_based_umap(sample_ids, pgs_ids, data_dict, n_neighbors, min_dist, score_type, cohort):
    """Generate UMAP where each point is a sample."""
    print("Creating matrix for sample-based clustering...")
    
    # Create matrix
    matrix = create_sample_matrix(sample_ids, pgs_ids, data_dict)
    
    # Prepare matrix for UMAP
    matrix_for_umap = prepare_matrix_for_umap(matrix)
    
    # Run UMAP
    embedding = run_umap_algorithm(matrix_for_umap, n_neighbors, min_dist)
    
    # Calculate color values (average scores per sample)
    avg_scores = calculate_sample_average_scores(sample_ids, pgs_ids, data_dict)
    
    # Create hover text
    hover_text = create_sample_hover_text(sample_ids, pgs_ids, data_dict)
    
    # Create figure
    fig = create_sample_umap_figure(
        embedding,
        hover_text,
        avg_scores,
        score_type,
        cohort,
        len(pgs_ids),
        len(sample_ids)
    )
    
    # Configure layout
    configure_umap_layout(fig)
    
    return fig, (None,)

def generate_score_based_umap(sample_ids, pgs_ids, data_dict, n_neighbors, min_dist, 
                              score_type, cohort, pgs_metadata):
    """Generate UMAP where each point is a PGS score."""
    print("Creating matrix for score-based clustering...")
    
    # Create transposed matrix (PGS x samples)
    matrix = create_score_matrix(pgs_ids, sample_ids, data_dict)
    
    # Prepare matrix for UMAP
    matrix_for_umap = prepare_matrix_for_umap(matrix)
    
    # Adjust n_neighbors if necessary
    adjusted_n_neighbors = min(n_neighbors, len(pgs_ids) - 1)
    
    # Run UMAP
    embedding = run_umap_algorithm(matrix_for_umap, adjusted_n_neighbors, min_dist)
    
    # Create hover text
    hover_text = create_score_hover_text(pgs_ids, sample_ids, data_dict, pgs_metadata)
    
    # Get trait colors
    color_data = create_trait_color_mapping(pgs_ids, pgs_metadata)
    
    # Create figure
    fig = create_score_umap_figure(
        embedding,
        hover_text,
        color_data['color_indices'],
        score_type,
        cohort,
        len(pgs_ids),
        len(sample_ids)
    )
    
    # Configure layout
    configure_umap_layout(fig)
    
    return fig, (None,)

def create_sample_matrix(sample_ids, pgs_ids, data_dict):
    """Create matrix with samples as rows and PGS as columns."""
    matrix = np.full((len(sample_ids), len(pgs_ids)), np.nan)
    
    for i, sample_id in enumerate(sample_ids):
        if sample_id in data_dict:
            for j, pgs_id in enumerate(pgs_ids):
                if pgs_id in data_dict[sample_id]:
                    matrix[i, j] = data_dict[sample_id][pgs_id]
    
    return matrix

def create_score_matrix(pgs_ids, sample_ids, data_dict):
    """Create matrix with PGS as rows and samples as columns."""
    matrix = np.full((len(pgs_ids), len(sample_ids)), np.nan)
    
    for i, pgs_id in enumerate(pgs_ids):
        for j, sample_id in enumerate(sample_ids):
            if sample_id in data_dict and pgs_id in data_dict[sample_id]:
                matrix[i, j] = data_dict[sample_id][pgs_id]
    
    return matrix

def prepare_matrix_for_umap(matrix):
    """Handle missing values by replacing with column means."""
    print("Handling missing values...")
    matrix_for_umap = np.copy(matrix)
    
    for j in range(matrix_for_umap.shape[1]):
        col_values = matrix_for_umap[:, j]
        col_mean = np.nanmean(col_values)
        
        if not np.isnan(col_mean):  # Only fill if we have a valid mean
            mask = np.isnan(col_values)
            matrix_for_umap[mask, j] = col_mean
    
    return matrix_for_umap

def run_umap_algorithm(matrix, n_neighbors, min_dist):
    """Run UMAP dimensionality reduction."""
    print("Applying UMAP dimensionality reduction...")
    
    reducer = umap.UMAP(
        n_neighbors=n_neighbors,
        min_dist=min_dist,
        n_components=2,
        random_state=42
    )
    
    embedding = reducer.fit_transform(matrix)
    print(f"UMAP complete. Embedding shape: {embedding.shape}")
    
    return embedding

def calculate_sample_average_scores(sample_ids, pgs_ids, data_dict):
    """Calculate average score for each sample."""
    avg_scores = []
    
    for sample_id in sample_ids:
        if sample_id in data_dict:
            scores = [data_dict[sample_id].get(pgs_id, np.nan) for pgs_id in pgs_ids]
            avg_score = np.nanmean([s for s in scores if not np.isnan(s)])
            avg_scores.append(avg_score)
        else:
            avg_scores.append(np.nan)
    
    return avg_scores

def create_sample_hover_text(sample_ids, pgs_ids, data_dict):
    """Create hover text for sample-based UMAP."""
    hover_text = []
    
    for sample_id in sample_ids:
        # Calculate average score
        if sample_id in data_dict:
            scores = [data_dict[sample_id].get(pgs_id, np.nan) for pgs_id in pgs_ids]
            avg_score = np.nanmean([s for s in scores if not np.isnan(s)])
        else:
            avg_score = np.nan
        
        # Get ancestry information
        ancestry = db.ancestry.get_sample_ancestry(sample_id=sample_id)
        
        hover_info = (
            f"Sample: {sample_id}<br>"
            f"Ancestry: {ancestry}<br>"
            f"Avg Score: {avg_score:.4f}"
        )
        hover_text.append(hover_info)
    
    return hover_text

def create_score_hover_text(pgs_ids, sample_ids, data_dict, pgs_metadata):
    """Create hover text for score-based UMAP."""
    hover_text = []
    
    for pgs_id in pgs_ids:
        # Get metadata
        metadata = pgs_metadata.get(pgs_id, {
            'PGS_Name': 'Unknown',
            'Reported_Trait': 'Unknown',
            'Publication_ID': 'Unknown'
        })
        
        # Calculate average score across samples
        scores = []
        for sample_id in sample_ids:
            if sample_id in data_dict and pgs_id in data_dict[sample_id]:
                scores.append(data_dict[sample_id][pgs_id])
        
        avg_score = np.mean(scores) if scores else np.nan
        
        hover_info = (
            f"PGS ID: {pgs_id}<br>"
            f"Name: {metadata.get('PGS_Name', 'Unknown')}<br>"
            f"Trait: {metadata.get('Reported_Trait', 'Unknown')}<br>"
            f"Publication: {metadata.get('Publication_ID', 'Unknown')}<br>"
            f"Avg Score: {avg_score:.4f}"
        )
        hover_text.append(hover_info)
    
    return hover_text

def create_trait_color_mapping(pgs_ids, pgs_metadata):
    """Create color indices based on traits."""
    traits = [pgs_metadata.get(pgs_id, {}).get('Reported_Trait', 'Unknown') for pgs_id in pgs_ids]
    unique_traits = list(set(traits))
    color_indices = [unique_traits.index(trait) for trait in traits]
    
    return {
        'traits': traits,
        'unique_traits': unique_traits,
        'color_indices': color_indices
    }

def create_sample_umap_figure(embedding, hover_text, avg_scores, score_type, cohort, 
                             num_pgs, num_samples):
    """Create UMAP figure for sample-based visualization."""
    cohort_text = f" - {cohort} Cohort" if cohort and cohort != "ALL" else ""
    title = f'UMAP of {score_type} Scores{cohort_text}<br>({num_pgs} PGS_IDs, {num_samples} Samples)'
    
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
    
    fig.update_layout(title=title)
    
    return fig

def create_score_umap_figure(embedding, hover_text, color_indices, score_type, cohort, 
                            num_pgs, num_samples):
    """Create UMAP figure for score-based visualization."""
    cohort_text = f" - {cohort} Cohort" if cohort and cohort != "ALL" else ""
    title = f'Score-based UMAP of {score_type} Scores{cohort_text}<br>({num_pgs} PGS_IDs across {num_samples} Samples)'
    
    fig = go.Figure(data=go.Scatter(
        x=embedding[:, 0],
        y=embedding[:, 1],
        mode='markers',
        marker=dict(
            size=8,
            color=color_indices,
            colorscale='Rainbow',
            showscale=False
        ),
        text=hover_text,
        hoverinfo='text'
    ))
    
    fig.update_layout(title=title)
    
    return fig

def configure_umap_layout(fig):
    """Configure common layout settings for UMAP plots."""
    fig.update_layout(
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
        hovermode='closest',
        hoverlabel=dict(
            bgcolor="white",
            font_size=12,
            font_family="Arial"
        )
    )