import os
import json
import hashlib
import sqlite3
import numpy as np
from typing import List
from scipy import stats
import plotly.graph_objects as go
from apps.core.database import DB_PATH

def process_distribution(request_data):
    """
    Generate distribution plots on the backend, cache them, and return the plot path.
    The function calculates a hash of the request to check if it's already been processed.
    """
    try:
        # Create a hash of the request to use as the filename
        request_hash = hashlib.md5(json.dumps(request_data, sort_keys=True).encode()).hexdigest()
        os.makedirs("temp", exist_ok=True)

        html_path = f"temp/{request_hash}.html"
        json_path = f"temp/{request_hash}.json"
        
        # Check if this exact plot has been generated recently
        if os.path.exists(html_path) and os.path.exists(json_path):
            # Return the cached file path
            return f"/{html_path}"
        
        # Connect to the database
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            # Handle cohort analysis
            if request_data["analysis_type"] == 'cohort':
                pgs_id = request_data.get("pgs_id", "")
                score_type = request_data.get("score_type", "")
                cohorts = request_data.get("cohorts", [])
                chart_type = request_data.get("chart_type", "")
                plot_title = request_data.get("plot_title", "")
                
                if not pgs_id or not score_type or not cohorts:
                    raise ValueError("Missing required fields for cohort analysis")
                
                # Retrieve scores for the given PGS and score type
                cursor.execute(
                    "SELECT SAMPLE_ID, SCORE FROM scores WHERE PGS_ID = ? AND SCORE_TYPE = ?",
                    (pgs_id, score_type)
                )
                rows = cursor.fetchall()
                
                if not rows:
                    raise ValueError(f"No data found for PGS '{pgs_id}' and Score Type '{score_type}'")
                
                # Create a dictionary mapping SAMPLE_ID to SCORE
                score_dict = {row["SAMPLE_ID"]: row["SCORE"] for row in rows}
                
                cohort_data = []
                for cohort in cohorts:
                    print(cohort.keys())
                    if cohort["name"] != "ALL":
                        # Filter to include only samples that exist in our data
                        valid_samples = [
                            {"SAMPLE_ID": sample_id, "SCORE": score_dict[sample_id]}
                            for sample_id in cohort["sample_ids"]
                            if sample_id in score_dict
                        ]
                        
                        cohort_scores = [sample["SCORE"] for sample in valid_samples]
                        
                        cohort_data.append({
                            "color": cohort["color"],
                            "values": cohort_scores,
                            "samples": valid_samples,
                            "name": cohort["name"]
                        })
                    else:
                        # Filter to include only samples that exist in our data
                        valid_samples = [
                            {"SAMPLE_ID": sample_id, "SCORE": score_dict[sample_id]}
                            for sample_id in score_dict
                            ]
                        
                        print(f"For ALL: {len(valid_samples)} samples.")
                        cohort_scores = [sample["SCORE"] for sample in valid_samples]
                        
                        cohort_data.append({
                            "color": cohort["color"],
                            "values": cohort_scores,
                            "samples": valid_samples,
                            "name": cohort["name"]
                        })

                # Create Plotly figure based on chart_type
                fig = go.Figure()
                
                if chart_type == 'density':
                    # Create a common x-axis range for all distributions
                    all_values = []
                    for cohort in cohort_data:
                        if cohort["values"]:
                            all_values.extend(cohort["values"])
                    
                    if not all_values:
                        raise ValueError("No valid data to plot")
                    
                    # Determine appropriate range for x-axis with padding
                    min_val = min(all_values)
                    max_val = max(all_values)
                    range_padding = (max_val - min_val) * 0.1
                    x_min = min_val - range_padding
                    x_max = max_val + range_padding
                    
                    # Create evenly spaced x values for the density curves
                    x = np.linspace(x_min, x_max, 100)
                    
                    for cohort in cohort_data:
                        if cohort["values"] and len(cohort["values"]) > 1:
                            # Use kernel density estimation to create smooth curve
                            try:
                                kde = stats.gaussian_kde(cohort["values"])
                                y = kde(x)
                                
                                # Create density curve
                                fig.add_trace(go.Scatter(
                                    x=x,
                                    y=y,
                                    mode='lines',
                                    name=f"{cohort['name']} (n={len(cohort['values'])})",
                                    line=dict(color=cohort["color"], width=2),
                                    fill=None  # No fill, just the line
                                ))
                                
                            except Exception as e:
                                print(f"Error creating density plot for {cohort['name']}: {str(e)}")
                                continue
                    
                    # Update layout
                    fig.update_layout(
                        title=plot_title,
                        xaxis_title="Score",
                        yaxis_title="Density",
                        hovermode="closest",
                        showlegend=True,
                        legend=dict(
                            x=1.02,
                            y=0.98,
                            xanchor="left",
                            yanchor="top"
                        ),
                        margin=dict(l=60, r=150, t=50, b=50)
                    )

                elif chart_type == 'histogram':
                    # Get all values to determine common axis
                    all_values = []
                    for cohort in cohort_data:
                        if cohort["values"]:
                            all_values.extend(cohort["values"])
                    
                    if not all_values:
                        raise ValueError("No valid data to plot")
                    
                    # Determine appropriate range with padding
                    min_val = min(all_values)
                    max_val = max(all_values)
                    range_padding = (max_val - min_val) * 0.1
                    x_min = min_val - range_padding
                    x_max = max_val + range_padding
                    
                    # Calculate optimal number of bins based on data
                    num_bins = min(30, int(np.ceil(np.sqrt(len(all_values)))))
                    
                    # Create histogram bins
                    bin_size = (x_max - x_min) / num_bins
                    
                    # Add histograms for each cohort
                    for i, cohort in enumerate(cohort_data):
                        if cohort["values"]:
                            fig.add_trace(go.Histogram(
                                x=cohort["values"],
                                name=f"{cohort['name']} (n={len(cohort['values'])})",
                                marker_color=cohort["color"],
                                opacity=0.7,
                                xbins=dict(
                                    start=x_min,
                                    end=x_max,
                                    size=bin_size
                                ),
                                # Offset bins for each cohort to avoid complete overlap
                                offsetgroup=i
                            ))
                    
                    # Update layout
                    fig.update_layout(
                        title=plot_title,
                        xaxis_title="Score",
                        yaxis_title="Frequency",
                        barmode='group',  # Group bars for different cohorts
                        hovermode="closest",
                        showlegend=True,
                        legend=dict(
                            x=1.02,
                            y=0.98,
                            xanchor="left",
                            yanchor="top"
                        ),
                        margin=dict(l=60, r=150, t=50, b=50)
                    )
                elif chart_type == 'box':
                    # Add boxplots for each cohort
                    for cohort in cohort_data:
                        if cohort["values"] and len(cohort["values"]) > 0:
                            # Calculate boxplot stats
                            values = sorted(cohort["values"])
                            
                            fig.add_trace(go.Box(
                                y=values,
                                name=f"{cohort['name']} (n={len(cohort['values'])})",
                                boxmean=True,  # Show mean as a dashed line
                                marker_color=cohort["color"],
                                line=dict(color='black'),
                                fillcolor=cohort["color"],
                                opacity=0.7
                            ))
                    
                    # Update layout
                    fig.update_layout(
                        title=plot_title,
                        yaxis_title="Score",
                        xaxis_title="Cohort",
                        hovermode="closest",
                        showlegend=False,
                        margin=dict(l=60, r=150, t=50, b=50)
                    )
                
                # Common layout settings for all chart types
                fig.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0.05)',
                    height=600,
                    width=900
                )
                
                # Save the plot as an HTML file
                fig.write_html(html_path)
                
                # Save the data matrix
                data_matrix = {"cohorts": cohort_data}
                with open(json_path, 'w') as f:
                    json.dump(data_matrix, f)
                
                # Return the file path
                return f"/{html_path}"
                    
            # Handle score comparison
            elif request_data["analysis_type"] == 'score':
                score_type = request_data.get("score_type", "")
                pgs_comparison = request_data.get("pgs_comparison", {})
                chart_type = request_data.get("chart_type", "")
                plot_title = request_data.get("plot_title", "")
                sample_ids = pgs_comparison.get("sample_ids", [])
                
                if not pgs_comparison or not score_type:
                    raise ValueError("Missing required fields for score comparison")
                
                # For each PGS ID, retrieve the scores for the sample IDs
                pgs_data = []
                for i, pgs_id in enumerate(pgs_comparison.get("pgs_ids", [])):
                    # Retrieve scores for this PGS and the score type
                    cursor.execute(
                        "SELECT SAMPLE_ID, SCORE FROM scores WHERE PGS_ID = ? AND SCORE_TYPE = ?",
                        (pgs_id, score_type)
                    )
                    rows = cursor.fetchall()
                    
                    if not rows:
                        continue  # Skip if no data found for this PGS
                    
                    # Create a dictionary mapping SAMPLE_ID to SCORE
                    score_dict = {row["SAMPLE_ID"]: row["SCORE"] for row in rows}
                    
                    if sample_ids:
                        # Filter to include only samples that exist in our data
                        valid_samples = [
                            {"SAMPLE_ID": sample_id, "SCORE": score_dict[sample_id]}
                            for sample_id in pgs_comparison.get("sample_ids", [])
                            if sample_id in score_dict
                        ]
                    else: 
                        valid_samples = [
                            {"SAMPLE_ID": sample_id, "SCORE": score_dict[sample_id]}
                            for sample_id in score_dict
                            ]
                        
                    scores = [sample["SCORE"] for sample in valid_samples]
                    
                    pgs_data.append({
                        "color": pgs_comparison.get("colors", [])[i] if i < len(pgs_comparison.get("colors", [])) else "#000000",
                        "values": scores,
                        "samples": valid_samples,
                        "name": pgs_comparison.get("names", [])[i] if i < len(pgs_comparison.get("names", [])) else pgs_id
                    })
                
                # Create Plotly figure based on chart_type
                fig = go.Figure()
                
                # Similar plotting logic as for cohorts, but with PGS data
                if chart_type == 'density':
                    # Create a common x-axis range for all distributions
                    all_values = []
                    for pgs in pgs_data:
                        if pgs["values"]:
                            all_values.extend(pgs["values"])
                    
                    if not all_values:
                        raise ValueError("No valid data to plot")
                    
                    # Determine appropriate range for x-axis
                    min_val = min(all_values)
                    max_val = max(all_values)
                    range_padding = (max_val - min_val) * 0.1
                    x_min = min_val - range_padding
                    x_max = max_val + range_padding
                    
                    # Create evenly spaced x values for the density curves
                    x = np.linspace(x_min, x_max, 100)
                    
                    for pgs in pgs_data:
                        if pgs["values"] and len(pgs["values"]) > 1:
                            try:
                                # Use kernel density estimation to create smooth curve
                                kde = stats.gaussian_kde(pgs["values"])
                                y = kde(x)
                                
                                # Create density curve
                                fig.add_trace(go.Scatter(
                                    x=x,
                                    y=y,
                                    mode='lines',
                                    name=pgs["name"],
                                    line=dict(color=pgs["color"], width=2),
                                    fill=None  # No fill, just the line
                                ))
                            except Exception as e:
                                print(f"Error creating density plot for {pgs['name']}: {str(e)}")
                                continue
                    
                    fig.update_layout(
                        title=plot_title,
                        xaxis_title="Score",
                        yaxis_title="Density",
                        hovermode="closest",
                        showlegend=True,
                        legend=dict(
                            x=1.02,
                            y=0.98,
                            xanchor="left",
                            yanchor="top"
                        ),
                        margin=dict(l=60, r=150, t=50, b=50)
                    )

                elif chart_type == 'histogram':
                    # Get all values to determine common axis
                    all_values = []
                    for pgs in pgs_data:
                        if pgs["values"]:
                            all_values.extend(pgs["values"])
                    
                    if not all_values:
                        raise ValueError("No valid data to plot")
                    
                    # Determine appropriate range with padding
                    min_val = min(all_values)
                    max_val = max(all_values)
                    range_padding = (max_val - min_val) * 0.1
                    x_min = min_val - range_padding
                    x_max = max_val + range_padding
                    
                    # Calculate optimal number of bins based on data
                    num_bins = min(30, int(np.ceil(np.sqrt(len(all_values)))))
                    
                    # Create histogram bins
                    bin_size = (x_max - x_min) / num_bins
                    
                    # Add histograms for each PGS
                    for i, pgs in enumerate(pgs_data):
                        if pgs["values"]:
                            fig.add_trace(go.Histogram(
                                x=pgs["values"],
                                name=pgs["name"],
                                marker_color=pgs["color"],
                                opacity=0.7,
                                xbins=dict(
                                    start=x_min,
                                    end=x_max,
                                    size=bin_size
                                ),
                                # Offset bins for each PGS to avoid complete overlap
                                offsetgroup=i
                            ))
                    
                    # Update layout
                    fig.update_layout(
                        title=plot_title,
                        xaxis_title="Score",
                        yaxis_title="Frequency",
                        barmode='group',  # Group bars for different PGS
                        hovermode="closest",
                        showlegend=True,
                        legend=dict(
                            x=1.02,
                            y=0.98,
                            xanchor="left",
                            yanchor="top"
                        ),
                        margin=dict(l=60, r=150, t=50, b=50)
                    )

                elif chart_type == 'box':
                    # Add boxplots for each PGS
                    for pgs in pgs_data:
                        if pgs["values"] and len(pgs["values"]) > 0:
                            # Calculate boxplot stats to match D3 implementation
                            values = sorted(pgs["values"])
                            
                            fig.add_trace(go.Box(
                                y=values,
                                name=pgs["name"],
                                boxmean=True,  # Show mean as a dashed line
                                marker_color=pgs["color"],
                                line=dict(color='black'),
                                fillcolor=pgs["color"],
                                opacity=0.7
                            ))
                    
                    # Update layout
                    fig.update_layout(
                        title=plot_title,
                        yaxis_title="Score",
                        xaxis_title="PGS",
                        hovermode="closest",
                        showlegend=False,  # Legend is less important for boxplots since labels are on x-axis
                        margin=dict(l=60, r=150, t=50, b=50)
                    )
                
                # Common layout settings for all chart types
                fig.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0.05)',
                    height=600,
                    width=900
                )
                
                # Save the plot as an HTML file
                fig.write_html(html_path)
                
                # Save the data matrix
                data_matrix = {"pgs_data": pgs_data}
                with open(json_path, 'w') as f:
                    json.dump(data_matrix, f)
                
                # Return the file path
                return f"/{html_path}"
            
            else:
                raise ValueError(f"Invalid analysis type: {request_data['analysis_type']}")
        
        finally:
            conn.close()
            
    except Exception as e:
        # Log error and re-raise to be caught by background task processor
        print(f"Error in process_distribution: {str(e)}")
        raise e      

def calculate_percentile(value: float, array: List[float]) -> float:
    """Calculate the percentile of a value in an array."""
    sorted_array = sorted(array)
    position = next((i for i, x in enumerate(sorted_array) if x >= value), len(sorted_array))
    
    if position == len(sorted_array):
        return 100.0  # Value is greater than all elements
    
    return (position / len(sorted_array) * 100)
