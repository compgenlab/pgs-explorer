import os
import json
import hashlib
import sqlite3
import numpy as np
from datetime import datetime
import plotly.graph_objects as go
from sklearn.manifold import TSNE
# from apps.core.database import DB_PATH
# from apps.database.service import fetch_pgs_metadata
from apps.multivariate.service import get_matrix

def process_tsne(request_data):
    try:
        # Create temp directory if it doesn't exist
        os.makedirs("temp", exist_ok=True)

        # Extract parameters from request_data
        score_type = request_data["score_type"]
        pgs_ids = request_data.get("pgs_ids")
        cohort = request_data.get("cohort")
        perspective = request_data.get("perspective", "sample")
        perplexity = request_data["perplexity"]
        iterations = request_data["iterations"]
        learning_rate = request_data["learning_rate"]

        # Generate hash for caching
        request_hash = generate_tsne_hash(
            score_type,
            pgs_ids,
            cohort,
            perspective,
            perplexity,
            iterations,
            learning_rate
        )

        # Check for existing cached file
        for filename in os.listdir("temp"):
            if filename.endswith(".html") and request_hash in filename and "tsne" in filename:
                cached_filepath = os.path.join("temp", filename)
                os.utime(cached_filepath)
                print(f"Using cached t-SNE visualization: {filename}")
                return f"/temp/{filename}"

        # Perform t-SNE analysis
        tsne_result, pgs_ids, sample_ids = perform_tsne_analysis(
            score_type=score_type,
            specific_pgs_ids=pgs_ids,
            cohort=cohort,
            perspective=perspective,
            perplexity=perplexity,
            n_iter=iterations,
            learning_rate=learning_rate
        )

        # Generate filename with hash
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        score_type_safe = score_type.replace("/", "_").replace("\\", "_")
        cohort_indicator = f"{cohort}_" if cohort and cohort != "ALL" else ""
        filename = f"tsne_{cohort_indicator}{score_type_safe}_{request_hash}_{timestamp}.html"
        filepath = os.path.join("temp", filename)

        # Generate the appropriate visualization
        if perspective == "score":
            fig = generate_tsne_score(tsne_result, pgs_ids=pgs_ids)
        else:
            fig = generate_tsne_sample(tsne_result, sample_ids=sample_ids)

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

        return f"/temp/{filename}"

    except Exception as e:
        print(f"Error generating t-SNE visualization: {str(e)}")
        raise e

def perform_tsne_analysis(score_type, specific_pgs_ids, cohort, perspective, perplexity, n_iter, learning_rate):
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
        pgs_ids = None
        print("all pgs")

    pgs_ids = [row[0] for row in cursor.fetchall()]
    print(f"Selected {len(pgs_ids)} PGS_IDs.")

    # --- Get sample IDs ---
    if cohort and cohort != "ALL":
        cursor.execute("SELECT sample_ids FROM ancestry_groups WHERE population = ?", (cohort,))
        cohort_result = cursor.fetchone()
        sample_ids = json.loads(cohort_result[0])
        print(f"Filtering to {len(sample_ids)} samples from {cohort} population")
    else:
        sample_ids = None
        print("all samples")

    # --- Matrix build ---
    matrix, pgs_ids = get_matrix(
        sample_ids=sample_ids,
        pgs_ids=pgs_ids,
        score_type=score_type,
        output_format="numpy",
        handle_missing=True
    )

    # --- Run t-SNE ---
    tsne = TSNE(
        n_components=2,
        perplexity=perplexity,
        n_iter=n_iter,  # Use n_iter as passed from the calling function
        learning_rate=learning_rate,
        random_state=42
    )
    
    # Transform matrix based on perspective
    if perspective == "score" and matrix.shape[0] > matrix.shape[1]:
        # Transpose matrix for score-centered analysis (if samples > scores)
        matrix = matrix.T
        tsne_result = tsne.fit_transform(matrix)
        return tsne_result, pgs_ids, sample_ids
    else:
        # For sample-centered or already transposed matrices
        tsne_result = tsne.fit_transform(matrix)
        return tsne_result, pgs_ids, sample_ids

def generate_tsne_sample(tsne_result, sample_ids):
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=tsne_result[:, 0],
            y=tsne_result[:, 1],
            mode="markers",
            marker=dict(size=6, color="blue", opacity=0.7),
            text=sample_ids,
            hoverinfo="text",
            name="Samples"
        )
    )
    fig.update_layout(
        title="t-SNE Projection (Samples as Points)",
        xaxis_title="t-SNE 1",
        yaxis_title="t-SNE 2",
        showlegend=False
    )
    return fig

def generate_tsne_score(tsne_result, pgs_ids):
    pgs_metadata = fetch_pgs_metadata(pgs_ids)
    hover_text = []
    for pgs_id in pgs_ids:
        meta = pgs_metadata.get(pgs_id, {})
        if not meta:
            print(f"Missing metadata for {pgs_id}")
        hover_text.append(
            f"PGS ID: {pgs_id}<br>"
            f"Name: {meta.get('PGS_Name', 'N/A')}<br>"
            f"Trait: {meta.get('Reported_Trait', 'N/A')}<br>"
            f"Publication: {meta.get('Publication_ID', 'N/A')}"
        )

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=tsne_result[:, 0],
            y=tsne_result[:, 1],
            mode="markers",
            marker=dict(size=6, color="red", opacity=0.7),
            text=hover_text,
            hoverinfo="text",
            name="PGS Scores"
        )
    )
    fig.update_layout(
        title="t-SNE Projection (PGS Scores as Points)",
        xaxis_title="t-SNE 1",
        yaxis_title="t-SNE 2",
        showlegend=False
    )
    return fig

def generate_tsne_hash(score_type, pgs_ids, cohort, perspective, perplexity, iterations, learning_rate):
    hash_input = json.dumps({
        "score_type": score_type,
        "pgs_ids": pgs_ids,
        "cohort": cohort,
        "perspective": perspective,
        "perplexity": perplexity,
        "iterations": iterations,
        "learning_rate": learning_rate
    }, sort_keys=True)
    print(hash_input)
    print(hashlib.md5(hash_input.encode()).hexdigest())
    return hashlib.md5(hash_input.encode()).hexdigest()
