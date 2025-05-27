import os
import json
import hashlib
import numpy as np
from typing import List, Dict, Any
from scipy import stats
import plotly.graph_objects as go
from apps.core.utils import generate_request_hash

# Import repositories
from database import get_score_repository, get_ancestry_repository
score_repository = get_score_repository()
ancestry_repository = get_ancestry_repository()

def process_distribution(request_data: Dict[str, Any]) -> str:
    """
    Generate distribution plots on the backend, cache them, and return the plot path.
    The function calculates a hash of the request to check if it's already been processed.
    
    Parameters:
    -----------
    request_data : dict
        Dictionary containing all parameters required for visualization
    
    Returns:
    --------
    str
        Path to the generated HTML visualization
    """
    try:
        existing, html_path, json_path = generate_request_hash(request_data)
        if existing:
            return f"/{html_path}"   
        
        # Handle cohort analysis
        if request_data["analysis_type"] == 'cohort':
            generate_cohort_visualization(request_data, html_path, json_path)
                
        # Handle score comparison
        elif request_data["analysis_type"] == 'score':
            generate_score_visualization(request_data, html_path, json_path)
        
        else:
            raise ValueError(f"Invalid analysis type: {request_data['analysis_type']}")
        
        return f"/{html_path}"
            
    except Exception as e:
        # Log error and re-raise to be caught by background task processor
        print(f"Error in process_distribution: {str(e)}")
        raise e

def generate_score_visualization(request_data: Dict[str, Any], html_path: str, json_path: str) -> str:
    """
    Generate visualization comparing different PGS scores.
    
    Parameters:
    -----------
    request_data : dict
        Dictionary containing parameters for score comparison
    html_path : str
        Path to save the HTML visualization
    json_path : str
        Path to save the JSON data
    
    Returns:
    --------
    str
        Path to the generated HTML visualization
    """
    # Extract parameters
    score_type = request_data.get("score_type", "")
    pgs_comparison = request_data.get("pgs_comparison", {})
    chart_type = request_data.get("chart_type", "")
    plot_title = request_data.get("plot_title", "")
    
    if not pgs_comparison or not score_type:
        raise ValueError("Missing required fields for score comparison")
    
    # Get PGS IDs and other data from the comparison object
    pgs_ids = pgs_comparison.get("pgs_ids", [])
    sample_ids = pgs_comparison.get("sample_ids", [])
    colors = pgs_comparison.get("colors", [])
    display_names = pgs_comparison.get("names", [])
    
    # Get PGS data
    pgs_data = get_pgs_scores_for_comparison(score_type, pgs_ids, sample_ids)
    
    # Add display names and colors to the data
    for i, pgs in enumerate(pgs_data):
        pgs["color"] = colors[i] if i < len(colors) else "#000000"
        pgs["name"] = display_names[i] if i < len(display_names) else pgs["name"]
    
    # Create visualization based on chart type
    fig = None
    if chart_type == 'density':
        fig = generate_pgs_density_plot(pgs_data, plot_title)
    elif chart_type == 'histogram':
        fig = generate_pgs_histogram_plot(pgs_data, plot_title)
    elif chart_type == 'box':
        fig = generate_pgs_boxplot(pgs_data, plot_title)
    else:
        raise ValueError(f"Invalid chart type: {chart_type}")
    
    # Save the plot as an HTML file
    fig.write_html(html_path)
    
    # Save the data matrix
    data_matrix = {"pgs_data": pgs_data}
    with open(json_path, 'w') as f:
        json.dump(data_matrix, f)
    
    return f"/{html_path}"

def get_pgs_scores_for_comparison(score_type: str, pgs_ids: List[str], sample_ids: List[str] = None) -> List[Dict[str, Any]]:
    """
    Get scores for multiple PGS IDs using the repository.
    
    Parameters:
    -----------
    score_type : str
        Type of score to retrieve
    pgs_ids : list
        List of PGS IDs to retrieve scores for
    sample_ids : list, optional
        List of sample IDs to filter by
    
    Returns:
    --------
    list
        List of dictionaries containing PGS data
    """
    result = []
    
    # For each PGS ID, retrieve the scores
    for i, pgs_id in enumerate(pgs_ids):
        # Get scores from repository
        scores_dict = score_repository.get_scores_for_pgs(pgs_id, score_type, sample_ids)
        
        if not scores_dict:
            continue  # Skip if no data found for this PGS
        
        # Convert to samples format
        valid_samples = [{"SAMPLE_ID": sample_id, "SCORE": score} for sample_id, score in scores_dict.items()]
        scores = [sample["SCORE"] for sample in valid_samples]
        
        result.append({
            "values": scores,
            "samples": valid_samples,
            "name": pgs_id  # Will be replaced with display name later
        })
    
    return result

def generate_pgs_density_plot(pgs_data: List[Dict[str, Any]], plot_title: str) -> go.Figure:
    """
    Generate density plot for PGS data.
    
    Parameters:
    -----------
    pgs_data : list
        List of dictionaries containing PGS data
    plot_title : str
        Title for the plot
    
    Returns:
    --------
    plotly.graph_objects.Figure
        Plotly figure object
    """
    fig = go.Figure()
    
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
                    name=f"{pgs['name']} (n={len(pgs['values'])})",
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
        margin=dict(l=60, r=150, t=50, b=50),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0.05)',
        height=600,
        width=900
    )
    
    return fig

def generate_pgs_histogram_plot(pgs_data: List[Dict[str, Any]], plot_title: str) -> go.Figure:
    """
    Generate histogram plot for PGS data.
    
    Parameters:
    -----------
    pgs_data : list
        List of dictionaries containing PGS data
    plot_title : str
        Title for the plot
    
    Returns:
    --------
    plotly.graph_objects.Figure
        Plotly figure object
    """
    fig = go.Figure()
    
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
                name=f"{pgs['name']} (n={len(pgs['values'])})",
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
        margin=dict(l=60, r=150, t=50, b=50),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0.05)',
        height=600,
        width=900
    )
    
    return fig

def generate_pgs_boxplot(pgs_data: List[Dict[str, Any]], plot_title: str) -> go.Figure:
    """
    Generate box plot for PGS data.
    
    Parameters:
    -----------
    pgs_data : list
        List of dictionaries containing PGS data
    plot_title : str
        Title for the plot
    
    Returns:
    --------
    plotly.graph_objects.Figure
        Plotly figure object
    """
    fig = go.Figure()
    
    # Add boxplots for each PGS
    for pgs in pgs_data:
        if pgs["values"] and len(pgs["values"]) > 0:
            # Calculate boxplot stats to match D3 implementation
            values = sorted(pgs["values"])
            
            fig.add_trace(go.Box(
                y=values,
                name=f"{pgs['name']} (n={len(pgs['values'])})",
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
        margin=dict(l=60, r=150, t=50, b=50),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0.05)',
        height=600,
        width=900
    )
    
    return fig

def generate_cohort_visualization(request_data: Dict[str, Any], html_path: str, json_path: str) -> str:
    """
    Generate visualization comparing scores across different cohorts.
    
    Parameters:
    -----------
    request_data : dict
        Dictionary containing parameters for cohort comparison
    html_path : str
        Path to save the HTML visualization
    json_path : str
        Path to save the JSON data
    
    Returns:
    --------
    str
        Path to the generated HTML visualization
    """
    # Extract parameters
    pgs_id = request_data.get("pgs_id", "")
    score_type = request_data.get("score_type", "")
    cohorts = request_data.get("cohorts", [])
    chart_type = request_data.get("chart_type", "")
    plot_title = request_data.get("plot_title", "")
    
    if not pgs_id or not score_type or not cohorts:
        raise ValueError("Missing required fields for cohort analysis")
    
    # Get cohort data from database
    cohort_data = score_repository.get_score_by_cohorts(pgs_id=pgs_id, score_type=score_type, cohorts=cohorts)
    
    # Create visualization based on chart type
    fig = None
    if chart_type == 'density':
        fig = generate_cohort_density(cohort_data, plot_title)
    elif chart_type == 'histogram':
        fig = generate_cohort_histogram(cohort_data, plot_title)
    elif chart_type == 'box':
        fig = generate_cohort_boxplot(cohort_data, plot_title)
    else:
        raise ValueError(f"Invalid chart type: {chart_type}")
    
    # Save the plot as an HTML file
    fig.write_html(html_path)
    
    # Save the data matrix
    data_matrix = {"cohorts": cohort_data}
    with open(json_path, 'w') as f:
        json.dump(data_matrix, f)
    
    return f"/{html_path}"

def generate_cohort_density(cohort_data: List[Dict[str, Any]], plot_title: str) -> go.Figure:
    """
    Generate density plot for cohort data.
    
    Parameters:
    -----------
    cohort_data : list
        List of dictionaries containing cohort data
    plot_title : str
        Title for the plot
    
    Returns:
    --------
    plotly.graph_objects.Figure
        Plotly figure object
    """
    # Create Plotly figure
    fig = go.Figure()

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
        margin=dict(l=60, r=150, t=50, b=50),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0.05)',
        height=600,
        width=900
    )

    return fig 

def generate_cohort_histogram(cohort_data: List[Dict[str, Any]], plot_title: str) -> go.Figure:
    """
    Generate histogram plot for cohort data.
    
    Parameters:
    -----------
    cohort_data : list
        List of dictionaries containing cohort data
    plot_title : str
        Title for the plot
    
    Returns:
    --------
    plotly.graph_objects.Figure
        Plotly figure object
    """
    # Create Plotly figure
    fig = go.Figure()

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
        margin=dict(l=60, r=150, t=50, b=50),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0.05)',
        height=600,
        width=900
    )

    return fig

def generate_cohort_boxplot(cohort_data: List[Dict[str, Any]], plot_title: str) -> go.Figure:
    """
    Generate box plot for cohort data.
    
    Parameters:
    -----------
    cohort_data : list
        List of dictionaries containing cohort data
    plot_title : str
        Title for the plot
    
    Returns:
    --------
    plotly.graph_objects.Figure
        Plotly figure object
    """
    # Create Plotly figure
    fig = go.Figure()
    
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
        margin=dict(l=60, r=150, t=50, b=50),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0.05)',
        height=600,
        width=900
    )

    return fig
