import os
import time
import hashlib
import json
import numpy as np
import sqlite3
from datetime import datetime
import plotly.graph_objects as go
from scipy.cluster.hierarchy import linkage, dendrogram
from apps.core.database import DB_PATH
from apps.database.service import fetch_pgs_ids, fetch_pgs_metadata, sample_ids_by_cohort
from apps.multivariate.service import get_matrix

def process_heatmap(request_data):
    try:
        # Create temp directory if it doesn't exist
        os.makedirs("temp", exist_ok=True)
        
        # Extract parameters from request_data
        score_type = request_data["score_type"]
        std_dev_threshold = request_data["std_dev_threshold"]
        dendrogram_view = request_data["dendrogram_view"]
        pgs_ids = request_data["pgs_ids"]
        cohort = request_data["cohort"]
        subcohorts = request_data["subcohorts"]
        max_pgs_ids = request_data.get("max_pgs_ids")
        
        # Generate hash based on request parameters
        request_hash = generate_heatmap_hash(
            score_type,
            std_dev_threshold,
            dendrogram_view,
            pgs_ids,
            cohort,
            subcohorts 
        )

        # Check if we already have a file with this hash
        for filename in os.listdir("temp"):
            if filename.endswith(".html") and request_hash in filename and "heatmap" in filename:
                # Found a cached file, update its access time
                cached_filepath = os.path.join("temp", filename)
                os.utime(cached_filepath)
                
                print(f"Using cached heatmap: {filename}")
                
                # Return file path with empty statistics
                return f"/temp/{filename}"

        # Check and clean up temp directory if needed
        # cleanup_temp_files(max_size_in_gb=10)  

        # Generate filename with hash for future cache hits
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        score_type_safe = score_type.replace("/", "_").replace("\\", "_")
        cohort_indicator = f"{cohort}_" if cohort and cohort != "ALL" else ""
        filename = f"heatmap_{cohort_indicator}{score_type_safe}_{request_hash}_{timestamp}.html"
        filepath = os.path.join("temp", filename)
        
        # Generate the heatmap
        print(f"Large dataset detected. Using static heatmap generator.")
        fig, stats = generate_static_heatmap_for_large_dataset(
            score_type=score_type,
            max_pgs_ids=max_pgs_ids,
            std_dev_threshold=std_dev_threshold,
            dendrogram_view=dendrogram_view,
            specific_pgs_ids=pgs_ids,
            cohort=cohort,
            subcohorts=subcohorts 
        )
        
        # Save the heatmap
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
        print(f"Error generating heatmap: {str(e)}")
        raise e

def generate_static_heatmap_for_large_dataset(score_type='Z_norm2', max_pgs_ids=5500, 
                                             std_dev_threshold=3, dendrogram_view=False, 
                                             specific_pgs_ids=None, cohort=None, subcohorts=None):
    """
    Generate a simplified static heatmap for very large datasets.
    Similar to the regular heatmap but optimized for file size and rendering performance.
    
    Parameters:
    - score_type: The SCORE_TYPE to filter on
    - max_pgs_ids: Maximum number of PGS_IDs to include
    - std_dev_threshold: Number of standard deviations beyond which to cap outliers
    - dendrogram_view: If True, simplifies visualization
    - specific_pgs_ids: List of specific PGS IDs to include
    - cohort: Name of cohort to filter samples (optional)
    
    Returns:
    - fig: Plotly figure object (static version)
    - stats: Tuple containing statistics about the data
    """
    # TODO dendrograms - we may have to change formt altogether? 
    print(f"=== Generating Static Heatmap for Large Dataset ===")
    print(f"Score Type: {score_type}")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get PGS ID list
    pgs_ids = fetch_pgs_ids(specific_pgs_ids, score_type)
    
    # Get metadata for PGS IDs
    pgs_metadata = fetch_pgs_metadata(pgs_ids)
    
    # Get sample IDs
    sample_ids = sample_ids_by_cohort(cohort)

    # Calculate overall statistics for outlier detection
    print("Calculating overall score distribution...")
    cursor.execute("""
        SELECT 
            AVG(SCORE), 
            MIN(SCORE), 
            MAX(SCORE), 
            SQRT(AVG(SCORE * SCORE) - AVG(SCORE) * AVG(SCORE)) AS stdev
        FROM scores
        WHERE SCORE_TYPE = ? AND PGS_ID IN ({})
    """.format(','.join(['?']*len(pgs_ids))),
        [score_type] + pgs_ids)
    
    row = cursor.fetchone()
    avg, min_score, max_score, stdev = row
    
    if stdev is None:  # Handle case where calculation fails
        print("Warning: Standard deviation calculation failed. Using default value.")
        stdev = 1.0
    
    print(f"Score distribution: Mean = {avg:.4f}, Std Dev = {stdev:.4f}")
    
    # Calculate outlier thresholds
    upper_threshold = avg + (std_dev_threshold * stdev)
    lower_threshold = avg - (std_dev_threshold * stdev)
    
    print(f"Outlier thresholds: Lower = {lower_threshold:.4f}, Upper = {upper_threshold:.4f}")
    
    # Count outliers
    cursor.execute("""
        SELECT COUNT(*)
        FROM scores
        WHERE SCORE_TYPE = ? AND PGS_ID IN ({})
        AND (SCORE > ? OR SCORE < ?)
    """.format(','.join(['?']*len(pgs_ids))),
        [score_type] + pgs_ids + [upper_threshold, lower_threshold])
    
    outlier_count = cursor.fetchone()[0]
    print(f"Found {outlier_count} outliers in dataset")
    print("Creating matrix data structure...")
    start_time = time.time()

    matrix, _ = get_matrix(
        sample_ids=sample_ids,
        pgs_ids=pgs_ids,
        score_type=score_type,
        output_format="numpy",  # This will return a numpy matrix directly
        upper_threshold=upper_threshold,
        lower_threshold=lower_threshold
    )
    end_time = time.time()
    print(f"Matrix created in {end_time - start_time:.2f} seconds.")

    # For clustering, we need to temporarily replace NaNs
    clustering_matrix = np.copy(matrix)
    
    print("Preparing data for clustering...")
    # Replace NaNs with column means for row clustering
    for j in range(len(pgs_ids)):
        col = clustering_matrix[:, j]
        valid_values = col[~np.isnan(col)]
        if len(valid_values) > 0:
            col_mean = np.mean(valid_values)
            clustering_matrix[:, j] = np.where(np.isnan(col), col_mean, col)
    
    # Create a transposed matrix for column (PGS_ID) clustering
    clustering_matrix_t = np.copy(matrix).T
    for i in range(len(sample_ids)):
        row = matrix[i, :]
        valid_values = row[~np.isnan(row)]
        if len(valid_values) > 0:
            row_mean = np.mean(valid_values)
            clustering_matrix_t[:, i] = np.where(np.isnan(clustering_matrix_t[:, i]), row_mean, clustering_matrix_t[:, i])
    
    print("Performing hierarchical clustering...")
    
    # Sample (row) clustering
    try:
        # Only use rows that have at least one non-NaN value
        valid_row_indices = np.where(~np.isnan(matrix).all(axis=1))[0]
        if len(valid_row_indices) > 0:
            # Extract valid rows for clustering
            valid_rows = clustering_matrix[valid_row_indices]
            sample_linkage = linkage(valid_rows, method='average')
            sample_dendro = dendrogram(sample_linkage, no_plot=not dendrogram_view)
            
            # Create the full ordering by starting with clustered valid rows
            sample_order = [valid_row_indices[i] for i in sample_dendro['leaves']]
            nan_row_indices = np.where(np.isnan(matrix).all(axis=1))[0]
            sample_order.extend(nan_row_indices)
        else:
            # If no valid rows, use original order
            sample_order = list(range(len(sample_ids)))
            
        ordered_sample_ids = [sample_ids[i] for i in sample_order]
    except Exception as e:
        print(f"Error during sample clustering: {e}. Using original order.")
        sample_order = list(range(len(sample_ids)))
        ordered_sample_ids = sample_ids
    
    # PGS_ID (column) clustering
    try:
        # Only use columns that have at least one non-NaN value
        valid_col_indices = np.where(~np.isnan(matrix).all(axis=0))[0]
        if len(valid_col_indices) > 0:
            # Extract valid columns for clustering
            valid_cols_t = clustering_matrix_t[valid_col_indices]
            pgs_linkage = linkage(valid_cols_t, method='average')
            pgs_dendro = dendrogram(pgs_linkage, no_plot=not dendrogram_view)
            
            # Create the full ordering by starting with clustered valid columns
            pgs_order = [valid_col_indices[i] for i in pgs_dendro['leaves']]
            nan_col_indices = np.where(np.isnan(matrix).all(axis=0))[0]
            pgs_order.extend(nan_col_indices)
        else:
            # If no valid columns, use original order
            pgs_order = list(range(len(pgs_ids)))
            
        ordered_pgs_ids = [pgs_ids[i] for i in pgs_order]
    except Exception as e:
        print(f"Error during PGS_ID clustering: {e}. Using original order.")
        pgs_order = list(range(len(pgs_ids)))
        ordered_pgs_ids = pgs_ids
    
    # Reorder matrix based on both clusterings
    ordered_matrix = matrix[sample_order, :][:, pgs_order]
    
    # Convert to list structure for Plotly
    z_data = ordered_matrix.tolist()
        
    if subcohorts and len(subcohorts) > 0:
        print("Generating heatmap with subcohort-aware clustering...")
        # Pass the original matrix (before clustering) and other necessary data
        subcohort_fig, stats = cluster_with_subcohorts(
            matrix=matrix,  # The original matrix before clustering
            ordered_sample_ids=sample_ids,  # Original sample IDs
            ordered_pgs_ids=ordered_pgs_ids,  # Keep the clustered PGS_ID order
            pgs_metadata=pgs_metadata,
            lower_threshold=lower_threshold,
            upper_threshold=upper_threshold,
            score_type=score_type,
            subcohorts=subcohorts
        )
        return subcohort_fig, stats
        
    # Create hover text matrix with metadata
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

    # Create static heatmap with clustered data
    print("Creating static heatmap visualization with clustering...")
    cohort_text = f" - {cohort} Cohort" if cohort and cohort != "ALL" else ""
    title = f'Heatmap of {score_type} Scores{cohort_text}<br>({len(pgs_ids)} PGS_IDs, {len(sample_ids)} Samples, Clustered)'
    
    fig = go.Figure(data=go.Heatmap(
        z=z_data,
        x=ordered_pgs_ids,  # Use ordered PGS IDs
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
        hoverinfo='text',  # Enable hover info
        text=hover_text,  # Use the hover text we created
        showscale=True
    ))
    
    # Configure layout for performance
    fig.update_layout(
        title=title,
        xaxis=dict(
            showticklabels=False,  # Hide tick labels by default
            showgrid=False,
            zeroline=False,
            hoverformat='.4f'  # Format for hover
        ),
        yaxis=dict(
            showticklabels=False,  # Hide tick labels by default
            showgrid=False,
            zeroline=False
        ),
        width=1000,
        height=800,
        autosize=False,
        margin=dict(l=20, r=20, t=80, b=20),  # Minimal margins
        plot_bgcolor='rgba(0,0,0,0)',  # Transparent background
        paper_bgcolor='white',
        hovermode='closest'  # Enable hover interactions
    )
    
    # Add customized hover behavior with plotly's configuration
    fig.update_layout(
        hoverlabel=dict(
            bgcolor="white",
            font_size=12,
            font_family="Arial"
        )
    )
       # After creating the main heatmap figure, add subcohort annotations if provided
    if subcohorts and len(subcohorts) > 0:
        print(f"Adding {len(subcohorts)} subcohort annotations...")
        
        # Create a mapping from sample_id to row index in the ordered matrix
        sample_id_to_idx = {sample_id: idx for idx, sample_id in enumerate(ordered_sample_ids)}
        
        # For each subcohort, create an annotation trace
        for subcohort in subcohorts:
            # Find which samples from this subcohort are in our dataset
            subcohort_indices = []
            for sample_id in subcohort.sampleIds:
                if sample_id in sample_id_to_idx:
                    subcohort_indices.append(sample_id_to_idx[sample_id])
            
            if not subcohort_indices:
                print(f"Warning: No samples from subcohort '{subcohort.name}' found in dataset")
                continue
                
            print(f"Adding subcohort '{subcohort.name}' with {len(subcohort_indices)} samples")
            
            # Create annotation rectangle for each sample in the subcohort
            for idx in subcohort_indices:
                # Add a thin rectangle at the left edge of the heatmap
                fig.add_shape(
                    type="rect",
                    x0=-0.5,  # Just to the left of the first column
                    x1=-0.1,
                    y0=idx - 0.5,  # Position matches the sample's row
                    y1=idx + 0.5,
                    fillcolor=subcohort.color,
                    opacity=0.8,
                    layer="above",
                    line_width=0,
                )
            fig.add_shape(
                type="rect",
                x0=ordered_pgs_ids[0],  # Ensure it's inside the heatmap area
                x1=ordered_pgs_ids[1], 
                y0=0,
                y1=10,  # Cover multiple rows for visibility
                fillcolor="red",
                opacity=0.8,
                layer="above",
            )
            # Add a legend item for this subcohort
            fig.add_trace(go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                marker=dict(size=10, color=subcohort.color),
                name=subcohort.name,
                legendgroup=subcohort.name,
                showlegend=True
            ))
        
        # Adjust layout to make room for the annotations
        fig.update_layout(
            margin=dict(l=40, r=20, t=80, b=20),  # Increase left margin
            legend=dict(
                title="Subcohorts",
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01,
                bgcolor="rgba(255,255,255,0.8)"
            )
        )
    # Close database connection
    conn.close()
    
    # Return statistics
    stats = (min_score, max_score, None, None, outlier_count)
    return fig, stats

def cluster_with_subcohorts(matrix, ordered_sample_ids, ordered_pgs_ids, pgs_metadata, 
                           lower_threshold, upper_threshold, score_type, subcohorts):
    """
    Generate a single heatmap with subcohort-aware clustering.
    Samples are grouped by subcohorts with each subcohort independently clustered.
    
    Parameters:
    - matrix: The original data matrix (before clustering)
    - ordered_sample_ids: Sample IDs in the order they appear in the matrix
    - ordered_pgs_ids: PGS IDs in the order they appear in the matrix
    - pgs_metadata: Dictionary of metadata for each PGS ID
    - lower_threshold: Lower threshold for color scale
    - upper_threshold: Upper threshold for color scale
    - score_type: Type of score (for labels)
    - subcohorts: List of subcohort objects containing name, color, and sampleIds
    
    Returns:
    - fig: Plotly figure object with subcohort-aware clustering
    - stats: Dictionary containing statistics about each subcohort's data
    """
    
    print(f"=== Generating Heatmap with Subcohort-Aware Clustering ===")
    print(f"Number of subcohorts: {len(subcohorts)}")
    
    # Create a mapping from sample_id to index in the ordered matrix
    sample_id_to_idx = {sample_id: idx for idx, sample_id in enumerate(ordered_sample_ids)}
    
    # Get the set of all sample indices included in subcohorts
    all_subcohort_indices = set()
    for subcohort in subcohorts:
        for sample_id in subcohort.sampleIds:
            if sample_id in sample_id_to_idx:
                all_subcohort_indices.add(sample_id_to_idx[sample_id])
    
    # Determine which samples aren't in any subcohort
    remaining_indices = [i for i in range(len(ordered_sample_ids)) if i not in all_subcohort_indices]
    print(f"Found {len(remaining_indices)} samples not belonging to any subcohort")
    
    # Create a "remaining" subcohort object if we have any remaining samples
    if remaining_indices:
        remaining_subcohort = type('obj', (object,), {
            'name': 'Remaining Samples',
            'color': 'gray',
            'sampleIds': [ordered_sample_ids[i] for i in remaining_indices]
        })
        # Add to the end of subcohorts list
        all_subcohorts = list(subcohorts) + [remaining_subcohort]
    else:
        all_subcohorts = list(subcohorts)
    
    # Create a new ordering of samples based on subcohorts
    # Each subcohort will be clustered independently
    new_sample_order = []
    subcohort_boundaries = []  # To keep track of where each subcohort begins/ends
    current_position = 0
    
    # Process each subcohort
    for subcohort in all_subcohorts:
        print(f"Processing subcohort: {subcohort.name}")
        
        # Find which samples from this subcohort are in our dataset
        subcohort_indices = []
        for sample_id in subcohort.sampleIds:
            if sample_id in sample_id_to_idx:
                subcohort_indices.append(sample_id_to_idx[sample_id])
        
        if not subcohort_indices:
            print(f"Warning: No samples from subcohort '{subcohort.name}' found in dataset")
            continue
        
        print(f"Found {len(subcohort_indices)} samples for subcohort '{subcohort.name}'")
        
        # Extract the submatrix for this subcohort
        subcohort_matrix = matrix[subcohort_indices, :]
        subcohort_sample_ids = [ordered_sample_ids[idx] for idx in subcohort_indices]
        
        # Perform clustering on this submatrix for rows
        # For clustering, we need to temporarily replace NaNs
        clustering_matrix = np.copy(subcohort_matrix)
        
        # Replace NaNs with column means for row clustering
        for j in range(clustering_matrix.shape[1]):
            col = clustering_matrix[:, j]
            valid_values = col[~np.isnan(col)]
            if len(valid_values) > 0:
                col_mean = np.mean(valid_values)
                clustering_matrix[:, j] = np.where(np.isnan(col), col_mean, col)
        
        # Sample (row) clustering for this subcohort
        try:
            # Only use rows that have at least one non-NaN value
            valid_row_indices = np.where(~np.isnan(subcohort_matrix).all(axis=1))[0]
            if len(valid_row_indices) > 0:
                # Extract valid rows for clustering
                valid_rows = clustering_matrix[valid_row_indices]
                if len(valid_rows) > 1:  # Need at least 2 rows for clustering
                    sample_linkage = linkage(valid_rows, method='average')
                    sample_dendro = dendrogram(sample_linkage, no_plot=True)
                    
                    # Create the full ordering by starting with clustered valid rows
                    sample_order = [valid_row_indices[i] for i in sample_dendro['leaves']]
                    nan_row_indices = np.where(np.isnan(subcohort_matrix).all(axis=1))[0]
                    sample_order.extend(nan_row_indices)
                else:
                    sample_order = list(range(len(subcohort_indices)))
            else:
                # If no valid rows, use original order
                sample_order = list(range(len(subcohort_indices)))
        except Exception as e:
            print(f"Error during sample clustering for subcohort: {e}. Using original order.")
            sample_order = list(range(len(subcohort_indices)))
        
        # Add these indices to our new overall ordering
        for idx in sample_order:
            new_sample_order.append(subcohort_indices[idx])
        
        # Record the boundary for this subcohort
        if len(subcohort_indices) > 0:
            if current_position > 0:  # Not the first subcohort
                subcohort_boundaries.append({
                    'name': subcohort.name,
                    'color': subcohort.color,
                    'start': current_position,
                    'size': len(subcohort_indices)
                })
            else:  # First subcohort
                subcohort_boundaries.append({
                    'name': subcohort.name,
                    'color': subcohort.color,
                    'start': 0,
                    'size': len(subcohort_indices)
                })
            current_position += len(subcohort_indices)
              
    # Reorder matrix based on new sample ordering
    # The PGS_ID order remains the same
    new_ordered_matrix = matrix[new_sample_order, :]
    new_ordered_sample_ids = [ordered_sample_ids[i] for i in new_sample_order]
    
    # Convert to list structure for Plotly
    z_data = new_ordered_matrix.tolist()
    
    # Create hover text matrix with metadata
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
    
    # Create static heatmap with subcohort-aware clustering
    print("Creating heatmap visualization with subcohort-aware clustering...")
    title = f'Heatmap of {score_type} Scores<br>({len(ordered_pgs_ids)} PGS_IDs, {len(ordered_sample_ids)} Samples, Subcohort-Clustered)'
    
    fig = go.Figure(data=go.Heatmap(
        z=z_data,
        x=ordered_pgs_ids,  # Use original ordered PGS IDs
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
        hoverinfo='text',  # Enable hover info
        text=hover_text,  # Use the hover text we created
        showscale=True
    ))
    
    # Add horizontal lines to separate subcohorts
    for boundary in subcohort_boundaries[1:]:  # Skip the first boundary (start of first subcohort)
        y_pos = boundary['start'] - 0.5  # Position line between subcohorts
        fig.add_shape(
            type="line",
            x0=-0.5,  # Start at the left edge
            x1=len(ordered_pgs_ids) - 0.5,  # End at the right edge
            y0=y_pos,
            y1=y_pos,
            line=dict(
                color="white",
                width=2,
            ),
            layer="above"
        )
    
    # Add colored rectangles on the left to indicate subcohorts
    for boundary in subcohort_boundaries:
        y0 = boundary['start'] - 0.5
        y1 = boundary['start'] + boundary['size'] - 0.5
        fig.add_shape(
            type="rect",
            x0=-0.5,  # Left of the heatmap
            x1=-0.1,  # Width of the indicator
            y0=y0,
            y1=y1,
            fillcolor=boundary['color'],
            opacity=0.8,
            layer="above",
            line_width=0,
        )
        
        # Add a text label for the subcohort
        fig.add_annotation(
            x=-0.3,  # Position of the text
            y=(y0 + y1) / 2,  # Middle of the subcohort
            text=boundary['name'],
            showarrow=False,
            textangle=-90,  # Vertical text
            xanchor="center",
            yanchor="middle",
            font=dict(
                color="white",
                size=10
            )
        )
    
    # Add legend entries for each subcohort
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
    
    # Configure layout
    fig.update_layout(
        title=title,
        xaxis=dict(
            showticklabels=False,  # Hide tick labels by default
            showgrid=False,
            zeroline=False,
            hoverformat='.4f'  # Format for hover
        ),
        yaxis=dict(
            showticklabels=False,  # Hide tick labels by default
            showgrid=False,
            zeroline=False
        ),
        width=1000,
        height=800,
        autosize=False,
        margin=dict(l=60, r=20, t=80, b=20),  # Increased left margin for subcohort labels
        plot_bgcolor='rgba(0,0,0,0)',  # Transparent background
        paper_bgcolor='white',
        hovermode='closest',  # Enable hover interactions
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
    
    return fig, (0, 0, None, None, 0)

def cleanup_temp_files(max_size_in_gb=10):
    """
    Cleans up temporary heatmap files when the directory exceeds the specified size limit.
    
    Args:
        max_size_in_gb: Maximum allowed size of the temp directory in GB
    """
    temp_dir = "temp"
    max_size_in_bytes = max_size_in_gb * 1024 * 1024 * 1024
    
    # Check if the directory exists
    if not os.path.exists(temp_dir):
        return
    
    # Get all HTML files in the temp directory with their stats
    files = []
    total_size = 0
    
    for filename in os.listdir(temp_dir):
        if filename.endswith(".html"):
            filepath = os.path.join(temp_dir, filename)
            file_stats = os.stat(filepath)
            file_size = file_stats.st_size
            access_time = file_stats.st_atime  # Last access time
            
            files.append({
                "path": filepath,
                "size": file_size,
                "last_accessed": access_time
            })
            
            total_size += file_size
    
    print(f"Current temp directory size: {total_size / (1024 * 1024):.2f} MB")
    
    # If we're under the limit, do nothing
    if total_size <= max_size_in_bytes:
        return
    
    print(f"Temp directory size ({total_size / (1024 * 1024 * 1024):.2f} GB) exceeds limit of {max_size_in_gb} GB")
    
    # Sort files by last access time (oldest first)
    files.sort(key=lambda x: x["last_accessed"])
    
    # Remove files until we're under the limit
    deleted_count = 0
    freed_space = 0
    
    while total_size > max_size_in_bytes and files:
        file_to_remove = files.pop(0)  # Get the oldest file
        
        try:
            os.remove(file_to_remove["path"])
            freed_space += file_to_remove["size"]
            total_size -= file_to_remove["size"]
            deleted_count += 1
            print(f"Deleted: {os.path.basename(file_to_remove['path'])}")
        except Exception as e:
            print(f"Error deleting {file_to_remove['path']}: {e}")
    
    print(f"Cleanup complete: Deleted {deleted_count} files, freed {freed_space / (1024 * 1024):.2f} MB")

def generate_heatmap_hash(score_type, std_dev_threshold, dendrogram_view, pgs_ids, cohort=None, subcohort=None):
    """
    Generate a consistent hash based on heatmap request parameters.
    
    Args:
        score_type: The type of score to display
        std_dev_threshold: Threshold for outlier detection
        dendrogram_view: Whether compact view is enabled
        pgs_ids: List of PGS IDs to include
        cohort: Selected sample cohort
    
    Returns:
        str: A hash string representing the request parameters
    """
    
    all_subcohort_sample_ids = []
    if subcohort:
        for c in subcohort:
            all_subcohort_sample_ids.extend(c.sampleIds)
        all_subcohort_sample_ids = sorted(all_subcohort_sample_ids)

    # Create a dictionary of parameters
    params = {
        "score_type": score_type,
        "std_dev_threshold": std_dev_threshold,
        "dendrogram_view": dendrogram_view,
        "pgs_ids": sorted(pgs_ids) if pgs_ids else [],  
        "cohort": cohort,
        "subcohort": all_subcohort_sample_ids
    }
    
    # Convert to JSON string
    param_str = json.dumps(params, sort_keys=True)
    
    # Generate hash
    hash_obj = hashlib.md5(param_str.encode())
    return hash_obj.hexdigest()
