import os
import json
import time
import hashlib
import numpy as np
from datetime import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from database import db

def process_svd(request_data):
    """Main entry point for SVD visualization generation."""
    try:
        # Create temp directory if it doesn't exist
        os.makedirs("temp", exist_ok=True)
        
        # Extract and validate parameters
        params = extract_svd_parameters(request_data)
        
        # Generate hash for caching
        request_hash = generate_svd_hash(**params)
        
        # Check for cached result
        cached_file = check_svd_cache(request_hash)
        if cached_file:
            return cached_file
        
        # Perform SVD analysis
        svd_result = perform_svd_analysis(
            score_type=params['score_type'],
            specific_pgs_ids=params['pgs_ids'],
            cohort=params['cohort']
        )
        
        # Generate visualization
        fig = generate_svd_visualization(svd_result, params)
        
        # Save and return file path
        filepath = save_svd_visualization(fig, params, request_hash)
        return filepath
        
    except Exception as e:
        print(f"Error generating SVD visualization: {str(e)}")
        raise e

def extract_svd_parameters(request_data):
    """Extract and validate SVD parameters from request data."""
    return {
        'score_type': request_data["score_type"],
        'pgs_ids': request_data["pgs_ids"],
        'cohort': request_data["cohort"],
        'plot_type': request_data["plot_type"],
        'perspective': request_data.get("perspective", "sample"),
        'max_vectors': request_data.get("max_vectors", 10)
    }

def generate_svd_hash(score_type, pgs_ids, cohort, plot_type, perspective, max_vectors):
    """Generate a hash for the SVD request parameters for caching."""
    params = {
        "score_type": score_type,
        "pgs_ids": sorted(pgs_ids) if pgs_ids else "all",
        "cohort": cohort if cohort else "ALL",
        "plot_type": plot_type,
        "perspective": perspective,
        "max_vectors": max_vectors
    }
    param_str = json.dumps(params, sort_keys=True)
    hash_obj = hashlib.md5(param_str.encode())
    return hash_obj.hexdigest()

def check_svd_cache(request_hash):
    """Check if SVD visualization is already cached."""
    for filename in os.listdir("temp"):
        if filename.endswith(".html") and request_hash in filename and "svd" in filename:
            cached_filepath = os.path.join("temp", filename)
            os.utime(cached_filepath)
            print(f"Using cached SVD visualization: {filename}")
            return f"/temp/{filename}"
    return None

def generate_svd_visualization(svd_result, params):
    """Route to appropriate visualization function based on plot type."""
    plot_type = params['plot_type']
    
    if plot_type == "scree":
        return generate_svd_scree_plot(
            svd_result['S'], 
            svd_result['stats']
        )
    elif plot_type == "biplot":
        if params['perspective'] == "score":
            return generate_svd_biplot_score(
                U=svd_result['U'],
                S=svd_result['S'],
                Vt=svd_result['Vt'],
                pgs_ids=svd_result['pgs_ids'],
                sample_ids=svd_result['sample_ids'],
                stats=svd_result['stats'],
                max_vectors=params['max_vectors']
            )
        else:
            return generate_svd_biplot_sample(
                U=svd_result['U'],
                S=svd_result['S'],
                Vt=svd_result['Vt'],
                pgs_ids=svd_result['pgs_ids'],
                sample_ids=svd_result['sample_ids'],
                stats=svd_result['stats'],
                max_vectors=params['max_vectors']
            )
    elif plot_type == "component_weights":
        return generate_svd_component_weights(
            svd_result['Vt'],
            svd_result['pgs_ids'],
            svd_result['stats']
        )
    elif plot_type == "heatmap":
        return generate_svd_heatmap(
            svd_result['Vt'],
            svd_result['pgs_ids'],
            svd_result['stats']
        )
    elif plot_type == "combined":
        return generate_svd_combined(
            U=svd_result['U'],
            S=svd_result['S'],
            Vt=svd_result['Vt'],
            pgs_ids=svd_result['pgs_ids'],
            sample_ids=svd_result['sample_ids'],
            stats=svd_result['stats']
        )

def save_svd_visualization(fig, params, request_hash):
    """Save SVD visualization to HTML file."""
    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    score_type_safe = params['score_type'].replace("/", "_").replace("\\", "_")
    cohort_indicator = f"{params['cohort']}_" if params['cohort'] and params['cohort'] != "ALL" else ""
    filename = f"svd_{cohort_indicator}{score_type_safe}_{params['plot_type']}_{request_hash}_{timestamp}.html"
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

def perform_svd_analysis(score_type, specific_pgs_ids=None, cohort=None):
    """
    Build a matrix of PGS scores x samples and perform SVD on it.
    This is identical to PCA analysis since SVD is used for PCA computation.
    """
    print(f"=== Performing SVD Analysis ===")
    print(f"Score Type: {score_type}")
    
    # Fetch required data
    data = fetch_svd_data(score_type, specific_pgs_ids, cohort)
    
    # Get the score matrix
    matrix = fetch_svd_matrix(data['sample_ids'], data['pgs_ids'], score_type)
    
    # Perform SVD
    svd_result = perform_svd_computation(matrix)
    
    # Calculate statistics
    stats = calculate_svd_statistics(
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

def fetch_svd_data(score_type, specific_pgs_ids, cohort):
    """Fetch PGS IDs and sample IDs for SVD analysis."""
    # Get PGS IDs
    pgs_ids = db.scores.fetch_pgs_ids(
        specific_pgs_ids=specific_pgs_ids,
        score_type=score_type
    )
    print(f"Selected {len(pgs_ids)} PGS_IDs.")
    
    # Get sample IDs
    if cohort and cohort != "ALL":
        sample_ids = db.ancestry.sample_ids_by_cohort(cohort)
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

def fetch_svd_matrix(sample_ids, pgs_ids, score_type):
    """Fetch and prepare the score matrix for SVD."""
    start_time = time.time()
    print("Starting data processing...")
    
    matrix, _ = db.scores.get_matrix(
        sample_ids=sample_ids,
        pgs_ids=pgs_ids,
        score_type=score_type,
        output_format="numpy",
        handle_missing=True
    )
    
    total_time = time.time() - start_time
    print(f"Total processing time: {total_time:.2f} seconds.")
    print(f"Matrix shape: {matrix.shape}")
    
    return matrix

def perform_svd_computation(matrix):
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

def calculate_svd_statistics(svd_result, num_samples, num_pgs_ids, score_type, cohort):
    """Calculate SVD statistics including explained variance."""
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

def generate_svd_scree_plot(S, stats):
    """Generate a scree plot to visualize singular values and explained variance."""
    explained_variance_ratio = stats["explained_variance_ratio"]
    cumulative_variance = stats["cumulative_variance"]
    
    # Create scree plot with two traces
    fig = create_scree_plot_figure()
    
    # Add bar chart for individual explained variance
    add_variance_bars(fig, explained_variance_ratio)
    
    # Add line chart for cumulative explained variance
    add_cumulative_line(fig, cumulative_variance)
    
    # Update layout
    configure_scree_plot_layout(fig, stats["score_type"], explained_variance_ratio)
    
    return fig

def create_scree_plot_figure():
    """Create the base figure for scree plot."""
    return make_subplots(specs=[[{"secondary_y": True}]])

def add_variance_bars(fig, explained_variance_ratio):
    """Add bar chart for individual explained variance."""
    fig.add_trace(
        go.Bar(
            x=list(range(1, len(explained_variance_ratio)+1)),
            y=explained_variance_ratio,
            name="Explained Variance",
            marker_color="blue"
        ),
        secondary_y=False
    )

def add_cumulative_line(fig, cumulative_variance):
    """Add line chart for cumulative explained variance."""
    fig.add_trace(
        go.Scatter(
            x=list(range(1, len(cumulative_variance)+1)),
            y=cumulative_variance,
            name="Cumulative Variance",
            mode="lines+markers",
            line=dict(color="red")
        ),
        secondary_y=True
    )

def configure_scree_plot_layout(fig, score_type, explained_variance_ratio):
    """Configure layout for scree plot."""
    fig.update_layout(
        title=f'SVD Scree Plot: {score_type} Scores',
        xaxis=dict(
            title='Component',
            tickmode='linear',
            tick0=1,
            dtick=1
        ),
        yaxis=dict(
            title='Explained Variance Ratio',
            range=[0, max(explained_variance_ratio) * 1.1]
        ),
        yaxis2=dict(
            title='Cumulative Explained Variance',
            range=[0, 1.05],
            tickformat='.0%'
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        height=600,
        width=900
    )
    
    fig.update_traces(
        marker_line_color='rgb(8,48,107)',
        marker_line_width=1.5,
        opacity=0.6,
        selector=dict(type='bar')
    )

def generate_svd_biplot_sample(U, S, Vt, pgs_ids, sample_ids, stats, max_vectors=20):
    """Generate a biplot to visualize samples and features in the same 2D space."""
    n_components = 2
    
    # Scale the singular vectors
    U_scaled = scale_singular_vectors(U, S, n_components)
    
    # Create figure
    fig = go.Figure()
    
    # Add sample scatter plot
    add_sample_scatter(fig, U_scaled, sample_ids)
    
    # Get top contributing PGS scores
    top_indices = get_top_contributing_indices(Vt, n_components, pgs_ids, max_vectors)
    
    # Calculate scaling factor
    scale_factor = calculate_biplot_scale_factor(U_scaled, Vt, n_components)
    
    # Fetch metadata and add PGS vectors
    pgs_metadata = db.metadata.fetch_pgs_metadata(pgs_ids=pgs_ids)
    add_pgs_vectors(fig, Vt, pgs_ids, top_indices, scale_factor, pgs_metadata, n_components)
    
    # Update layout
    update_biplot_layout(
        fig,
        f'SVD Biplot: {stats["score_type"]} Scores (Sample-centered view)',
        stats,
        n_components
    )
    
    # Add scale reference circle
    add_scale_circle(fig, U_scaled)
    
    return fig

def generate_svd_biplot_score(U, S, Vt, pgs_ids, sample_ids, stats, max_vectors=20):
    """Generate a biplot to visualize PGS scores and samples in the same 2D space."""
    n_components = 2
    
    # Scale the singular vectors
    Vt_scaled = scale_singular_vectors_transpose(Vt, S, n_components)
    
    # Create figure
    fig = go.Figure()
    
    # Fetch metadata and create hover text
    pgs_metadata = db.metadata.fetch_pgs_metadata(pgs_ids=pgs_ids)
    hover_text = create_score_hover_text(pgs_ids, pgs_metadata, sample_ids)
    
    # Add PGS score scatter plot
    add_score_scatter(fig, Vt_scaled, pgs_ids, hover_text)
    
    # Calculate scaling factor and get top samples
    scale_factor = calculate_score_biplot_scale_factor(Vt_scaled, U, n_components)
    top_sample_indices = get_top_contributing_samples(U, n_components, sample_ids, max_vectors)
    
    # Add sample vectors
    add_sample_vectors(fig, U, sample_ids, top_sample_indices, scale_factor, n_components)
    
    # Update layout
    update_biplot_layout(
        fig,
        f'SVD Biplot: {stats["score_type"]} Scores (Score-centered view)',
        stats,
        n_components
    )
    
    # Add scale reference circle
    add_scale_circle(fig, Vt_scaled)
    
    return fig

def scale_singular_vectors(U, S, n_components):
    """Scale the left singular vectors by the singular values."""
    return U[:, :n_components] * S[:n_components]

def scale_singular_vectors_transpose(Vt, S, n_components):
    """Scale the right singular vectors by the singular values."""
    return Vt[:n_components, :].T * S[:n_components]

def add_sample_scatter(fig, U_scaled, sample_ids):
    """Add sample points to biplot."""
    fig.add_trace(
        go.Scatter(
            x=U_scaled[:, 0],
            y=U_scaled[:, 1],
            mode='markers',
            marker=dict(size=5, color='green', opacity=0.6),
            name='Samples',
            text=[f"Sample: {sample_id}" for sample_id in sample_ids],
            hoverinfo='text'
        )
    )

def add_score_scatter(fig, Vt_scaled, pgs_ids, hover_text):
    """Add PGS score points to biplot."""
    fig.add_trace(
        go.Scatter(
            x=Vt_scaled[:, 0],
            y=Vt_scaled[:, 1],
            mode='markers+text',
            marker=dict(size=5, color='red', opacity=0.6),
            name='PGS Scores',
            text=pgs_ids,
            textposition="top center",
            hovertext=hover_text,
            hoverinfo='text'
        )
    )

def get_top_contributing_indices(Vt, n_components, pgs_ids, max_vectors):
    """Get indices of top contributing PGS scores."""
    if len(pgs_ids) > max_vectors:
        pgs_contributions = np.sum(Vt[:n_components, :]**2, axis=0)
        return np.argsort(pgs_contributions)[::-1][:max_vectors]
    else:
        return range(len(pgs_ids))

def get_top_contributing_samples(U, n_components, sample_ids, max_vectors):
    """Get indices of top contributing samples."""
    if len(sample_ids) > max_vectors:
        sample_contributions = np.sum(U[:, :n_components]**2, axis=1)
        return np.argsort(sample_contributions)[::-1][:max_vectors]
    else:
        return range(len(sample_ids))

def calculate_biplot_scale_factor(U_scaled, Vt, n_components):
    """Calculate scaling factor for feature vectors in sample biplot."""
    return np.percentile(np.abs(U_scaled), 95) / np.percentile(np.abs(Vt[:n_components, :]), 95) * 0.5

def calculate_score_biplot_scale_factor(Vt_scaled, U, n_components):
    """Calculate scaling factor for sample vectors in score biplot."""
    return np.percentile(np.abs(Vt_scaled), 95) / np.percentile(np.abs(U[:, :n_components]), 95) * 0.5

def add_pgs_vectors(fig, Vt, pgs_ids, top_indices, scale_factor, pgs_metadata, n_components):
    """Add PGS feature vectors to biplot."""
    for idx in top_indices:
        pgs_id = pgs_ids[idx]
        hover_text = create_pgs_vector_hover_text(pgs_id, pgs_metadata)
        
        fig.add_trace(
            go.Scatter(
                x=[0, Vt[0, idx] * scale_factor],
                y=[0, Vt[1, idx] * scale_factor],
                mode='lines+text',
                line=dict(color='red', width=1),
                text=['', pgs_id],
                textposition='top center',
                name=pgs_id,
                hovertext=['', hover_text],
                hoverinfo='text'
            )
        )

def add_sample_vectors(fig, U, sample_ids, top_indices, scale_factor, n_components):
    """Add sample vectors to score biplot."""
    for idx in top_indices:
        fig.add_trace(
            go.Scatter(
                x=[0, U[idx, 0] * scale_factor],
                y=[0, U[idx, 1] * scale_factor],
                mode='lines',
                line=dict(color='blue', width=1),
                name=sample_ids[idx],
                hoverinfo='name'
            )
        )

def create_pgs_vector_hover_text(pgs_id, pgs_metadata):
    """Create hover text for PGS vectors."""
    if pgs_metadata and pgs_id in pgs_metadata:
        meta = pgs_metadata[pgs_id]
        return (
            f"PGS ID: {pgs_id}<br>"
            f"Name: {meta.get('PGS_Name', 'N/A')}<br>"
            f"Trait: {meta.get('Reported_Trait', 'N/A')}<br>"
            f"Publication: {meta.get('Publication_ID', 'N/A')}"
        )
    else:
        return f"PGS ID: {pgs_id}"

def create_score_hover_text(pgs_ids, pgs_metadata, sample_ids):
    """Create hover text for PGS score points."""
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

def update_biplot_layout(fig, title, stats, n_components):
    """Update layout for biplot."""
    fig.update_layout(
        title=title,
        xaxis=dict(
            title=f'Component 1 ({stats["explained_variance_ratio"][0]*100:.1f}%)',
            zeroline=True
        ),
        yaxis=dict(
            title=f'Component 2 ({stats["explained_variance_ratio"][1]*100:.1f}%)',
            zeroline=True
        ),
        showlegend=False,
        height=800,
        width=1000,
        hoverlabel=dict(
            bgcolor="white",
            font_size=12,
            font_family="Arial"
        )
    )

def add_scale_circle(fig, scaled_data):
    """Add a dashed circle to indicate scale."""
    theta = np.linspace(0, 2*np.pi, 100)
    radius = np.percentile(np.sqrt(np.sum(scaled_data**2, axis=1)), 75)
    
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

def generate_svd_component_weights(Vt, pgs_ids, stats):
    """Generate a visualization of component weights (loadings) for top components."""
    n_components = min(5, Vt.shape[0])
    n_top_pgs = min(20, len(pgs_ids))
    
    # Create subplots
    fig = create_component_weights_subplots(n_components, stats)
    
    # Add bar charts for each component
    for i in range(n_components):
        add_component_weights_bars(fig, Vt, pgs_ids, i, n_top_pgs)
    
    # Update layout
    configure_component_weights_layout(fig, stats["score_type"], n_components)
    
    return fig

def create_component_weights_subplots(n_components, stats):
    """Create subplots for component weights visualization."""
    return make_subplots(
        rows=n_components,
        cols=1,
        subplot_titles=[
            f'Component {i+1} ({stats["explained_variance_ratio"][i]*100:.1f}%)'
            for i in range(n_components)
        ]
    )

def add_component_weights_bars(fig, Vt, pgs_ids, component_idx, n_top_pgs):
    """Add bar chart for a single component's weights."""
    # Sort PGS IDs by absolute contribution
    sorted_indices = np.argsort(np.abs(Vt[component_idx, :]))[::-1][:n_top_pgs]
    
    # Get weights and PGS IDs
    weights = Vt[component_idx, sorted_indices]
    component_pgs_ids = [pgs_ids[idx] for idx in sorted_indices]
    
    # Add bar chart
    fig.add_trace(
        go.Bar(
            x=component_pgs_ids,
            y=weights,
            marker_color=['red' if w < 0 else 'green' for w in weights],
            name=f'Component {component_idx+1}'
        ),
        row=component_idx+1,
        col=1
    )

def configure_component_weights_layout(fig, score_type, n_components):
    """Configure layout for component weights visualization."""
    fig.update_layout(
        title=f'SVD Component Weights: {score_type} Scores',
        height=300 * n_components,
        width=1000,
        showlegend=False
    )
    
    # Update axes
    for i in range(n_components):
        fig.update_xaxes(title_text="PGS ID", row=i+1, col=1)
        fig.update_yaxes(title_text="Loading Weight", row=i+1, col=1)

def generate_svd_heatmap(Vt, pgs_ids, stats):
    """Generate a heatmap of component loadings."""
    n_components = min(10, Vt.shape[0])
    n_top_pgs = min(50, len(pgs_ids))
    
    # Get top contributing PGS IDs
    top_indices = get_top_pgs_for_heatmap(Vt, n_components, n_top_pgs)
    
    # Extract data for heatmap
    heatmap_data = Vt[:n_components, top_indices]
    heatmap_pgs_ids = [pgs_ids[idx] for idx in top_indices]
    
    # Create heatmap
    fig = create_loading_heatmap(heatmap_data, heatmap_pgs_ids, stats, n_components)
    
    # Update layout
    configure_heatmap_layout(fig, stats["score_type"])
    
    return fig

def get_top_pgs_for_heatmap(Vt, n_components, n_top_pgs):
    """Get indices of top contributing PGS IDs across all components."""
    overall_importance = np.sum(Vt[:n_components, :]**2, axis=0)
    return np.argsort(overall_importance)[::-1][:n_top_pgs]

def create_loading_heatmap(heatmap_data, heatmap_pgs_ids, stats, n_components):
    """Create the loading heatmap figure."""
    return go.Figure(data=go.Heatmap(
        z=heatmap_data,
        x=heatmap_pgs_ids,
        y=[f'Component {i+1} ({stats["explained_variance_ratio"][i]*100:.1f}%)'
           for i in range(n_components)],
        colorscale='RdBu',
        zmid=0,
        text=[[f'PGS: {pgs_id}<br>Component: {i+1}<br>Weight: {weight:.3f}'
              for pgs_id, weight in zip(heatmap_pgs_ids, row)]
              for i, row in enumerate(heatmap_data)],
        hoverinfo='text'
    ))

def configure_heatmap_layout(fig, score_type):
    """Configure layout for loading heatmap."""
    fig.update_layout(
        title=f'SVD Component Loading Heatmap: {score_type} Scores',
        xaxis=dict(title='PGS ID', tickangle=45),
        yaxis=dict(title='Component', autorange='reversed'),
        height=600,
        width=1200
    )

def generate_svd_combined(U, S, Vt, pgs_ids, sample_ids, stats):
    """Generate a combined visualization with multiple SVD plots."""
    # Create subplots
    fig = create_combined_subplots()
    
    # Add scree plot
    add_combined_scree_plot(fig, S, stats)
    
    # Add biplot
    add_combined_biplot(fig, U, S, Vt, pgs_ids)
    
    # Add component weights
    add_combined_component_weights(fig, Vt, pgs_ids)
    
    # Add heatmap
    add_combined_heatmap(fig, Vt, pgs_ids)
    
    # Update layout
    configure_combined_layout(fig, stats)
    
    return fig

def create_combined_subplots():
    """Create subplots for combined visualization."""
    return make_subplots(
        rows=2,
        cols=2,
        subplot_titles=[
            "Scree Plot",
            "Biplot (PC1 vs PC2)",
            "Top PGS Contributions to PC1",
            "Component Loading Heatmap"
        ],
        specs=[
            [{"type": "xy"}, {"type": "xy"}],
            [{"type": "xy"}, {"type": "heatmap"}]
        ]
    )

def add_combined_scree_plot(fig, S, stats):
    """Add scree plot to combined visualization."""
    explained_variance_ratio = stats["explained_variance_ratio"]
    cumulative_variance = stats["cumulative_variance"]
    
    # Bar chart for individual explained variance
    fig.add_trace(
        go.Bar(
            x=list(range(1, min(11, len(S))+1)),
            y=explained_variance_ratio[:10],
            name="Explained Variance"
        ),
        row=1, col=1
    )
    
    # Line chart for cumulative explained variance
    fig.add_trace(
        go.Scatter(
            x=list(range(1, min(11, len(S))+1)),
            y=cumulative_variance[:10],
            name="Cumulative Variance",
            mode="lines+markers"
        ),
        row=1, col=1
    )

def add_combined_biplot(fig, U, S, Vt, pgs_ids):
    """Add biplot to combined visualization."""
    n_components = 2
    U_scaled = U[:, :n_components] * S[:n_components]
    
    # Add samples as scatter points
    fig.add_trace(
        go.Scatter(
            x=U_scaled[:, 0],
            y=U_scaled[:, 1],
            mode='markers',
            marker=dict(size=5, opacity=0.6),
            name='Samples'
        ),
        row=1, col=2
    )
    
    # Add top PGS features as vectors
    scale_factor = np.percentile(np.abs(U_scaled), 95) / np.percentile(np.abs(Vt[:n_components, :]), 95) * 0.5
    
    # Find the top 10 contributors to PC1 and PC2
    pc_importance = Vt[0, :]**2 + Vt[1, :]**2
    top_indices = np.argsort(pc_importance)[::-1][:10]
    
    for idx in top_indices:
        pgs_id = pgs_ids[idx]
        fig.add_trace(
            go.Scatter(
                x=[0, Vt[0, idx] * scale_factor],
                y=[0, Vt[1, idx] * scale_factor],
                mode='lines+text',
                line=dict(width=1),
                text=['', pgs_id],
                textposition='top center',
                name=pgs_id
            ),
            row=1, col=2
        )

def add_combined_component_weights(fig, Vt, pgs_ids):
    """Add component weights to combined visualization."""
    n_top_pgs = 15
    sorted_indices = np.argsort(np.abs(Vt[0, :]))[::-1][:n_top_pgs]
    weights = Vt[0, sorted_indices]
    component_pgs_ids = [pgs_ids[idx] for idx in sorted_indices]
    
    fig.add_trace(
        go.Bar(
            x=component_pgs_ids,
            y=weights,
            marker_color=['red' if w < 0 else 'green' for w in weights],
            name='PC1 Weights'
        ),
        row=2, col=1
    )

def add_combined_heatmap(fig, Vt, pgs_ids):
    """Add heatmap to combined visualization."""
    n_components_heatmap = min(5, Vt.shape[0])
    n_top_pgs_heatmap = min(20, len(pgs_ids))
    
    overall_importance = np.sum(Vt[:n_components_heatmap, :]**2, axis=0)
    top_indices_heatmap = np.argsort(overall_importance)[::-1][:n_top_pgs_heatmap]
    
    heatmap_data = Vt[:n_components_heatmap, top_indices_heatmap]
    heatmap_pgs_ids = [pgs_ids[idx] for idx in top_indices_heatmap]
    
    fig.add_trace(
        go.Heatmap(
            z=heatmap_data,
            x=heatmap_pgs_ids,
            y=[f'PC{i+1}' for i in range(n_components_heatmap)],
            colorscale='RdBu',
            zmid=0
        ),
        row=2, col=2
    )

def configure_combined_layout(fig, stats):
    """Configure layout for combined visualization."""
    explained_variance_ratio = stats["explained_variance_ratio"]
    
    fig.update_layout(
        title=f'SVD Analysis of {stats["score_type"]} Scores ({stats["num_pgs_ids"]} PGS IDs, {stats["num_samples"]} Samples)',
        height=1000,
        width=1200,
        showlegend=False
    )
    
    # Update axes
    fig.update_xaxes(title_text="Component", row=1, col=1)
    fig.update_yaxes(title_text="Explained Variance", row=1, col=1)
    
    fig.update_xaxes(title_text=f"PC1 ({explained_variance_ratio[0]*100:.1f}%)", row=1, col=2)
    fig.update_yaxes(title_text=f"PC2 ({explained_variance_ratio[1]*100:.1f}%)", row=1, col=2)
    
    fig.update_xaxes(title_text="PGS ID", row=2, col=1, tickangle=45)
    fig.update_yaxes(title_text="Component Weight", row=2, col=1)
    
    fig.update_xaxes(title_text="PGS ID", row=2, col=2, tickangle=45)