import os
import json
import hashlib
import numpy as np
from typing import List, Dict, Any
from scipy import stats
import plotly.graph_objects as go
from apps.core.utils import process_cache_request
from database import db

def process_distribution(request_data: Dict[str, Any]) -> str:
    """
    Generate distribution plots on the backend, cache them, and return the plot path.
    
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
        # Check cache
        existing, html_path, json_path = process_cache_request(request_data)
        if existing:
            return f"/{html_path}"
        
        # Route to appropriate visualization
        analysis_type = request_data.get("analysis_type")
        
        if analysis_type == 'cohort':
            generate_cohort_visualization(request_data, html_path, json_path)
        elif analysis_type == 'score':
            generate_score_visualization(request_data, html_path, json_path)
        else:
            raise ValueError(f"Invalid analysis type: {analysis_type}")
        
        return f"/{html_path}"
        
    except Exception as e:
        print(f"Error in process_distribution: {str(e)}")
        import traceback
        traceback.print_exc()
        raise e

def generate_score_visualization(request_data: Dict[str, Any], html_path: str, json_path: str) -> None:
    """Generate visualization comparing different PGS scores."""
    # Extract and validate parameters
    params = extract_score_parameters(request_data)
    validate_score_parameters(params)
    
    # Get PGS data
    pgs_data = fetch_pgs_comparison_data(params)
    
    # Enhance data with display attributes
    enhance_pgs_data(pgs_data, params)
    
    # Generate visualization
    fig = create_score_visualization(pgs_data, params)
    
    # Save outputs
    save_visualization_outputs(fig, pgs_data, html_path, json_path, "pgs_data")

def extract_score_parameters(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract parameters for score visualization."""
    pgs_comparison = request_data.get("pgs_comparison", {})
    
    return {
        "score_type": request_data.get("score_type", ""),
        "chart_type": request_data.get("chart_type", ""),
        "plot_title": request_data.get("plot_title", ""),
        "pgs_ids": pgs_comparison.get("pgs_ids", []),
        "sample_ids": pgs_comparison.get("sample_ids", []),
        "colors": pgs_comparison.get("colors", []),
        "display_names": pgs_comparison.get("names", []),
        "user_id": request_data.get("user_id", "")
    }

def validate_score_parameters(params: Dict[str, Any]) -> None:
    """Validate score visualization parameters."""
    if not params["score_type"]:
        raise ValueError("Missing score_type")
    if not params["pgs_ids"]:
        raise ValueError("Missing PGS IDs in comparison")

def fetch_pgs_comparison_data(params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Fetch score data for PGS comparison."""
    result = []
    print(params.keys())
    for pgs_id in params["pgs_ids"]:
        scores_dict = db.active_db.get_scores_for_pgs(
            pgs_id, 
            params["score_type"], 
            params["sample_ids"] if params["sample_ids"] else None,
            user_id=params["user_id"]
        )
        
        if not scores_dict:
            continue
        
        # Convert to required format
        pgs_data = format_pgs_data(pgs_id, scores_dict)
        result.append(pgs_data)
    
    return result

def format_pgs_data(pgs_id: str, scores_dict: Dict[str, float]) -> Dict[str, Any]:
    """Format PGS scores into required structure."""
    valid_samples = [
        {"SAMPLE_ID": sample_id, "SCORE": score} 
        for sample_id, score in scores_dict.items()
    ]
    
    return {
        "values": [sample["SCORE"] for sample in valid_samples],
        "samples": valid_samples,
        "name": pgs_id
    }

def enhance_pgs_data(pgs_data: List[Dict[str, Any]], params: Dict[str, Any]) -> None:
    """Add display names and colors to PGS data."""
    colors = params["colors"]
    display_names = params["display_names"]
    
    for i, pgs in enumerate(pgs_data):
        pgs["color"] = colors[i] if i < len(colors) else "#000000"
        pgs["name"] = display_names[i] if i < len(display_names) else pgs["name"]

def create_score_visualization(pgs_data: List[Dict[str, Any]], params: Dict[str, Any]) -> go.Figure:
    """Create visualization based on chart type."""
    chart_type = params["chart_type"]
    plot_title = params["plot_title"]
    
    visualization_functions = {
        'density': generate_pgs_density_plot,
        'histogram': generate_pgs_histogram_plot,
        'box': generate_pgs_boxplot
    }
    
    if chart_type not in visualization_functions:
        raise ValueError(f"Invalid chart type: {chart_type}")
    
    return visualization_functions[chart_type](pgs_data, plot_title)

def generate_pgs_density_plot(pgs_data: List[Dict[str, Any]], plot_title: str) -> go.Figure:
    """Generate density plot for PGS data."""
    fig = go.Figure()
    
    # Calculate x-axis range
    x_range = calculate_plot_range(pgs_data)
    x = np.linspace(x_range["min"], x_range["max"], 100)
    
    # Add density curves
    for pgs in pgs_data:
        if should_plot_density(pgs["values"]):
            add_density_curve(fig, pgs, x)
    
    # Configure layout
    configure_density_layout(fig, plot_title)
    
    return fig

def calculate_plot_range(data: List[Dict[str, Any]]) -> Dict[str, float]:
    """Calculate appropriate plot range with padding."""
    all_values = extract_all_values(data)
    
    if not all_values:
        raise ValueError("No valid data to plot")
    
    min_val = min(all_values)
    max_val = max(all_values)
    padding = (max_val - min_val) * 0.1
    
    return {
        "min": min_val - padding,
        "max": max_val + padding
    }

def extract_all_values(data: List[Dict[str, Any]]) -> List[float]:
    """Extract all values from data list."""
    all_values = []
    for item in data:
        if item["values"]:
            all_values.extend(item["values"])
    return all_values

def should_plot_density(values: List[float]) -> bool:
    """Check if density plot is appropriate for data."""
    return values and len(values) > 1

def add_density_curve(fig: go.Figure, data: Dict[str, Any], x: np.ndarray) -> None:
    """Add a density curve to the figure."""
    try:
        kde = stats.gaussian_kde(data["values"])
        y = kde(x)
        
        fig.add_trace(go.Scatter(
            x=x,
            y=y,
            mode='lines',
            name=f"{data['name']} (n={len(data['values'])})",
            line=dict(color=data["color"], width=2),
            fill=None
        ))
    except Exception as e:
        print(f"Error creating density plot for {data['name']}: {str(e)}")

def configure_density_layout(fig: go.Figure, plot_title: str) -> None:
    """Configure layout for density plot."""
    fig.update_layout(
        title=plot_title,
        xaxis_title="Score",
        yaxis_title="Density",
        hovermode="closest",
        showlegend=True,
        legend=dict(x=1.02, y=0.98, xanchor="left", yanchor="top"),
        margin=dict(l=60, r=150, t=50, b=50),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0.05)',
        height=600,
        width=900
    )

def generate_pgs_histogram_plot(pgs_data: List[Dict[str, Any]], plot_title: str) -> go.Figure:
    """Generate histogram plot for PGS data."""
    fig = go.Figure()
    
    # Calculate histogram parameters
    hist_params = calculate_histogram_parameters(pgs_data)
    
    # Add histograms
    for i, pgs in enumerate(pgs_data):
        if pgs["values"]:
            add_histogram(fig, pgs, hist_params, i)
    
    # Configure layout
    configure_histogram_layout(fig, plot_title)
    
    return fig

def calculate_histogram_parameters(data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate histogram bin parameters."""
    all_values = extract_all_values(data)
    
    if not all_values:
        raise ValueError("No valid data to plot")
    
    x_range = calculate_plot_range(data)
    num_bins = min(30, int(np.ceil(np.sqrt(len(all_values)))))
    bin_size = (x_range["max"] - x_range["min"]) / num_bins
    
    return {
        "x_min": x_range["min"],
        "x_max": x_range["max"],
        "bin_size": bin_size,
        "num_bins": num_bins
    }

def add_histogram(fig: go.Figure, data: Dict[str, Any], hist_params: Dict[str, Any], 
                 offset_group: int) -> None:
    """Add a histogram to the figure."""
    fig.add_trace(go.Histogram(
        x=data["values"],
        name=f"{data['name']} (n={len(data['values'])})",
        marker_color=data["color"],
        opacity=0.7,
        xbins=dict(
            start=hist_params["x_min"],
            end=hist_params["x_max"],
            size=hist_params["bin_size"]
        ),
        offsetgroup=offset_group
    ))

def configure_histogram_layout(fig: go.Figure, plot_title: str) -> None:
    """Configure layout for histogram plot."""
    fig.update_layout(
        title=plot_title,
        xaxis_title="Score",
        yaxis_title="Frequency",
        barmode='group',
        hovermode="closest",
        showlegend=True,
        legend=dict(x=1.02, y=0.98, xanchor="left", yanchor="top"),
        margin=dict(l=60, r=150, t=50, b=50),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0.05)',
        height=600,
        width=900
    )

def generate_pgs_boxplot(pgs_data: List[Dict[str, Any]], plot_title: str) -> go.Figure:
    """Generate box plot for PGS data."""
    fig = go.Figure()
    
    # Add boxplots
    for pgs in pgs_data:
        if should_plot_boxplot(pgs["values"]):
            add_boxplot(fig, pgs)
    
    # Configure layout
    configure_boxplot_layout(fig, plot_title)
    
    return fig

def should_plot_boxplot(values: List[float]) -> bool:
    """Check if boxplot is appropriate for data."""
    return values and len(values) > 0

def add_boxplot(fig: go.Figure, data: Dict[str, Any]) -> None:
    """Add a boxplot to the figure."""
    fig.add_trace(go.Box(
        y=sorted(data["values"]),
        name=f"{data['name']} (n={len(data['values'])})",
        boxmean=True,
        marker_color=data["color"],
        line=dict(color='black'),
        fillcolor=data["color"],
        opacity=0.7
    ))

def configure_boxplot_layout(fig: go.Figure, plot_title: str) -> None:
    """Configure layout for boxplot."""
    fig.update_layout(
        title=plot_title,
        yaxis_title="Score",
        xaxis_title="PGS",
        hovermode="closest",
        showlegend=False,
        margin=dict(l=60, r=150, t=50, b=50),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0.05)',
        height=600,
        width=900
    )

def generate_cohort_visualization(request_data: Dict[str, Any], html_path: str, json_path: str) -> None:
    """Generate visualization comparing scores across different cohorts."""
    # Extract and validate parameters
    params = extract_cohort_parameters(request_data)
    validate_cohort_parameters(params)
    
    print(f"DEBUG: PGS ID: {params['pgs_id']}")
    print(f"DEBUG: Score type: {params['score_type']}")
    # print(f"DEBUG: Cohorts: {params['cohorts']}")
    
    # Prepare cohorts with sample_ids
    prepared_cohorts = prepare_cohorts_with_sample_ids(params["cohorts"])
    print(f"DEBUG: Prepared cohorts count: {len(prepared_cohorts)}")
    for cohort in prepared_cohorts:
        print(f"DEBUG: Cohort '{cohort['name']}' has {len(cohort.get('sample_ids', []))} samples")
    
    # Get cohort data with sample_ids already populated
    cohort_data = db.active_db.get_score_by_cohorts(
        pgs_id=params["pgs_id"],
        score_type=params["score_type"],
        cohorts=prepared_cohorts,
        user_id = params["user_id"]
    )
    
    print(f"DEBUG: Cohort data count: {len(cohort_data)}")
    for i, data in enumerate(cohort_data):
        print(f"DEBUG: Cohort {i} '{data['name']}' has {len(data['values'])} scores")
    
    # Generate visualization
    fig = create_cohort_visualization(cohort_data, params)
    
    # Save outputs
    save_visualization_outputs(fig, cohort_data, html_path, json_path, "cohorts")

def prepare_cohorts_with_sample_ids(cohorts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Ensure all cohorts have their sample_ids populated.
    
    Parameters:
    -----------
    cohorts : list
        List of cohort dictionaries
        
    Returns:
    --------
    list
        List of cohorts with sample_ids populated
    """
    prepared_cohorts = []
    
    for cohort in cohorts:
        # Skip invalid cohorts
        if "name" not in cohort:
            continue
        
        # Copy cohort to avoid modifying original
        cohort_copy = cohort.copy()
        
        # If sample_ids not provided and it's not the "ALL" cohort, fetch them
        if "sample_ids" not in cohort_copy and cohort_copy["name"] != "ALL":
            cohort_copy["sample_ids"] = db.active_db.sample_ids_by_cohort(cohort_copy["name"])
        
        prepared_cohorts.append(cohort_copy)
    
    return prepared_cohorts

def extract_cohort_parameters(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract parameters for cohort visualization."""
    return {
        "pgs_id": request_data.get("pgs_id", ""),
        "score_type": request_data.get("score_type", ""),
        "cohorts": request_data.get("cohorts", []),
        "chart_type": request_data.get("chart_type", ""),
        "plot_title": request_data.get("plot_title", ""),
        "user_id": request_data.get("user_id", "")
    }

def validate_cohort_parameters(params: Dict[str, Any]) -> None:
    """Validate cohort visualization parameters."""
    if not params["pgs_id"]:
        raise ValueError("Missing pgs_id")
    if not params["score_type"]:
        raise ValueError("Missing score_type")
    if not params["cohorts"]:
        raise ValueError("Missing cohorts")

def create_cohort_visualization(cohort_data: List[Dict[str, Any]], params: Dict[str, Any]) -> go.Figure:
    """Create visualization based on chart type."""
    chart_type = params["chart_type"]
    plot_title = params["plot_title"]
    
    visualization_functions = {
        'density': generate_cohort_density,
        'histogram': generate_cohort_histogram,
        'box': generate_cohort_boxplot
    }
    
    if chart_type not in visualization_functions:
        raise ValueError(f"Invalid chart type: {chart_type}")
    
    return visualization_functions[chart_type](cohort_data, plot_title)

def generate_cohort_density(cohort_data: List[Dict[str, Any]], plot_title: str) -> go.Figure:
    """Generate density plot for cohort data."""
    # Uses same logic as PGS density plot
    return generate_pgs_density_plot(cohort_data, plot_title)

def generate_cohort_histogram(cohort_data: List[Dict[str, Any]], plot_title: str) -> go.Figure:
    """Generate histogram plot for cohort data."""
    # Uses same logic as PGS histogram plot
    return generate_pgs_histogram_plot(cohort_data, plot_title)

def generate_cohort_boxplot(cohort_data: List[Dict[str, Any]], plot_title: str) -> go.Figure:
    """Generate box plot for cohort data."""
    fig = go.Figure()
    
    # Add boxplots with cohort-specific labeling
    for cohort in cohort_data:
        if should_plot_boxplot(cohort["values"]):
            add_cohort_boxplot(fig, cohort)
    
    # Configure layout
    configure_cohort_boxplot_layout(fig, plot_title)
    
    return fig

def add_cohort_boxplot(fig: go.Figure, cohort: Dict[str, Any]) -> None:
    """Add a cohort boxplot to the figure."""
    fig.add_trace(go.Box(
        y=sorted(cohort["values"]),
        name=f"{cohort['name']} (n={len(cohort['values'])})",
        boxmean=True,
        marker_color=cohort["color"],
        line=dict(color='black'),
        fillcolor=cohort["color"],
        opacity=0.7
    ))

def configure_cohort_boxplot_layout(fig: go.Figure, plot_title: str) -> None:
    """Configure layout for cohort boxplot."""
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

def save_visualization_outputs(fig: go.Figure, data: Any, html_path: str, 
                             json_path: str, data_key: str) -> None:
    """Save visualization outputs to files."""
    # Save HTML
    fig.write_html(html_path)
    
    # Save JSON data
    data_matrix = {data_key: data}
    with open(json_path, 'w') as f:
        json.dump(data_matrix, f)