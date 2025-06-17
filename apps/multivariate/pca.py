import os
import json
import hashlib
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
from database import db
import time

def process_pca(request_data):
    """Main entry point for PCA visualization generation."""
    try:
        # Create temp directory if it doesn't exist
        os.makedirs("temp", exist_ok=True)
        
        # Extract and validate parameters
        params = extract_pca_parameters(request_data)
        
        # Generate hash for caching
        request_hash = generate_pca_hash(**params)
        
        # Check for cached result
        cached_file = check_pca_cache(request_hash)
        if cached_file:
            return cached_file
        
        # Perform PCA analysis
        pca_result = perform_pca_analysis(
            score_type=params['score_type'],
            specific_pgs_ids=params['pgs_ids'],
            cohort=params['cohort'],
            user_id=params['user_id']
        )
        
        # Generate visualization
        fig = generate_pca_visualization(pca_result, params)
        
        # Save and return file path
        filepath = save_pca_visualization(fig, params, request_hash)
        return filepath
        
    except Exception as e:
        print(f"Error generating PCA visualization: {str(e)}")
        raise e

def extract_pca_parameters(request_data):
    """Extract and validate PCA parameters from request data."""
    return {
        'score_type': request_data["score_type"],
        'pgs_ids': request_data["pgs_ids"],
        'cohort': request_data["cohort"],
        'perspective': request_data.get("perspective", "sample"),
        'x_axis': request_data.get("x_axis", "1"),
        'y_axis': request_data.get("y_axis", "2"),
        'include_variance': request_data.get("include_variance", True),
        'user_id': request_data.get("user_id", None)
    }

def generate_pca_hash(score_type, pgs_ids, cohort, perspective, x_axis, y_axis, include_variance, user_id):
    """Generate a hash for the PCA request parameters for caching."""
    params = {
        "score_type": score_type,
        "pgs_ids": sorted(pgs_ids) if pgs_ids else "all",
        "cohort": cohort if cohort else "ALL",
        "perspective": perspective,
        "x_axis": x_axis,
        "y_axis": y_axis,
        "include_variance": include_variance,
        "user_id": user_id
    }
    param_str = json.dumps(params, sort_keys=True)
    hash_obj = hashlib.md5(param_str.encode())
    return hash_obj.hexdigest()

def check_pca_cache(request_hash):
    """Check if PCA visualization is already cached."""
    for filename in os.listdir("temp"):
        if filename.endswith(".html") and request_hash in filename and "pca" in filename:
            # Found a cached file, update its access time
            cached_filepath = os.path.join("temp", filename)
            os.utime(cached_filepath)
            print(f"Using cached PCA visualization: {filename}")
            return f"/temp/{filename}"
    return None

def generate_pca_visualization(pca_result, params):
    """Route to appropriate visualization function based on perspective."""
    if params['perspective'] == "score":
        return generate_pca_score(
            U=pca_result['U'],
            S=pca_result['S'],
            Vt=pca_result['Vt'],
            pgs_ids=pca_result['pgs_ids'],
            sample_ids=pca_result['sample_ids'],
            stats=pca_result['stats'],
            x_axis=params['x_axis'],
            y_axis=params['y_axis'],
            include_variance=params['include_variance']
        )
    else:
        return generate_pca_sample(
            U=pca_result['U'],
            S=pca_result['S'],
            Vt=pca_result['Vt'],
            pgs_ids=pca_result['pgs_ids'],
            sample_ids=pca_result['sample_ids'],
            stats=pca_result['stats'],
            x_axis=params['x_axis'],
            y_axis=params['y_axis'],
            include_variance=params['include_variance']
        )

def save_pca_visualization(fig, params, request_hash):
    """Save PCA visualization to HTML file."""
    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    score_type_safe = params['score_type'].replace("/", "_").replace("\\", "_")
    cohort_indicator = f"{params['cohort']}_" if params['cohort'] and params['cohort'] != "ALL" else ""
    filename = f"pca_{cohort_indicator}{score_type_safe}_{request_hash}_{timestamp}.html"
    filepath = os.path.join("temp", filename)
    
    # Save figure
    fig.write_html(
        filepath,
        include_plotlyjs='cdn',
        include_mathjax=False,
        config={
            'displayModeBar': True,
            'responsive': True
        }
    )
    
    return f"/temp/{filename}"

def perform_pca_analysis(score_type, specific_pgs_ids=None, cohort=None, user_id=None):
    """
    Build a matrix of PGS scores x samples and perform SVD on it.
    """
    print(f"=== Performing SVD Analysis ===")
    print(f"Score Type: {score_type}")
    
    # Fetch required data
    data = fetch_pca_data(score_type, specific_pgs_ids, cohort, user_id)
    
    # Get the score matrix
    matrix = fetch_pca_matrix(data['sample_ids'], data['pgs_ids'], score_type, user_id)
    
    # Perform SVD
    svd_result = perform_svd(matrix)
    
    # Calculate statistics
    stats = calculate_pca_statistics(
        svd_result, 
        len(data['sample_ids']), 
        len(data['pgs_ids']), 
        score_type, 
        cohort
    )
    
    return {
        'U': svd_result['U'],
        'S': svd_result['S'],
        'Vt': svd_result['Vt'],
        'pgs_ids': data['pgs_ids'],
        'sample_ids': data['sample_ids'],
        'stats': stats
    }

def fetch_pca_data(score_type, specific_pgs_ids, cohort, user_id):
    """Fetch PGS IDs and sample IDs for PCA analysis."""
    # Get PGS IDs
    pgs_ids = db.fetch_pgs_ids(
        specific_pgs_ids=specific_pgs_ids,
        score_type=score_type,
        user_id=user_id
    )
    print(f"Selected {len(pgs_ids)} PGS_IDs.")
    
    # Get sample IDs
    if cohort and cohort != "ALL":
        sample_ids = db.ancestry.get_sample_ids_by_cohort(cohort)
        print(f"Filtering to {len(sample_ids)} samples from {cohort} population")
    else:
        # Get all sample IDs that have scores for these PGS IDs
        sample_ids = db.scores.get_sample_ids_with_scores(
            score_type=score_type,
            pgs_ids=pgs_ids
        )
        print(f"Found {len(sample_ids)} unique SAMPLE_IDs.")
    
    return {
        'pgs_ids': pgs_ids,
        'sample_ids': sample_ids
    }

def fetch_pca_matrix(sample_ids, pgs_ids, score_type, user_id):
    """Fetch and prepare the score matrix for PCA."""
    start_time = time.time()
    print("Starting data processing...")
    
    matrix, _ = db.get_score_matrix(
        sample_ids=sample_ids,
        pgs_ids=pgs_ids,
        score_type=score_type,
        output_format="numpy",
        handle_missing=True,
        user_id=user_id
    )
    
    total_time = time.time() - start_time
    print(f"Total processing time: {total_time:.2f} seconds.")
    print(f"Matrix shape: {matrix.shape}")
    
    return matrix

def perform_svd(matrix):
    """Perform SVD on the centered matrix."""
    print("Performing SVD...")
    
    # Center the data (important for SVD/PCA interpretation)
    matrix_centered = matrix - np.mean(matrix, axis=0)
    
    # Perform SVD
    U, S, Vt = np.linalg.svd(matrix_centered, full_matrices=False)
    
    return {
        'U': U,
        'S': S,
        'Vt': Vt,
        'matrix_centered': matrix_centered
    }

def calculate_pca_statistics(svd_result, num_samples, num_pgs_ids, score_type, cohort):
    """Calculate PCA statistics including explained variance."""
    S = svd_result['S']
    matrix_centered = svd_result['matrix_centered']
    
    # Calculate explained variance
    explained_variance = (S ** 2) / (matrix_centered.shape[0] - 1)
    total_variance = np.sum(explained_variance)
    explained_variance_ratio = explained_variance / total_variance
    
    return {
        "explained_variance_ratio": explained_variance_ratio.tolist(),
        "cumulative_variance": np.cumsum(explained_variance_ratio).tolist(),
        "singular_values": S.tolist(),
        "num_samples": num_samples,
        "num_pgs_ids": num_pgs_ids,
        "score_type": score_type,
        "cohort": cohort if cohort else "ALL"
    }

def generate_pca_sample(U, S, Vt, pgs_ids, sample_ids, stats, pgs_metadata=None, x_axis="1", y_axis="2", include_variance=True):
    """Generate a PCA plot visualizing samples in 2D space."""
    # Convert axis inputs to indices
    x_idx, y_idx = convert_axis_to_indices(x_axis, y_axis)
    
    # Scale the singular vectors
    U_scaled = scale_singular_vectors(U, S, x_idx, y_idx)
    
    # Create figure
    fig = create_sample_scatter_plot(U_scaled, sample_ids)
    
    # Add variance labels
    axis_labels = create_axis_labels(x_axis, y_axis, stats, x_idx, y_idx, include_variance)
    
    # Update layout
    update_pca_layout(
        fig, 
        f'PCA: {stats.get("score_type", "Unknown")} Scores (Sample-centered view)',
        axis_labels['x_title'],
        axis_labels['y_title']
    )
    
    # Add scale reference circle
    add_scale_reference_circle(fig, U_scaled)
    
    return fig

def generate_pca_score(U, S, Vt, pgs_ids, sample_ids, stats, x_axis="1", y_axis="2", include_variance=True):
    """Generate a PCA plot visualizing PGS scores in 2D space."""
    # Convert axis inputs to indices
    x_idx, y_idx = convert_axis_to_indices(x_axis, y_axis)
    
    # Scale the singular vectors
    Vt_scaled = scale_singular_vectors_transpose(Vt, S, x_idx, y_idx)
    
    # Fetch metadata and create hover text
    pgs_metadata = db.metadata.fetch_pgs_metadata(pgs_ids=pgs_ids)
    hover_text = create_pgs_hover_text(pgs_ids, pgs_metadata)
    
    # Create figure
    fig = create_score_scatter_plot(Vt_scaled, hover_text)
    
    # Add variance labels
    axis_labels = create_axis_labels(x_axis, y_axis, stats, x_idx, y_idx, include_variance)
    
    # Update layout
    update_pca_layout(
        fig, 
        f'PCA Plot: {stats.get("score_type", "Unknown")} Scores (Score-centered view)',
        axis_labels['x_title'],
        axis_labels['y_title']
    )
    
    # Add scale reference circle
    add_scale_reference_circle(fig, Vt_scaled)
    
    return fig

def convert_axis_to_indices(x_axis, y_axis):
    """Convert axis inputs from 1-based to 0-based indices."""
    return int(x_axis) - 1, int(y_axis) - 1

def scale_singular_vectors(U, S, x_idx, y_idx):
    """Scale the left singular vectors by the singular values."""
    return U[:, [x_idx, y_idx]] * S[[x_idx, y_idx]]

def scale_singular_vectors_transpose(Vt, S, x_idx, y_idx):
    """Scale the right singular vectors by the singular values."""
    return Vt[[x_idx, y_idx], :].T * S[[x_idx, y_idx]]

def create_sample_scatter_plot(U_scaled, sample_ids):
    """Create scatter plot for samples."""
    fig = go.Figure()
    
    fig.add_trace(
        go.Scatter(
            x=U_scaled[:, 0],
            y=U_scaled[:, 1],
            mode='markers',
            marker=dict(
                size=5,
                color='green',
                opacity=0.6
            ),
            name='Samples',
            text=[f"Sample: {sample_id}" for sample_id in sample_ids],
            hoverinfo='text'
        )
    )
    
    return fig

def create_score_scatter_plot(Vt_scaled, hover_text):
    """Create scatter plot for PGS scores."""
    fig = go.Figure()
    
    fig.add_trace(
        go.Scatter(
            x=Vt_scaled[:, 0],
            y=Vt_scaled[:, 1],
            mode='markers+text',
            marker=dict(
                size=5,
                color='red',
                opacity=0.6
            ),
            name='PGS Scores',
            hovertext=hover_text,
            hoverinfo='text'
        )
    )
    
    return fig

def create_pgs_hover_text(pgs_ids, pgs_metadata):
    """Create hover text for PGS points."""
    hover_text = []
    
    for pgs_id in pgs_ids:
        if pgs_metadata and pgs_id in pgs_metadata:
            meta = pgs_metadata[pgs_id]
            hover_info = (
                f"PGS ID: {pgs_id}<br>"
                f"Name: {meta.get('PGS_Name', 'N/A')}<br>"
                f"Trait: {meta.get('Reported_Trait', 'N/A')}<br>"
                f"Publication: {meta.get('Publication_ID', 'N/A')}"
            )
        else:
            hover_info = f"PGS ID: {pgs_id}"
        
        hover_text.append(hover_info)
    
    return hover_text

def create_axis_labels(x_axis, y_axis, stats, x_idx, y_idx, include_variance):
    """Create axis labels with variance information if requested."""
    if include_variance and "explained_variance_ratio" in stats:
        x_var = stats["explained_variance_ratio"][x_idx] * 100
        y_var = stats["explained_variance_ratio"][y_idx] * 100
        return {
            'x_title': f'Component {x_axis} ({x_var:.1f}%)',
            'y_title': f'Component {y_axis} ({y_var:.1f}%)'
        }
    else:
        return {
            'x_title': f'Component {x_axis}',
            'y_title': f'Component {y_axis}'
        }

def update_pca_layout(fig, title, x_title, y_title):
    """Update the layout of the PCA plot."""
    fig.update_layout(
        title=title,
        xaxis=dict(title=x_title, zeroline=True),
        yaxis=dict(title=y_title, zeroline=True),
        showlegend=False,
        height=800,
        width=1000,
        hoverlabel=dict(
            bgcolor="white",
            font_size=12,
            font_family="Arial"
        )
    )

def add_scale_reference_circle(fig, scaled_vectors):
    """Add a dashed circle to indicate scale."""
    theta = np.linspace(0, 2 * np.pi, 100)
    radius = np.percentile(np.sqrt(np.sum(scaled_vectors**2, axis=1)), 75)
    
    fig.add_trace(
        go.Scatter(
            x=radius * np.cos(theta),
            y=radius * np.sin(theta),
            mode='lines',
            line=dict(color='gray', dash='dash', width=1),
            name='Scale Reference',
            hoverinfo='skip'
        )
    )