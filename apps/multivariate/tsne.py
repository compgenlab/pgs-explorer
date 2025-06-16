import os
import json
import hashlib
import numpy as np
from datetime import datetime
import plotly.graph_objects as go
from sklearn.manifold import TSNE
from database import db

def process_tsne(request_data):
    """Main entry point for t-SNE visualization generation."""
    try:
        # Create temp directory if it doesn't exist
        os.makedirs("temp", exist_ok=True)
        
        # Extract and validate parameters
        params = extract_tsne_parameters(request_data)
        
        # Generate hash for caching
        request_hash = generate_tsne_hash(**params)
        print(f"Request hash: {request_hash}")

        # Check for cached result
        cached_file = check_tsne_cache(request_hash)
        if cached_file:
            return cached_file
        
        # Perform t-SNE analysis
        tsne_result = perform_tsne_analysis(**params)
        
        # Generate visualization
        fig = generate_tsne_visualization(tsne_result, params)
        
        # Save and return file path
        filepath = save_tsne_visualization(fig, params, request_hash)
        return filepath
        
    except Exception as e:
        print(f"Error generating t-SNE visualization: {str(e)}")
        raise e

def extract_tsne_parameters(request_data):
    """Extract and validate t-SNE parameters from request data."""
    return {
        'score_type': request_data["score_type"],
        'specific_pgs_ids': request_data.get("pgs_ids"),
        'cohort': request_data.get("cohort"),
        'perspective': request_data.get("perspective", "sample"),
        'perplexity': request_data["perplexity"],
        'n_iter': request_data["iterations"],
        'learning_rate': request_data["learning_rate"],
        'user_id': request_data.get("user_id", None)
    }

def generate_tsne_hash(score_type, specific_pgs_ids, cohort, perspective, perplexity, n_iter, learning_rate, user_id):
    """Generate a hash for the t-SNE request parameters for caching."""
    hash_input = json.dumps({
        "score_type": score_type,
        "pgs_ids": sorted(specific_pgs_ids) if specific_pgs_ids else "all",
        "cohort": cohort if cohort else "ALL",
        "perspective": perspective,
        "perplexity": perplexity,
        "iterations": n_iter,
        "learning_rate": learning_rate,
        "user_id": user_id
    }, sort_keys=True)
    
    return hashlib.md5(hash_input.encode()).hexdigest()

def check_tsne_cache(request_hash):
    """Check if t-SNE visualization is already cached."""
    for filename in os.listdir("temp"):
        if filename.endswith(".html") and request_hash in filename and "tsne" in filename:
            cached_filepath = os.path.join("temp", filename)
            os.utime(cached_filepath)
            print(f"Using cached t-SNE visualization: {filename}")
            return f"/temp/{filename}"
    return None

def generate_tsne_visualization(tsne_result, params):
    """Route to appropriate visualization function based on perspective."""
    if params['perspective'] == "score":
        return generate_tsne_score(
            tsne_result['embedding'],
            tsne_result['pgs_ids']
        )
    else:
        return generate_tsne_sample(
            tsne_result['embedding'],
            tsne_result['sample_ids']
        )

def save_tsne_visualization(fig, params, request_hash):
    """Save t-SNE visualization to HTML file."""
    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    score_type_safe = params['score_type'].replace("/", "_").replace("\\", "_")
    cohort_indicator = f"{params['cohort']}_" if params['cohort'] and params['cohort'] != "ALL" else ""
    filename = f"tsne_{cohort_indicator}{score_type_safe}_{request_hash}_{timestamp}.html"
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

def perform_tsne_analysis(score_type, specific_pgs_ids, cohort, perspective, perplexity, n_iter, learning_rate, user_id):
    """
    Perform t-SNE analysis on the score matrix.
    
    Returns:
    --------
    dict
        Dictionary containing:
        - embedding: t-SNE transformed coordinates
        - pgs_ids: List of PGS IDs
        - sample_ids: List of sample IDs
    """
    # Fetch required data
    data = fetch_tsne_data(score_type, specific_pgs_ids, cohort, user_id)
    
    # Get the score matrix
    matrix = fetch_tsne_matrix(
        data['sample_ids'],
        data['pgs_ids'],
        score_type,
        user_id
    )
    
    # Prepare matrix based on perspective
    prepared_matrix = prepare_matrix_for_tsne(matrix, perspective)
    
    # Run t-SNE
    embedding = run_tsne_algorithm(
        prepared_matrix,
        perplexity,
        n_iter,
        learning_rate
    )
    
    return {
        'embedding': embedding,
        'pgs_ids': data['pgs_ids'],
        'sample_ids': data['sample_ids']
    }

def fetch_tsne_data(score_type, specific_pgs_ids, cohort, user_id):
    """Fetch PGS IDs and sample IDs for t-SNE analysis."""
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
        print(f"Filtering to {len(sample_ids)} samples from {cohort} cohort")
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

def fetch_tsne_matrix(sample_ids, pgs_ids, score_type, user_id):
    """Fetch the score matrix for t-SNE analysis."""
    matrix, _ = db.get_score_matrix(
        sample_ids=sample_ids,
        pgs_ids=pgs_ids,
        score_type=score_type,
        output_format="numpy",
        handle_missing=True,
        user_id=user_id
    )
    
    print(f"Matrix shape: {matrix.shape}")
    return matrix

def prepare_matrix_for_tsne(matrix, perspective):
    """
    Prepare matrix for t-SNE based on perspective.
    
    Parameters:
    -----------
    matrix : numpy.ndarray
        Original matrix (samples x PGS)
    perspective : str
        Either "sample" or "score"
        
    Returns:
    --------
    numpy.ndarray
        Matrix ready for t-SNE
    """
    if perspective == "score" and matrix.shape[0] > matrix.shape[1]:
        # Transpose matrix for score-centered analysis (if samples > scores)
        print("Transposing matrix for score-centered t-SNE")
        return matrix.T
    else:
        # For sample-centered or already suitable matrices
        return matrix

def run_tsne_algorithm(matrix, perplexity, n_iter, learning_rate):
    """
    Run the t-SNE algorithm on the prepared matrix.
    
    Parameters:
    -----------
    matrix : numpy.ndarray
        Prepared matrix for t-SNE
    perplexity : float
        t-SNE perplexity parameter
    n_iter : int
        Number of iterations
    learning_rate : float
        Learning rate for t-SNE
        
    Returns:
    --------
    numpy.ndarray
        2D embedding coordinates
    """
    print(f"Running t-SNE with perplexity={perplexity}, n_iter={n_iter}, learning_rate={learning_rate}")
    
    tsne = TSNE(
        n_components=2,
        perplexity=perplexity,
        n_iter=n_iter,
        learning_rate=learning_rate,
        random_state=42
    )
    
    embedding = tsne.fit_transform(matrix)
    print(f"t-SNE complete. Embedding shape: {embedding.shape}")
    
    return embedding

def generate_tsne_sample(tsne_result, sample_ids):
    """Generate t-SNE visualization for samples."""
    # Create figure
    fig = go.Figure()
    
    # Add sample scatter plot
    add_sample_scatter_tsne(fig, tsne_result, sample_ids)
    
    # Configure layout
    configure_sample_tsne_layout(fig)
    
    return fig

def generate_tsne_score(tsne_result, pgs_ids):
    """Generate t-SNE visualization for PGS scores."""
    # Fetch metadata
    pgs_metadata = db.metadata.fetch_pgs_metadata(pgs_ids)
    
    # Create hover text
    hover_text = create_score_hover_text_tsne(pgs_ids, pgs_metadata)
    
    # Create figure
    fig = go.Figure()
    
    # Add score scatter plot
    add_score_scatter_tsne(fig, tsne_result, hover_text)
    
    # Configure layout
    configure_score_tsne_layout(fig)
    
    return fig

def add_sample_scatter_tsne(fig, tsne_result, sample_ids):
    """Add sample points to t-SNE plot."""
    fig.add_trace(
        go.Scatter(
            x=tsne_result[:, 0],
            y=tsne_result[:, 1],
            mode="markers",
            marker=dict(
                size=6,
                color="blue",
                opacity=0.7
            ),
            text=sample_ids,
            hoverinfo="text",
            name="Samples"
        )
    )

def add_score_scatter_tsne(fig, tsne_result, hover_text):
    """Add PGS score points to t-SNE plot."""
    fig.add_trace(
        go.Scatter(
            x=tsne_result[:, 0],
            y=tsne_result[:, 1],
            mode="markers",
            marker=dict(
                size=6,
                color="red",
                opacity=0.7
            ),
            text=hover_text,
            hoverinfo="text",
            name="PGS Scores"
        )
    )

def create_score_hover_text_tsne(pgs_ids, pgs_metadata):
    """Create hover text for PGS score points in t-SNE."""
    hover_text = []
    
    for pgs_id in pgs_ids:
        meta = pgs_metadata.get(pgs_id, {})
        if not meta:
            print(f"Missing metadata for {pgs_id}")
        
        hover_info = (
            f"PGS ID: {pgs_id}<br>"
            f"Name: {meta.get('PGS_Name', 'N/A')}<br>"
            f"Trait: {meta.get('Reported_Trait', 'N/A')}<br>"
            f"Publication: {meta.get('Publication_ID', 'N/A')}"
        )
        hover_text.append(hover_info)
    
    return hover_text

def configure_sample_tsne_layout(fig):
    """Configure layout for sample t-SNE plot."""
    fig.update_layout(
        title="t-SNE Projection (Samples as Points)",
        xaxis_title="t-SNE 1",
        yaxis_title="t-SNE 2",
        showlegend=False,
        height=800,
        width=1000,
        hoverlabel=dict(
            bgcolor="white",
            font_size=12,
            font_family="Arial"
        )
    )

def configure_score_tsne_layout(fig):
    """Configure layout for PGS score t-SNE plot."""
    fig.update_layout(
        title="t-SNE Projection (PGS Scores as Points)",
        xaxis_title="t-SNE 1",
        yaxis_title="t-SNE 2",
        showlegend=False,
        height=800,
        width=1000,
        hoverlabel=dict(
            bgcolor="white",
            font_size=12,
            font_family="Arial"
        )
    )