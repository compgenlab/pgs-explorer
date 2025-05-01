import os
import json
import time
import hashlib
import numpy as np
import sqlite3
from datetime import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from apps.core.database import DB_PATH
from apps.multivariate.service import get_matrix

def process_svd(request_data):
    try:
        # Create temp directory if it doesn't exist
        os.makedirs("temp", exist_ok=True)
        
        # Extract parameters from request_data
        score_type = request_data["score_type"]
        pgs_ids = request_data["pgs_ids"]
        cohort = request_data["cohort"]
        plot_type = request_data["plot_type"]
        perspective = request_data.get("perspective", "sample")  # Default to sample
        max_vectors = request_data.get("max_vectors", 10)  # Default to 10
        
        # Generate hash for caching
        request_hash = generate_svd_hash(
            score_type,
            pgs_ids,
            cohort,
            plot_type,
            perspective,
            max_vectors
        )
        
        # Check if we already have a file with this hash
        for filename in os.listdir("temp"):
            if filename.endswith(".html") and request_hash in filename and "svd" in filename:
                # Found a cached file, update its access time
                cached_filepath = os.path.join("temp", filename)
                os.utime(cached_filepath)
                
                print(f"Using cached SVD visualization: {filename}")
                
                # Return file path
                return f"/temp/{filename}"
        
        # First, perform SVD analysis to get the matrices
        U, S, Vt, pgs_ids, sample_ids, stats = perform_svd_analysis(
            score_type=score_type,
            specific_pgs_ids=pgs_ids,
            cohort=cohort
        )
        
        # Generate filename with hash
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        score_type_safe = score_type.replace("/", "_").replace("\\", "_")
        cohort_indicator = f"{cohort}_" if cohort and cohort != "ALL" else ""
        filename = f"svd_{cohort_indicator}{score_type_safe}_{plot_type}_{request_hash}_{timestamp}.html"
        filepath = os.path.join("temp", filename)
        
        # Route to the appropriate visualization function
        if plot_type == "scree":
            fig = generate_svd_scree_plot(S, stats)
        elif plot_type == "biplot":
            if perspective == "score":
                fig = generate_svd_biplot_score(U, S, Vt, pgs_ids, sample_ids, stats, max_vectors=max_vectors)
            else:  # Default to sample perspective
                fig = generate_svd_biplot_sample(U, S, Vt, pgs_ids, sample_ids, stats, max_vectors=max_vectors)
        elif plot_type == "component_weights":
            fig = generate_svd_component_weights(Vt, pgs_ids, stats)
        elif plot_type == "heatmap":
            fig = generate_svd_heatmap(Vt, pgs_ids, stats)
        elif plot_type == "combined":
            fig = generate_svd_combined(U, S, Vt, pgs_ids, sample_ids, stats)
        
        # Save the figure to HTML
        fig.write_html(
            filepath,
            include_plotlyjs='cdn',
            include_mathjax=False,
            config={
                'displayModeBar': True,
                'responsive': True
            }
        )
        
        # Return file path
        return f"/temp/{filename}"
        
    except Exception as e:
        # Log the error
        print(f"Error generating SVD visualization: {str(e)}")
        raise e 

def perform_svd_analysis(score_type, specific_pgs_ids=None, cohort=None):
    """
    Build a matrix of PGS scores x samples and perform SVD on it.
    
    Parameters:
    - score_type: The SCORE_TYPE to filter on
    - specific_pgs_ids: List of specific PGS IDs to include (if None, use all)
    - cohort: Name of cohort to filter samples (optional)
    
    Returns:
    - U: Left singular vectors (sample space)
    - S: Singular values
    - Vt: Right singular vectors (PGS score space)
    - pgs_ids: List of PGS IDs used (for reference)
    - sample_ids: List of sample IDs used (for reference)
    - stats: Dictionary containing additional statistics
    """
    print(f"=== Performing SVD Analysis ===")
    print(f"Score Type: {score_type}")
    
    # Database connection
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get PGS IDs 
    if specific_pgs_ids:
        placeholders = ','.join(['?'] * len(specific_pgs_ids))
        cursor.execute(f"""
            SELECT DISTINCT PGS_ID 
            FROM scores 
            WHERE SCORE_TYPE = ?
            AND PGS_ID IN ({placeholders})
            ORDER BY PGS_ID
        """, [score_type] + specific_pgs_ids)
    else:
        cursor.execute("""
            SELECT DISTINCT PGS_ID 
            FROM scores 
            WHERE SCORE_TYPE = ?
            ORDER BY PGS_ID
        """, (score_type,))
    
    pgs_ids = [row[0] for row in cursor.fetchall()]
    print(f"Selected {len(pgs_ids)} PGS_IDs.")
            
    # Modified sample ID fetching with population filtering
    print("Getting all SAMPLE_IDs for the selected PGS_IDs...")

    if cohort and cohort != "ALL":
        # Query the ancestry table to get sample IDs for the specified population
        cursor.execute("SELECT sample_ids FROM ancestry_groups WHERE population = ?", (cohort,))
        cohort_result = cursor.fetchone()
        
        if cohort_result:
            # Parse the JSON array of sample IDs
            sample_ids = json.loads(cohort_result[0])
            print(f"Filtering to {len(sample_ids)} samples from {cohort} population")
            

        else:
            print(f"Warning: Population {cohort} not found in database. Using all samples.")
            cursor.execute(f"""
                SELECT DISTINCT SAMPLE_ID 
                FROM scores 
                WHERE SCORE_TYPE = ? 
                AND PGS_ID IN ({','.join(['?']*len(pgs_ids))})
                ORDER BY SAMPLE_ID
            """, [score_type] + pgs_ids)
            sample_ids = [row[0] for row in cursor.fetchall()]
    else:
        # No population filtering
        cursor.execute(f"""
            SELECT DISTINCT SAMPLE_ID 
            FROM scores 
            WHERE SCORE_TYPE = ? 
            AND PGS_ID IN ({','.join(['?']*len(pgs_ids))})
            ORDER BY SAMPLE_ID
        """, [score_type] + pgs_ids)
    
        sample_ids = [row[0] for row in cursor.fetchall()]

    print(f"Found {len(sample_ids)} unique SAMPLE_IDs.")

    start_time = time.time()
    print("Starting data processing...")

    matrix, _ = get_matrix(
        sample_ids=sample_ids,
        pgs_ids=pgs_ids,
        score_type=score_type,
        output_format="numpy",
        handle_missing=True  
    )

    total_time = time.time() - start_time
    print(f"Total processing time: {total_time:.2f} seconds.")
    print(f"Matrix shape: {matrix.shape}")   

    # Center the data (important for SVD/PCA interpretation)
    matrix_centered = matrix - np.mean(matrix, axis=0)
    
    # Perform SVD
    print("Performing SVD...")
    U, S, Vt = np.linalg.svd(matrix_centered, full_matrices=False)
    
    # Calculate explained variance
    explained_variance = (S ** 2) / (matrix_centered.shape[0] - 1)
    total_variance = np.sum(explained_variance)
    explained_variance_ratio = explained_variance / total_variance
    
    # Compile statistics
    stats = {
        "explained_variance_ratio": explained_variance_ratio.tolist(),
        "cumulative_variance": np.cumsum(explained_variance_ratio).tolist(),
        "singular_values": S.tolist(),
        "num_samples": len(sample_ids),
        "num_pgs_ids": len(pgs_ids),
        "score_type": score_type,
        "cohort": cohort if cohort else "ALL"
    }
    
    # Close database connection
    conn.close()
    
    return U, S, Vt, pgs_ids, sample_ids, stats

def generate_svd_scree_plot(S, stats):
    """Generate a scree plot to visualize singular values and explained variance"""
    explained_variance_ratio = stats["explained_variance_ratio"]
    cumulative_variance = stats["cumulative_variance"]
    
    # Create scree plot with two traces
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Bar chart for individual explained variance
    fig.add_trace(
        go.Bar(
            x=list(range(1, len(S)+1)),
            y=explained_variance_ratio,
            name="Explained Variance",
            marker_color="blue"
        ),
        secondary_y=False
    )
    
    # Line chart for cumulative explained variance
    fig.add_trace(
        go.Scatter(
            x=list(range(1, len(S)+1)),
            y=cumulative_variance,
            name="Cumulative Variance",
            mode="lines+markers",
            line=dict(color="red")
        ),
        secondary_y=True
    )
    
    # Update layout
    fig.update_layout(
        title=f'SVD Scree Plot: {stats["score_type"]} Scores',
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
    
    return fig

def generate_svd_biplot_sample(U, S, Vt, pgs_ids, sample_ids, stats, pgs_metadata=None, max_vectors=20):
    """Generate a biplot to visualize samples and features in the same 2D space"""
    # Number of components to use (typically 2 for a 2D plot)
    n_components = 2

    # Scale the singular vectors by the singular values
    U_scaled = U[:, :n_components] * S[:n_components]

    # Create figure
    fig = go.Figure()

    # Add samples as scatter points
    fig.add_trace(
        go.Scatter(
            x=U_scaled[:, 0],
            y=U_scaled[:, 1],
            mode='markers',
            marker=dict(
                size=5,
                color='green',  # Changed from blue to green as per your example
                opacity=0.6
            ),
            name='Samples',
            text=[f"Sample: {sample_id}" for sample_id in sample_ids],
            hoverinfo='text'
        )
    )

    # Calculate scaling factor for feature vectors
    scale_factor = np.percentile(np.abs(U_scaled), 95) / np.percentile(np.abs(Vt[:n_components, :]), 95) * 0.5

    # Find top contributing PGS scores
    if len(pgs_ids) > max_vectors:
        # Calculate contribution of each PGS to the first 2 components
        pgs_contributions = np.sum(Vt[:n_components, :]**2, axis=0)
        # Get indices of top contributors
        top_indices = np.argsort(pgs_contributions)[::-1][:max_vectors]
    else:
        # If fewer PGS than max_vectors, use all of them
        top_indices = range(len(pgs_ids))

    # Create hover text for PGS vectors
    hover_texts = []
    for idx in top_indices:
        pgs_id = pgs_ids[idx]
        
        # Get metadata if available
        if pgs_metadata and pgs_id in pgs_metadata:
            meta = pgs_metadata[pgs_id]
            hover_text = (
                f"PGS ID: {pgs_id}<br>"
                f"Name: {meta.get('PGS_Name', 'N/A')}<br>"
                f"Trait: {meta.get('Reported_Trait', 'N/A')}<br>"
                f"Publication: {meta.get('Publication_ID', 'N/A')}"
            )
        else:
            hover_text = f"PGS ID: {pgs_id}"
        
        hover_texts.append(['', hover_text])  # Empty string for the origin point, hover text for the arrow endpoint

    # Add PGS features as vectors (only top contributors)
    for i, idx in enumerate(top_indices):
        fig.add_trace(
            go.Scatter(
                x=[0, Vt[0, idx] * scale_factor],
                y=[0, Vt[1, idx] * scale_factor],
                mode='lines+text',
                line=dict(color='red', width=1),
                text=['', pgs_ids[idx]],
                textposition='top center',
                name=pgs_ids[idx],
                hovertext=hover_texts[i],
                hoverinfo='text'
            )
        )

    # Update layout
    fig.update_layout(
        title=f'SVD Biplot: {stats["score_type"]} Scores (Sample-centered view)',
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

    # Add a dashed circle to indicate scale
    theta = np.linspace(0, 2*np.pi, 100)
    radius = np.percentile(np.sqrt(np.sum(U_scaled**2, axis=1)), 75)
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

    return fig

def generate_svd_biplot_score(U, S, Vt, pgs_ids, sample_ids, stats, pgs_metadata=None, data_dict=None, max_vectors=20):
    """Generate a biplot to visualize PGS scores and samples in the same 2D space"""
    # Number of components to use (typically 2 for a 2D plot)
    n_components = 2
    
    # Scale the singular vectors by the singular values
    Vt_scaled = Vt[:n_components, :].T * S[:n_components]
    
    # Create figure
    fig = go.Figure()
    
    # Create hover text for PGS points
    hover_text = []
    for i, pgs_id in enumerate(pgs_ids):
        # Get metadata for this PGS ID
        if pgs_metadata and pgs_id in pgs_metadata:
            meta = pgs_metadata[pgs_id]
            
            # Calculate average score if data_dict is available
            avg_score_text = ""
            if data_dict:
                scores = [data_dict[sample_id].get(pgs_id, np.nan) for sample_id in sample_ids]
                avg_score = np.nanmean([s for s in scores if not np.isnan(s)])
                avg_score_text = f"<br>Avg Score: {avg_score:.4f}"
            
            hover_info = (
                f"PGS ID: {pgs_id}<br>"
                f"Name: {meta.get('PGS_Name', 'N/A')}<br>"
                f"Trait: {meta.get('Reported_Trait', 'N/A')}<br>"
                f"Publication: {meta.get('Publication_ID', 'N/A')}"
                f"{avg_score_text}"
            )
        else:
            hover_info = f"PGS ID: {pgs_id}"
            
        hover_text.append(hover_info)
    
    # Add PGS scores as scatter points
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
            text=pgs_ids,
            textposition="top center",
            hovertext=hover_text,
            hoverinfo='text'
        )
    )
    
    # Calculate scaling factor for sample vectors
    scale_factor = np.percentile(np.abs(Vt_scaled), 95) / np.percentile(np.abs(U[:, :n_components]), 95) * 0.5
    
    # Find top contributing samples
    if len(sample_ids) > max_vectors:
        # Calculate contribution of each sample to the first 2 components
        sample_contributions = np.sum(U[:, :n_components]**2, axis=1)
        # Get indices of top contributors
        top_indices = np.argsort(sample_contributions)[::-1][:max_vectors]
    else:
        # If fewer samples than max_vectors, use all of them
        top_indices = range(len(sample_ids))
    
    # Add samples as vectors (only top contributors)
    for idx in top_indices:
        fig.add_trace(
            go.Scatter(
                x=[0, U[idx, 0] * scale_factor],
                y=[0, U[idx, 1] * scale_factor],
                mode='lines',  # Removed text to make the plot cleaner
                line=dict(color='blue', width=1),
                name=sample_ids[idx],
                hoverinfo='name'
            )
        )
    
    # Update layout
    fig.update_layout(
        title=f'SVD Biplot: {stats["score_type"]} Scores (Score-centered view)',
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
    
    # Add a dashed circle to indicate scale
    theta = np.linspace(0, 2*np.pi, 100)
    radius = np.percentile(np.sqrt(np.sum(Vt_scaled**2, axis=1)), 75)
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
    
    return fig

def generate_svd_component_weights(Vt, pgs_ids, stats):
    """Generate a visualization of component weights (loadings) for top components"""
    # Number of components to visualize
    n_components = min(5, Vt.shape[0])
    
    # Number of top PGS IDs to show per component
    n_top_pgs = min(20, len(pgs_ids))
    
    # Create subplots, one for each component
    fig = make_subplots(
        rows=n_components, 
        cols=1,
        subplot_titles=[f'Component {i+1} ({stats["explained_variance_ratio"][i]*100:.1f}%)' 
                        for i in range(n_components)]
    )
    
    # For each component, show the top contributing PGS scores
    for i in range(n_components):
        # Sort PGS IDs by absolute contribution to this component
        sorted_indices = np.argsort(np.abs(Vt[i, :]))[::-1][:n_top_pgs]
        
        # Get the weights and corresponding PGS IDs
        weights = Vt[i, sorted_indices]
        component_pgs_ids = [pgs_ids[idx] for idx in sorted_indices]
        
        # Add bar chart for this component
        fig.add_trace(
            go.Bar(
                x=component_pgs_ids,
                y=weights,
                marker_color=['red' if w < 0 else 'green' for w in weights],
                name=f'Component {i+1}'
            ),
            row=i+1, 
            col=1
        )
    
    # Update layout
    fig.update_layout(
        title=f'SVD Component Weights: {stats["score_type"]} Scores',
        height=300 * n_components,
        width=1000,
        showlegend=False
    )
    
    # Update axes
    for i in range(n_components):
        fig.update_xaxes(title_text="PGS ID", row=i+1, col=1)
        fig.update_yaxes(title_text="Loading Weight", row=i+1, col=1)
    
    return fig

def generate_svd_heatmap(Vt, pgs_ids, stats):
    """Generate a heatmap of component loadings"""
    # Number of components to visualize
    n_components = min(10, Vt.shape[0])
    
    # Number of top PGS IDs to show
    n_top_pgs = min(50, len(pgs_ids))
    
    # Get the top contributing PGS IDs across all components
    overall_importance = np.sum(Vt[:n_components, :]**2, axis=0)
    top_indices = np.argsort(overall_importance)[::-1][:n_top_pgs]
    
    # Extract the submatrix for visualization
    heatmap_data = Vt[:n_components, top_indices]
    
    # Get corresponding PGS IDs
    heatmap_pgs_ids = [pgs_ids[idx] for idx in top_indices]
    
    # Create heatmap
    fig = go.Figure(data=go.Heatmap(
        z=heatmap_data,
        x=heatmap_pgs_ids,
        y=[f'Component {i+1} ({stats["explained_variance_ratio"][i]*100:.1f}%)' for i in range(n_components)],
        colorscale='RdBu',
        zmid=0,
        text=[[f'PGS: {pgs_id}<br>Component: {i+1}<br>Weight: {weight:.3f}' 
              for pgs_id, weight in zip(heatmap_pgs_ids, row)] 
              for i, row in enumerate(heatmap_data)],
        hoverinfo='text'
    ))
    
    # Update layout
    fig.update_layout(
        title=f'SVD Component Loading Heatmap: {stats["score_type"]} Scores',
        xaxis=dict(
            title='PGS ID',
            tickangle=45
        ),
        yaxis=dict(
            title='Component',
            autorange='reversed'
        ),
        height=600,
        width=1200
    )
    
    return fig

def generate_svd_combined(U, S, Vt, pgs_ids, sample_ids, stats):
    """Generate a combined visualization with multiple SVD plots"""
    # Create a figure with subplots
    fig = make_subplots(
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
    
    # 1. Scree plot
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
    
    # 2. Biplot
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
    
    # Add a few key PGS features as vectors
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
    
    # 3. Top PGS contributions to PC1
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
    
    # 4. Heatmap of top components
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
    
    # Update layout
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
    
    return fig

def generate_svd_hash(score_type, pgs_ids, cohort, plot_type, perspective, max_vectors):
    """Generate a hash for the SVD request parameters for caching"""
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
