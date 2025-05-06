import os
import json
import hashlib
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
from apps.database.service import fetch_pgs_metadata

def process_pca(request_data):
    try:
        # Create temp directory if it doesn't exist
        os.makedirs("temp", exist_ok=True)
        
        # Extract parameters from request_data
        score_type = request_data["score_type"]
        pgs_ids = request_data["pgs_ids"]
        cohort = request_data["cohort"]
        perspective = request_data.get("perspective", "sample")  # Default to sample
        x_axis = request_data.get("x_axis", "1") # Default to PC1
        y_axis = request_data.get("y_axis", "2") # Default to PC2
        include_variance = request_data.get("include_variance", True)

        # Generate hash for caching
        request_hash = generate_pca_hash(
            score_type,
            pgs_ids,
            cohort,
            perspective,
            x_axis,
            y_axis,
            include_variance
        )
        
        # Check if we already have a file with this hash
        for filename in os.listdir("temp"):
            if filename.endswith(".html") and request_hash in filename and "pca" in filename:
                # Found a cached file, update its access time
                cached_filepath = os.path.join("temp", filename)
                os.utime(cached_filepath)
                
                print(f"Using cached PCA visualization: {filename}")
                
                # Return file path
                return f"/temp/{filename}"
        
        # First, perform SVD analysis to get the matrices
        U, S, Vt, pgs_ids, sample_ids, stats = perform_pca_analysis(
            score_type=score_type,
            specific_pgs_ids=pgs_ids,
            cohort=cohort
        )
        
        # Generate filename with hash
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        score_type_safe = score_type.replace("/", "_").replace("\\", "_")
        cohort_indicator = f"{cohort}_" if cohort and cohort != "ALL" else ""
        filename = f"pca_{cohort_indicator}{score_type_safe}_{request_hash}_{timestamp}.html"
        filepath = os.path.join("temp", filename)
        
        # Route to the appropriate visualization function
        if perspective == "score":
            fig = generate_pca_score(U=U, S=S, Vt=Vt, 
                pgs_ids=pgs_ids, 
                sample_ids=sample_ids, 
                stats=stats, 
                x_axis=x_axis, 
                y_axis=y_axis, 
                include_variance=include_variance
            )
        else:  
            fig = generate_pca_sample(U=U, S=S, Vt=Vt, 
                pgs_ids=pgs_ids, 
                sample_ids=sample_ids, 
                stats=stats, 
                x_axis=x_axis, 
                y_axis=y_axis, 
                include_variance=include_variance
            )
        
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
        print(f"Error generating PCA visualization: {str(e)}")
        raise e 

def generate_pca_sample(U, S, Vt, pgs_ids, sample_ids, stats, pgs_metadata=None, x_axis="1", y_axis="2", include_variance=True):
    """Generate a biplot to visualize samples and features in the same 2D space."""
    
    # Convert axis inputs to integers (0-based)
    x_idx = int(x_axis) - 1
    y_idx = int(y_axis) - 1

    # Scale the singular vectors by the singular values
    U_scaled = U[:, [x_idx, y_idx]] * S[[x_idx, y_idx]]

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
                color='green',
                opacity=0.6
            ),
            name='Samples',
            text=[f"Sample: {sample_id}" for sample_id in sample_ids],
            hoverinfo='text'
        )
    )

    # Get variance labels
    if include_variance and "explained_variance_ratio" in stats:
        x_var = stats["explained_variance_ratio"][x_idx] * 100
        y_var = stats["explained_variance_ratio"][y_idx] * 100
        x_title = f'Component {x_axis} ({x_var:.1f}%)'
        y_title = f'Component {y_axis} ({y_var:.1f}%)'
    else:
        x_title = f'Component {x_axis}'
        y_title = f'Component {y_axis}'

    # Update layout
    fig.update_layout(
        title=f'PCA: {stats.get("score_type", "Unknown")} Scores (Sample-centered view)',
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

    # Add a dashed circle to indicate scale
    theta = np.linspace(0, 2 * np.pi, 100)
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

def generate_pca_score(U, S, Vt, pgs_ids, sample_ids, stats, x_axis="1", y_axis="2", include_variance=True):
    """Generate a biplot to visualize PGS scores and samples in the same 2D space."""
    
    # Convert axis inputs to 0-based indices
    x_idx = int(x_axis) - 1
    y_idx = int(y_axis) - 1

    # Scale the right singular vectors (Vt.T) by the singular values
    Vt_scaled = Vt[[x_idx, y_idx], :].T * S[[x_idx, y_idx]]

    # Create figure
    fig = go.Figure()

    # Create hover text for PGS points
    hover_text = []
    pgs_metadata = fetch_pgs_metadata(pgs_ids)
    for i, pgs_id in enumerate(pgs_ids):
        # Get metadata for this PGS ID
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
            hovertext=hover_text,
            hoverinfo='text'
        )
    )

    # Get variance labels
    if include_variance and "explained_variance_ratio" in stats:
        x_var = stats["explained_variance_ratio"][x_idx] * 100
        y_var = stats["explained_variance_ratio"][y_idx] * 100
        x_title = f'Component {x_axis} ({x_var:.1f}%)'
        y_title = f'Component {y_axis} ({y_var:.1f}%)'
    else:
        x_title = f'Component {x_axis}'
        y_title = f'Component {y_axis}'

    # Update layout
    fig.update_layout(
        title=f'PCA Plot: {stats.get("score_type", "Unknown")} Scores (Score-centered view)',
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

    # Add a dashed circle to indicate scale
    theta = np.linspace(0, 2 * np.pi, 100)
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

def perform_pca_analysis(score_type, specific_pgs_ids=None, cohort=None):
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

def generate_pca_hash(score_type, pgs_ids, cohort, perspective, x_axis, y_axis, include_variance):
    """Generate a hash for the SVD request parameters for caching"""
    params = {
        "score_type": score_type,
        "pgs_ids": sorted(pgs_ids) if pgs_ids else "all",
        "cohort": cohort if cohort else "ALL",
        "perspective": perspective,
        "x_axis": x_axis,
        "y_axis": y_axis,
        "include_variance": include_variance
    }
    param_str = json.dumps(params, sort_keys=True)
    hash_obj = hashlib.md5(param_str.encode())
    return hash_obj.hexdigest()
