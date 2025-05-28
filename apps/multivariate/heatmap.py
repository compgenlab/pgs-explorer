import os
import time
import hashlib
import json
import numpy as np
import sqlite3
from datetime import datetime
import plotly.graph_objects as go
from scipy.cluster.hierarchy import linkage, dendrogram
from apps.core.utils import generate_request_hash
from database import db

def process_heatmap(request_data):
    """
    Entry point for heatmap generation.
    """
    try:
        # Create temp directory if it doesn't exist
        os.makedirs("temp", exist_ok=True)
        
        # Check if already cached
        existing, html_path, json_path = generate_request_hash(request_data)
        if existing:
            return f"/{html_path}"

        # Extract parameters
        params = extract_heatmap_parameters(request_data)
        
        # Generate the heatmap
        print(f"Starting heatmap generation.")
        fig, stats = generate_static_heatmap_for_large_dataset(**params)
        
        # Save the heatmap
        save_heatmap_to_file(fig, html_path)
        
        # Save the data
        save_data_to_json({"stats": stats}, json_path)

        return f"/{html_path}"
        
    except Exception as e:
        print(f"Error generating heatmap: {str(e)}")
        raise e

### REGULAR HEATMAP FUNCTIONS

def extract_heatmap_parameters(request_data):
    """Extract and validate parameters from request data."""
    return {
        "score_type": request_data["score_type"],
        "std_dev_threshold": request_data["std_dev_threshold"],
        "dendrogram_view": request_data["dendrogram_view"],
        "specific_pgs_ids": request_data["pgs_ids"],
        "cohort": request_data["cohort"],
        "subcohorts": request_data["subcohorts"],
        "max_pgs_ids": request_data.get("max_pgs_ids")
    }

def save_heatmap_to_file(fig, filepath):
    """Save Plotly figure to HTML file."""
    fig.write_html(
        filepath,
        include_plotlyjs='cdn',
        include_mathjax=False,
        config={
            'displayModeBar': False,
            'responsive': True
        }
    )

def save_data_to_json(data, filepath):
    """Save data dictionary to JSON file."""
    with open(filepath, 'w') as f:
        json.dump(data, f)

def generate_static_heatmap_for_large_dataset(score_type='Z_norm2', max_pgs_ids=5500, 
                                             std_dev_threshold=3, dendrogram_view=False, 
                                             specific_pgs_ids=None, cohort=None, subcohorts=None):
    """
    Generate a simplified static heatmap for very large datasets.
    """
    # Fetch required data
    data = fetch_heatmap_data(score_type, specific_pgs_ids, cohort)
    
    # Calculate statistics and thresholds
    stats_data = calculate_statistics_and_thresholds(
        score_type, data['pgs_ids'], std_dev_threshold
    )
    
    # Get the data matrix
    matrix, _ = fetch_score_matrix(
        data['sample_ids'], data['pgs_ids'], score_type,
        stats_data['upper_threshold'], stats_data['lower_threshold']
    )
    
    # Handle subcohort clustering if needed
    if subcohorts and len(subcohorts) > 0:
        return generate_subcohort_clustered_heatmap(
            matrix, data, stats_data, score_type, subcohorts
        )
    
    # Perform clustering
    clustering_result = perform_hierarchical_clustering(
        matrix, data['sample_ids'], data['pgs_ids'], dendrogram_view
    )
    
    # Create hover text
    hover_text = create_hover_text_matrix(
        clustering_result['ordered_matrix'],
        clustering_result['sample_order'],
        clustering_result['pgs_order'],
        data['sample_ids'],
        data['pgs_ids'],
        data['pgs_metadata']
    )
    
    # Create the figure
    fig = create_heatmap_figure(
        clustering_result['ordered_matrix'],
        clustering_result['ordered_pgs_ids'],
        hover_text,
        stats_data['lower_threshold'],
        stats_data['upper_threshold'],
        score_type,
        cohort,
        len(data['pgs_ids']),
        len(data['sample_ids'])
    )
    
    # Configure layout
    configure_heatmap_layout(fig)
    
    # Add subcohort annotations if provided
    if subcohorts and len(subcohorts) > 0:
        add_subcohort_annotations(fig, subcohorts, clustering_result['ordered_sample_ids'])
    
    # Return figure and stats
    stats = (
        stats_data['min_score'],
        stats_data['max_score'],
        None,
        None,
        stats_data['outlier_count']
    )
    return fig, stats

def fetch_heatmap_data(score_type, specific_pgs_ids, cohort):
    """Fetch all required data for heatmap generation."""
    pgs_ids = db.scores.fetch_pgs_ids(
        specific_pgs_ids=specific_pgs_ids,
        score_type=score_type
    )
    pgs_metadata = db.metadata.fetch_pgs_metadata(pgs_ids=pgs_ids)
    sample_ids = db.ancestry.sample_ids_by_cohort(cohort)
    
    return {
        'pgs_ids': pgs_ids,
        'pgs_metadata': pgs_metadata,
        'sample_ids': sample_ids
    }

def calculate_statistics_and_thresholds(score_type, pgs_ids, std_dev_threshold):
    """Calculate statistics and outlier thresholds."""
    print("Calculating overall score distribution...")
    
    # Get all statistics in one call
    stats = db.scores.get_score_statistics_with_outliers(
        score_type, 
        pgs_ids, 
        std_dev_threshold
    )
    
    print(f"Score distribution: Mean = {stats['avg']:.4f}, Std Dev = {stats['stdev']:.4f}")
    print(f"Outlier thresholds: Lower = {stats['lower_threshold']:.4f}, Upper = {stats['upper_threshold']:.4f}")
    print(f"Found {stats['outlier_count']} outliers in dataset")
    
    return {
        'avg': stats['avg'],
        'min_score': stats['min'],
        'max_score': stats['max'],
        'stdev': stats['stdev'],
        'upper_threshold': stats['upper_threshold'],
        'lower_threshold': stats['lower_threshold'],
        'outlier_count': stats['outlier_count']
    }
    
def fetch_score_matrix(sample_ids, pgs_ids, score_type, upper_threshold, lower_threshold):
    """Fetch the score matrix from database."""
    print("Creating matrix data structure...")
    start_time = time.time()
    
    matrix, pgs_list = db.scores.get_matrix(
        sample_ids=sample_ids,
        pgs_ids=pgs_ids,
        score_type=score_type,
        output_format="numpy",
        upper_threshold=upper_threshold,
        lower_threshold=lower_threshold
    )
    
    end_time = time.time()
    print(f"Matrix created in {end_time - start_time:.2f} seconds.")
    
    return matrix, pgs_list

def prepare_matrix_for_clustering(matrix, sample_ids, pgs_ids):
    """Prepare matrices for clustering by replacing NaNs with appropriate values."""
    print("Preparing data for clustering...")
    
    # For row clustering
    clustering_matrix = np.copy(matrix)
    for j in range(len(pgs_ids)):
        col = clustering_matrix[:, j]
        valid_values = col[~np.isnan(col)]
        if len(valid_values) > 0:
            col_mean = np.mean(valid_values)
            clustering_matrix[:, j] = np.where(np.isnan(col), col_mean, col)
    
    # For column clustering
    clustering_matrix_t = np.copy(matrix).T
    for i in range(len(sample_ids)):
        row = matrix[i, :]
        valid_values = row[~np.isnan(row)]
        if len(valid_values) > 0:
            row_mean = np.mean(valid_values)
            clustering_matrix_t[:, i] = np.where(
                np.isnan(clustering_matrix_t[:, i]),
                row_mean,
                clustering_matrix_t[:, i]
            )
    
    return clustering_matrix, clustering_matrix_t

def cluster_samples(matrix, clustering_matrix, sample_ids, dendrogram_view):
    """Perform hierarchical clustering on samples (rows)."""
    try:
        valid_row_indices = np.where(~np.isnan(matrix).all(axis=1))[0]
        
        if len(valid_row_indices) > 0:
            valid_rows = clustering_matrix[valid_row_indices]
            sample_linkage = linkage(valid_rows, method='average')
            sample_dendro = dendrogram(sample_linkage, no_plot=not dendrogram_view)
            
            sample_order = [valid_row_indices[i] for i in sample_dendro['leaves']]
            nan_row_indices = np.where(np.isnan(matrix).all(axis=1))[0]
            sample_order.extend(nan_row_indices)
        else:
            sample_order = list(range(len(sample_ids)))
        
        ordered_sample_ids = [sample_ids[i] for i in sample_order]
        return sample_order, ordered_sample_ids
        
    except Exception as e:
        print(f"Error during sample clustering: {e}. Using original order.")
        return list(range(len(sample_ids))), sample_ids

def cluster_pgs_ids(matrix, clustering_matrix_t, pgs_ids, dendrogram_view):
    """Perform hierarchical clustering on PGS IDs (columns)."""
    try:
        valid_col_indices = np.where(~np.isnan(matrix).all(axis=0))[0]
        
        if len(valid_col_indices) > 0:
            valid_cols_t = clustering_matrix_t[valid_col_indices]
            pgs_linkage = linkage(valid_cols_t, method='average')
            pgs_dendro = dendrogram(pgs_linkage, no_plot=not dendrogram_view)
            
            pgs_order = [valid_col_indices[i] for i in pgs_dendro['leaves']]
            nan_col_indices = np.where(np.isnan(matrix).all(axis=0))[0]
            pgs_order.extend(nan_col_indices)
        else:
            pgs_order = list(range(len(pgs_ids)))
        
        ordered_pgs_ids = [pgs_ids[i] for i in pgs_order]
        return pgs_order, ordered_pgs_ids
        
    except Exception as e:
        print(f"Error during PGS_ID clustering: {e}. Using original order.")
        return list(range(len(pgs_ids))), pgs_ids

def perform_hierarchical_clustering(matrix, sample_ids, pgs_ids, dendrogram_view):
    """Perform hierarchical clustering on both samples and PGS IDs."""
    print("Performing hierarchical clustering...")
    
    # Prepare matrices for clustering
    clustering_matrix, clustering_matrix_t = prepare_matrix_for_clustering(
        matrix, sample_ids, pgs_ids
    )
    
    # Cluster samples
    sample_order, ordered_sample_ids = cluster_samples(
        matrix, clustering_matrix, sample_ids, dendrogram_view
    )
    
    # Cluster PGS IDs
    pgs_order, ordered_pgs_ids = cluster_pgs_ids(
        matrix, clustering_matrix_t, pgs_ids, dendrogram_view
    )
    
    # Reorder matrix
    ordered_matrix = matrix[sample_order, :][:, pgs_order]
    
    return {
        'ordered_matrix': ordered_matrix,
        'sample_order': sample_order,
        'pgs_order': pgs_order,
        'ordered_sample_ids': ordered_sample_ids,
        'ordered_pgs_ids': ordered_pgs_ids
    }

def create_hover_text_matrix(ordered_matrix, sample_order, pgs_order, 
                           sample_ids, pgs_ids, pgs_metadata):
    """Create hover text matrix with metadata."""
    hover_text = []
    
    for i, sample_idx in enumerate(sample_order):
        sample_id = sample_ids[sample_idx]
        hover_row = []
        
        for j, pgs_idx in enumerate(pgs_order):
            pgs_id = pgs_ids[pgs_idx]
            score = ordered_matrix[i, j]
            
            if not np.isnan(score):
                metadata = pgs_metadata.get(pgs_id, {})
                hover_text_cell = (
                    f"PGS ID: {pgs_id}<br>"
                    f"Publication_ID: {metadata.get('Publication_ID', 'N/A')}<br>"
                    f"Sample ID: {sample_id}<br>"
                    f"Score: {score:.4f}<br>"
                    f"Trait: {metadata.get('Reported_Trait', 'N/A')}"
                )
                hover_row.append(hover_text_cell)
            else:
                hover_row.append("")
                
        hover_text.append(hover_row)
    
    return hover_text

def create_heatmap_figure(ordered_matrix, ordered_pgs_ids, hover_text,
                         lower_threshold, upper_threshold, score_type,
                         cohort, num_pgs, num_samples):
    """Create the Plotly heatmap figure."""
    print("Creating static heatmap visualization with clustering...")
    
    # Convert matrix to list for Plotly
    z_data = ordered_matrix.tolist()
    
    # Create title
    cohort_text = f" - {cohort} Cohort" if cohort and cohort != "ALL" else ""
    title = f'Heatmap of {score_type} Scores{cohort_text}<br>({num_pgs} PGS_IDs, {num_samples} Samples, Clustered)'
    
    # Create figure
    fig = go.Figure(data=go.Heatmap(
        z=z_data,
        x=ordered_pgs_ids,
        y=None,  # Don't show sample IDs for large datasets
        colorscale='Viridis',
        colorbar=dict(
            title=f'{score_type} Score',
            tickvals=[lower_threshold, upper_threshold],
            ticktext=[f"{lower_threshold:.2f}", f"{upper_threshold:.2f}"]
        ),
        zmin=lower_threshold,
        zmax=upper_threshold,
        connectgaps=False,
        hoverinfo='text',
        text=hover_text,
        showscale=True
    ))
    
    return fig

def configure_heatmap_layout(fig):
    """Configure the layout settings for the heatmap."""
    fig.update_layout(
        xaxis=dict(
            showticklabels=False,
            showgrid=False,
            zeroline=False,
            hoverformat='.4f'
        ),
        yaxis=dict(
            showticklabels=False,
            showgrid=False,
            zeroline=False
        ),
        width=1000,
        height=800,
        autosize=False,
        margin=dict(l=20, r=20, t=80, b=20),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='white',
        hovermode='closest',
        hoverlabel=dict(
            bgcolor="white",
            font_size=12,
            font_family="Arial"
        )
    )

def add_subcohort_annotations(fig, subcohorts, ordered_sample_ids):
    """Add subcohort annotations to the heatmap."""
    print(f"Adding {len(subcohorts)} subcohort annotations...")
    
    # Create sample ID to index mapping
    sample_id_to_idx = {sample_id: idx for idx, sample_id in enumerate(ordered_sample_ids)}
    
    for subcohort in subcohorts:
        # Find indices for this subcohort
        subcohort_indices = []
        for sample_id in subcohort.sampleIds:
            if sample_id in sample_id_to_idx:
                subcohort_indices.append(sample_id_to_idx[sample_id])
        
        if not subcohort_indices:
            print(f"Warning: No samples from subcohort '{subcohort.name}' found in dataset")
            continue
        
        print(f"Adding subcohort '{subcohort.name}' with {len(subcohort_indices)} samples")
        
        # Add rectangles for each sample
        for idx in subcohort_indices:
            fig.add_shape(
                type="rect",
                x0=-0.5,
                x1=-0.1,
                y0=idx - 0.5,
                y1=idx + 0.5,
                fillcolor=subcohort.color,
                opacity=0.8,
                layer="above",
                line_width=0,
            )
        
        # Add legend entry
        fig.add_trace(go.Scatter(
            x=[None],
            y=[None],
            mode="markers",
            marker=dict(size=10, color=subcohort.color),
            name=subcohort.name,
            legendgroup=subcohort.name,
            showlegend=True
        ))
    
    # Update layout for annotations
    fig.update_layout(
        margin=dict(l=40, r=20, t=80, b=20),
        legend=dict(
            title="Subcohorts",
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01,
            bgcolor="rgba(255,255,255,0.8)"
        )
    )

def generate_subcohort_clustered_heatmap(matrix, data, stats_data, score_type, subcohorts):
    """Generate heatmap with subcohort-aware clustering."""
    print("Generating heatmap with subcohort-aware clustering...")
    
    subcohort_fig, stats = cluster_with_subcohorts(
        matrix=matrix,
        ordered_sample_ids=data['sample_ids'],
        ordered_pgs_ids=data['pgs_ids'],
        pgs_metadata=data['pgs_metadata'],
        lower_threshold=stats_data['lower_threshold'],
        upper_threshold=stats_data['upper_threshold'],
        score_type=score_type,
        subcohorts=subcohorts
    )
    
    return subcohort_fig, stats

### SUBCOHORT HEATMAP FUNCTIONS 

def cluster_with_subcohorts(matrix, ordered_sample_ids, ordered_pgs_ids, pgs_metadata, 
                           lower_threshold, upper_threshold, score_type, subcohorts):
    """
    Generate a single heatmap with subcohort-aware clustering.
    Samples are grouped by subcohorts with each subcohort independently clustered.
    """
    print(f"=== Generating Heatmap with Subcohort-Aware Clustering ===")
    print(f"Number of subcohorts: {len(subcohorts)}")
    
    # Prepare subcohort data
    sample_id_to_idx = create_sample_index_mapping(ordered_sample_ids)
    all_subcohorts = prepare_subcohorts_with_remaining(
        subcohorts, ordered_sample_ids, sample_id_to_idx
    )
    
    # Perform subcohort clustering
    clustering_result = perform_subcohort_clustering(
        matrix, ordered_sample_ids, all_subcohorts, sample_id_to_idx
    )
    
    # Create hover text
    hover_text = create_subcohort_hover_text(
        clustering_result['new_ordered_matrix'],
        clustering_result['new_sample_order'],
        ordered_sample_ids,
        ordered_pgs_ids,
        pgs_metadata
    )
    
    # Create the figure
    fig = create_subcohort_heatmap_figure(
        clustering_result['new_ordered_matrix'],
        ordered_pgs_ids,
        hover_text,
        lower_threshold,
        upper_threshold,
        score_type,
        len(ordered_sample_ids)
    )
    
    # Add visual elements
    add_subcohort_separators(fig, clustering_result['subcohort_boundaries'], ordered_pgs_ids)
    add_subcohort_indicators(fig, clustering_result['subcohort_boundaries'])
    add_subcohort_labels(fig, clustering_result['subcohort_boundaries'])
    add_subcohort_legend(fig, clustering_result['subcohort_boundaries'])
    
    # Configure layout
    configure_subcohort_layout(fig)
    
    return fig, (0, 0, None, None, 0)

def create_sample_index_mapping(ordered_sample_ids):
    """Create a mapping from sample ID to its index in the matrix."""
    return {sample_id: idx for idx, sample_id in enumerate(ordered_sample_ids)}

def prepare_subcohorts_with_remaining(subcohorts, ordered_sample_ids, sample_id_to_idx):
    """
    Prepare subcohorts list, adding a 'remaining samples' subcohort if needed.
    """
    # Get all sample indices that are in subcohorts
    all_subcohort_indices = set()
    for subcohort in subcohorts:
        for sample_id in subcohort.sampleIds:
            if sample_id in sample_id_to_idx:
                all_subcohort_indices.add(sample_id_to_idx[sample_id])
    
    # Find remaining samples
    remaining_indices = [i for i in range(len(ordered_sample_ids)) 
                        if i not in all_subcohort_indices]
    
    print(f"Found {len(remaining_indices)} samples not belonging to any subcohort")
    
    # Create list with all subcohorts
    all_subcohorts = list(subcohorts)
    
    # Add remaining samples as a subcohort if any exist
    if remaining_indices:
        remaining_subcohort = create_remaining_subcohort(
            ordered_sample_ids, remaining_indices
        )
        all_subcohorts.append(remaining_subcohort)
    
    return all_subcohorts

def create_remaining_subcohort(ordered_sample_ids, remaining_indices):
    """Create a subcohort object for remaining samples."""
    return type('obj', (object,), {
        'name': 'Remaining Samples',
        'color': 'gray',
        'sampleIds': [ordered_sample_ids[i] for i in remaining_indices]
    })

def perform_subcohort_clustering(matrix, ordered_sample_ids, all_subcohorts, sample_id_to_idx):
    """
    Perform clustering within each subcohort and create new sample ordering.
    """
    new_sample_order = []
    subcohort_boundaries = []
    current_position = 0
    
    for subcohort in all_subcohorts:
        # Process individual subcohort
        subcohort_result = process_single_subcohort(
            subcohort, matrix, ordered_sample_ids, sample_id_to_idx, current_position
        )
        
        if subcohort_result:
            new_sample_order.extend(subcohort_result['ordered_indices'])
            subcohort_boundaries.append(subcohort_result['boundary'])
            current_position += subcohort_result['size']
    
    # Reorder matrix based on new ordering
    new_ordered_matrix = matrix[new_sample_order, :]
    new_ordered_sample_ids = [ordered_sample_ids[i] for i in new_sample_order]
    
    return {
        'new_ordered_matrix': new_ordered_matrix,
        'new_ordered_sample_ids': new_ordered_sample_ids,
        'new_sample_order': new_sample_order,
        'subcohort_boundaries': subcohort_boundaries
    }

def process_single_subcohort(subcohort, matrix, ordered_sample_ids, sample_id_to_idx, current_position):
    """Process clustering for a single subcohort."""
    print(f"Processing subcohort: {subcohort.name}")
    
    # Get indices for this subcohort
    subcohort_indices = get_subcohort_indices(subcohort, sample_id_to_idx)
    
    if not subcohort_indices:
        print(f"Warning: No samples from subcohort '{subcohort.name}' found in dataset")
        return None
    
    print(f"Found {len(subcohort_indices)} samples for subcohort '{subcohort.name}'")
    
    # Extract submatrix
    subcohort_matrix = matrix[subcohort_indices, :]
    
    # Cluster the subcohort
    sample_order = cluster_subcohort_samples(subcohort_matrix)
    
    # Create ordered indices
    ordered_indices = [subcohort_indices[idx] for idx in sample_order]
    
    # Create boundary information
    boundary = {
        'name': subcohort.name,
        'color': subcohort.color,
        'start': current_position,
        'size': len(subcohort_indices)
    }
    
    return {
        'ordered_indices': ordered_indices,
        'boundary': boundary,
        'size': len(subcohort_indices)
    }

def get_subcohort_indices(subcohort, sample_id_to_idx):
    """Get matrix indices for samples in a subcohort."""
    indices = []
    for sample_id in subcohort.sampleIds:
        if sample_id in sample_id_to_idx:
            indices.append(sample_id_to_idx[sample_id])
    return indices

def cluster_subcohort_samples(subcohort_matrix):
    """Perform hierarchical clustering on samples within a subcohort."""
    # Prepare matrix for clustering
    clustering_matrix = prepare_subcohort_matrix_for_clustering(subcohort_matrix)
    
    try:
        # Find valid rows
        valid_row_indices = np.where(~np.isnan(subcohort_matrix).all(axis=1))[0]
        
        if len(valid_row_indices) > 0:
            valid_rows = clustering_matrix[valid_row_indices]
            
            if len(valid_rows) > 1:  # Need at least 2 rows for clustering
                # Perform clustering
                sample_linkage = linkage(valid_rows, method='average')
                sample_dendro = dendrogram(sample_linkage, no_plot=True)
                
                # Create ordering
                sample_order = [valid_row_indices[i] for i in sample_dendro['leaves']]
                
                # Add any NaN-only rows at the end
                nan_row_indices = np.where(np.isnan(subcohort_matrix).all(axis=1))[0]
                sample_order.extend(nan_row_indices)
            else:
                sample_order = list(range(len(subcohort_matrix)))
        else:
            sample_order = list(range(len(subcohort_matrix)))
            
    except Exception as e:
        print(f"Error during sample clustering for subcohort: {e}. Using original order.")
        sample_order = list(range(len(subcohort_matrix)))
    
    return sample_order

def prepare_subcohort_matrix_for_clustering(subcohort_matrix):
    """Prepare a subcohort matrix for clustering by replacing NaNs with column means."""
    clustering_matrix = np.copy(subcohort_matrix)
    
    for j in range(clustering_matrix.shape[1]):
        col = clustering_matrix[:, j]
        valid_values = col[~np.isnan(col)]
        if len(valid_values) > 0:
            col_mean = np.mean(valid_values)
            clustering_matrix[:, j] = np.where(np.isnan(col), col_mean, col)
    
    return clustering_matrix

def create_subcohort_hover_text(new_ordered_matrix, new_sample_order, 
                               ordered_sample_ids, ordered_pgs_ids, pgs_metadata):
    """Create hover text matrix for subcohort heatmap."""
    hover_text = []
    
    for i, sample_idx in enumerate(new_sample_order):
        sample_id = ordered_sample_ids[sample_idx]
        hover_row = []
        
        for j, pgs_id in enumerate(ordered_pgs_ids):
            score = new_ordered_matrix[i, j]
            
            if not np.isnan(score):
                metadata = pgs_metadata.get(pgs_id, {})
                hover_text_cell = (
                    f"PGS ID: {pgs_id}<br>"
                    f"Publication_ID: {metadata.get('Publication_ID', 'N/A')}<br>"
                    f"Sample ID: {sample_id}<br>"
                    f"Score: {score:.4f}<br>"
                    f"Trait: {metadata.get('Reported_Trait', 'N/A')}"
                )
                hover_row.append(hover_text_cell)
            else:
                hover_row.append("")
                
        hover_text.append(hover_row)
    
    return hover_text

def create_subcohort_heatmap_figure(matrix, ordered_pgs_ids, hover_text,
                                   lower_threshold, upper_threshold, 
                                   score_type, num_samples):
    """Create the Plotly heatmap figure for subcohort clustering."""
    print("Creating heatmap visualization with subcohort-aware clustering...")
    
    # Convert matrix to list
    z_data = matrix.tolist()
    
    # Create title
    title = (f'Heatmap of {score_type} Scores<br>'
            f'({len(ordered_pgs_ids)} PGS_IDs, {num_samples} Samples, Subcohort-Clustered)')
    
    # Create figure
    fig = go.Figure(data=go.Heatmap(
        z=z_data,
        x=ordered_pgs_ids,
        y=None,  # Don't show sample IDs for large datasets
        colorscale='Viridis',
        colorbar=dict(
            title=f'{score_type} Score',
            tickvals=[lower_threshold, upper_threshold],
            ticktext=[f"{lower_threshold:.2f}", f"{upper_threshold:.2f}"]
        ),
        zmin=lower_threshold,
        zmax=upper_threshold,
        connectgaps=False,
        hoverinfo='text',
        text=hover_text,
        showscale=True
    ))
    
    return fig

def add_subcohort_separators(fig, subcohort_boundaries, ordered_pgs_ids):
    """Add horizontal lines to separate subcohorts."""
    for boundary in subcohort_boundaries[1:]:  # Skip first boundary
        y_pos = boundary['start'] - 0.5
        fig.add_shape(
            type="line",
            x0=-0.5,
            x1=len(ordered_pgs_ids) - 0.5,
            y0=y_pos,
            y1=y_pos,
            line=dict(color="white", width=2),
            layer="above"
        )

def add_subcohort_indicators(fig, subcohort_boundaries):
    """Add colored rectangles on the left to indicate subcohorts."""
    for boundary in subcohort_boundaries:
        y0 = boundary['start'] - 0.5
        y1 = boundary['start'] + boundary['size'] - 0.5
        fig.add_shape(
            type="rect",
            x0=-0.5,
            x1=-0.1,
            y0=y0,
            y1=y1,
            fillcolor=boundary['color'],
            opacity=0.8,
            layer="above",
            line_width=0,
            )

def add_subcohort_labels(fig, subcohort_boundaries):
    """Add text labels for each subcohort."""
    for boundary in subcohort_boundaries:
        y0 = boundary['start'] - 0.5
        y1 = boundary['start'] + boundary['size'] - 0.5
        fig.add_annotation(
            x=-0.3,
            y=(y0 + y1) / 2,
            text=boundary['name'],
            showarrow=False,
            textangle=-90,
            xanchor="center",
            yanchor="middle",
            font=dict(color="white", size=10)
        )

def add_subcohort_legend(fig, subcohort_boundaries):
    """Add legend entries for each subcohort."""
    for boundary in subcohort_boundaries:
        fig.add_trace(go.Scatter(
            x=[None],
            y=[None],
            mode="markers",
            marker=dict(size=10, color=boundary['color']),
            name=f"{boundary['name']} ({boundary['size']} samples)",
            legendgroup=boundary['name'],
            showlegend=True
        ))

def configure_subcohort_layout(fig):
    """Configure the layout for subcohort heatmap."""
    fig.update_layout(
        xaxis=dict(
            showticklabels=False,
            showgrid=False,
            zeroline=False,
            hoverformat='.4f'
        ),
        yaxis=dict(
            showticklabels=False,
            showgrid=False,
            zeroline=False
        ),
        width=1000,
        height=800,
        autosize=False,
        margin=dict(l=60, r=20, t=80, b=20),  # Increased left margin for labels
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='white',
        hovermode='closest',
        hoverlabel=dict(
            bgcolor="white",
            font_size=12,
            font_family="Arial"
        ),
        legend=dict(
            title="Subcohorts",
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01,
            bgcolor="rgba(255,255,255,0.8)"
        )
    )