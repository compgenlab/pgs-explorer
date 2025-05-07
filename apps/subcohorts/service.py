import os
import json
import uuid
import numpy as np
from typing import List, Dict, Any, Tuple
from scipy import stats
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Import repositories 
from database import get_score_repository, get_ancestry_repository
score_repository = get_score_repository()
ancestry_repository = get_ancestry_repository()

def process_subcohort_plot(request_data: Dict[str, Any]) -> str:
    """
    Generate subcohort comparison plots with optional odds ratio analysis.
    
    Parameters:
    -----------
    request_data : Dict[str, Any]
        Dictionary containing request parameters
    
    Returns:
    --------
    str
        Path to the generated HTML plot
    """
    try:
        # Extract parameters
        plot_params = extract_plot_parameters(request_data)
        
        # Get base cohort and subcohort data
        base_scores, subcohort_data, table_data = get_cohort_data(
            plot_params["pgs_id"], 
            plot_params["score_type"], 
            plot_params["base_cohort"], 
            plot_params["subcohorts"]
        )
        
        # Generate the plot
        fig = generate_subcohort_plot(
            base_scores, 
            subcohort_data, 
            plot_params
        )
        
        # Save and return the file path
        return save_plot_to_file(fig)
        
    except Exception as e:
        # Log the error
        print(f"Error generating subcohort plot: {str(e)}")
        raise e

def extract_plot_parameters(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract and validate plot parameters from request data.
    
    Parameters:
    -----------
    request_data : Dict[str, Any]
        Dictionary containing request parameters
    
    Returns:
    --------
    Dict[str, Any]
        Dictionary of validated parameters
    """
    # Required parameters
    pgs_id = request_data.get("pgs_id")
    score_type = request_data.get("score_type")
    base_cohort = request_data.get("base_cohort")
    subcohorts = request_data.get("subcohorts", [])
    
    # Optional parameters with defaults
    plot_title = request_data.get("plot_title", "")
    display_or = request_data.get("display_or", False)
    normalize_bins = request_data.get("normalize_bins", False)
    bin_size = request_data.get("bin_size", 30)
    or_calculation_type = request_data.get("or_calculation_type")
    threshold_value = request_data.get("threshold_value")
    quantile_count = request_data.get("quantile_count", 10)
    decile_count = request_data.get("decile_count", 10)
    
    # Validate required fields
    if not all([pgs_id, score_type, base_cohort, subcohorts]):
        missing = []
        if not pgs_id: missing.append("pgs_id")
        if not score_type: missing.append("score_type")
        if not base_cohort: missing.append("base_cohort")
        if not subcohorts: missing.append("subcohorts")
        raise ValueError(f"Missing required parameters: {', '.join(missing)}")
    
    return {
        "pgs_id": pgs_id,
        "score_type": score_type,
        "base_cohort": base_cohort,
        "subcohorts": subcohorts,
        "plot_title": plot_title,
        "display_or": display_or,
        "normalize_bins": normalize_bins,
        "bin_size": bin_size,
        "or_calculation_type": or_calculation_type,
        "threshold_value": threshold_value,
        "quantile_count": quantile_count,
        "decile_count": decile_count
    }

def get_cohort_data(
    pgs_id: str, 
    score_type: str, 
    base_cohort: str, 
    subcohorts: List[Dict[str, Any]]
) -> Tuple[List[float], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Retrieve score data for base cohort and subcohorts using repositories.
    
    Parameters:
    -----------
    pgs_id : str
        PGS ID to retrieve scores for
    score_type : str
        Type of score to retrieve
    base_cohort : str
        Name of the base cohort
    subcohorts : List[Dict[str, Any]]
        List of subcohort information
    
    Returns:
    --------
    Tuple[List[float], List[Dict[str, Any]], List[Dict[str, Any]]]
        Tuple containing (base_scores, subcohort_data, table_data)
    """
    # Get scores using the repository
    score_dict = score_repository.get_scores_for_pgs(pgs_id, score_type)
    
    if not score_dict:
        raise ValueError(f"No data found for PGS '{pgs_id}' and Score Type '{score_type}'")
    
    # Get base cohort sample IDs using ancestry repository
    base_sample_ids = ancestry_repository.get_sample_ids_by_cohort(base_cohort)
    
    # Filter to include only samples that exist in our data
    base_valid_samples = [
        {"SAMPLE_ID": sample_id, "SCORE": score_dict[sample_id]}
        for sample_id in base_sample_ids
        if sample_id in score_dict
    ]
    
    if not base_valid_samples:
        raise ValueError(f"No valid samples found for base cohort '{base_cohort}'")
    
    base_scores = [sample["SCORE"] for sample in base_valid_samples]
    
    # Process subcohorts
    subcohort_data = []
    table_data = []
    
    for subcohort in subcohorts:
        if not subcohort.get("active", True):
            continue
        
        # If sample_ids not provided, get them from repository
        if "sample_ids" not in subcohort:
            subcohort["sample_ids"] = ancestry_repository.get_sample_ids_by_cohort(subcohort["name"])
            
        # Filter to include only samples that exist in our data
        valid_samples = [
            {"SAMPLE_ID": sample_id, "SCORE": score_dict[sample_id]}
            for sample_id in subcohort["sample_ids"]
            if sample_id in score_dict
        ]
        
        subcohort_scores = [sample["SCORE"] for sample in valid_samples]
        
        # Calculate percentiles relative to base distribution
        for sample in valid_samples:
            percentile = calculate_percentile(sample["SCORE"], base_scores)
            table_data.append({
                "SAMPLE_ID": sample["SAMPLE_ID"],
                "SCORE": f"{sample['SCORE']:.4f}",
                "PERCENTILE": f"{percentile:.2f}",
                "SUBCOHORT": subcohort["name"]
            })
        
        subcohort_data.append({
            "name": subcohort["name"],
            "color": subcohort["color"],
            "values": subcohort_scores
        })
    
    return base_scores, subcohort_data, table_data

def generate_subcohort_plot(
    base_scores: List[float], 
    subcohort_data: List[Dict[str, Any]], 
    plot_params: Dict[str, Any]
) -> go.Figure:
    """
    Generate the subcohort comparison plot with optional OR analysis.
    
    Parameters:
    -----------
    base_scores : List[float]
        List of scores from the base cohort
    subcohort_data : List[Dict[str, Any]]
        List of subcohort information and scores
    plot_params : Dict[str, Any]
        Dictionary of plot parameters
    
    Returns:
    --------
    go.Figure
        Plotly figure object
    """
    base_cohort = plot_params["base_cohort"]
    display_or = plot_params["display_or"]
    normalize_bins = plot_params["normalize_bins"]
    bin_size = plot_params["bin_size"]
    plot_title = plot_params["plot_title"]
    pgs_id = plot_params["pgs_id"]
    score_type = plot_params["score_type"]
    
    # Create plot
    fig = make_subplots(specs=[[{"secondary_y": display_or}]])
    
    # Set plot dimensions and layout
    fig.update_layout(
        title=plot_title or f"Distribution of {pgs_id} - {score_type}",
        xaxis_title="Score",
        yaxis_title="Density" if not normalize_bins else "Proportion of Samples",
        width=1000,
        height=600,
        margin=dict(l=60, r=160, t=50, b=50),
        legend=dict(x=1.05, y=0.5),
        template="plotly_white"
    )
    
    # Add base cohort density curve
    add_base_cohort_curve(fig, base_scores, base_cohort)
    
    # Calculate and add histogram bins
    add_subcohort_histograms(fig, base_scores, subcohort_data, bin_size, normalize_bins)
    
    # Add odds ratio calculation if requested
    if display_or and len(subcohort_data) == 2:
        add_odds_ratio_analysis(fig, subcohort_data, plot_params)
    
    return fig

def add_base_cohort_curve(fig: go.Figure, base_scores: List[float], base_cohort: str) -> None:
    """
    Add base cohort density curve to the plot.
    
    Parameters:
    -----------
    fig : go.Figure
        Plotly figure to add trace to
    base_scores : List[float]
        List of scores from the base cohort
    base_cohort : str
        Name of the base cohort
    """
    # Calculate KDE curve
    kde_xs = np.linspace(min(base_scores), max(base_scores), 1000)
    kde = stats.gaussian_kde(base_scores)
    kde_ys = kde(kde_xs)
    
    # Add density curve
    fig.add_trace(
        go.Scatter(
            x=kde_xs,
            y=kde_ys,
            mode="lines",
            line=dict(color="#1f77b4", width=2),
            name=f"{base_cohort} ({len(base_scores)} samples, density)"
        )
    )

def add_subcohort_histograms(
    fig: go.Figure, 
    base_scores: List[float], 
    subcohort_data: List[Dict[str, Any]], 
    bin_size: int, 
    normalize_bins: bool
) -> None:
    """
    Add subcohort histograms to the plot.
    
    Parameters:
    -----------
    fig : go.Figure
        Plotly figure to add traces to
    base_scores : List[float]
        List of scores from the base cohort
    subcohort_data : List[Dict[str, Any]]
        List of subcohort information and scores
    bin_size : int
        Number of bins for the histogram
    normalize_bins : bool
        Whether to normalize bin heights
    """
    # Calculate histogram bins
    all_scores = base_scores.copy()
    for subcohort in subcohort_data:
        all_scores.extend(subcohort["values"])
    
    bins = np.histogram_bin_edges(all_scores, bins=bin_size)
    
    # Add subcohort histograms
    for subcohort in subcohort_data:
        hist, _ = np.histogram(subcohort["values"], bins=bins)
        
        # Normalize if requested
        if normalize_bins:
            hist = hist / len(subcohort["values"])
            
        fig.add_trace(
            go.Bar(
                x=[(bins[i] + bins[i+1])/2 for i in range(len(bins)-1)],
                y=hist,
                opacity=0.6,
                width=bins[1]-bins[0],
                name=f"{subcohort['name']} ({len(subcohort['values'])} samples)",
                marker_color=subcohort["color"],
                marker_line_color="black",
                marker_line_width=0.5
            )
        )

def add_odds_ratio_analysis(
    fig: go.Figure, 
    subcohort_data: List[Dict[str, Any]], 
    plot_params: Dict[str, Any]
) -> None:
    """
    Add odds ratio analysis to the plot.
    
    Parameters:
    -----------
    fig : go.Figure
        Plotly figure to add OR traces to
    subcohort_data : List[Dict[str, Any]]
        List of subcohort data (must be exactly 2 subcohorts)
    plot_params : Dict[str, Any]
        Dictionary of plot parameters
    """
    or_calculation_type = plot_params["or_calculation_type"]
    bin_size = plot_params["bin_size"]
    threshold_value = plot_params["threshold_value"]
    quantile_count = plot_params["quantile_count"]
    decile_count = plot_params["decile_count"]
    
    # Configure secondary y-axis for OR
    fig.update_layout(
        yaxis2=dict(
            title="Odds Ratio",
            side="right",
            type="log",
            overlaying="y",
            showgrid=False
        )
    )
    
    # Add reference line at OR = 1
    fig.add_shape(
        type="line",
        x0=0, x1=1,
        y0=1, y1=1,
        xref="paper",
        yref="y2",
        line=dict(color="black", width=1, dash="dash"),
        opacity=0.6
    )
    
    # Choose appropriate OR calculation based on type
    if or_calculation_type == "bin":
        add_or_by_bin_cumulative(fig, subcohort_data, bin_size)
    elif or_calculation_type == "quantile":
        add_or_by_quantile_cumulative(fig, subcohort_data, quantile_count)
    elif or_calculation_type == "threshold":
        add_or_by_threshold(fig, subcohort_data, threshold_value or 0)
    elif or_calculation_type == "decileBaseline":
        add_or_by_decile_vs_baseline(fig, subcohort_data, decile_count)
    elif or_calculation_type == "decileCumulative":
        add_or_by_decile_vs_cumulative(fig, subcohort_data, decile_count)

def add_or_by_bin_cumulative(
    fig: go.Figure, 
    data: List[Dict[str, Any]], 
    bin_size: int
) -> None:
    """
    Add odds ratio analysis by histogram bin (cumulative).
    
    Parameters:
    -----------
    fig : go.Figure
        Plotly figure to add traces to
    data : List[Dict[str, Any]]
        List of subcohort data (must be exactly 2 subcohorts)
    bin_size : int
        Number of bins for the histogram
    """
    or_result = calculate_OR_by_bin_cumulative(data, bin_size)
    
    # Add OR line
    fig.add_trace(
        go.Scatter(
            x=[d["x"] for d in or_result["oddsRatios"]],
            y=[d["or"] for d in or_result["oddsRatios"]],
            mode="lines",
            line=dict(color="red", width=2),
            name=f"OR: {data[0]['name']} vs {data[1]['name']}",
            yaxis="y2"
        )
    )
    
    # Add CI area
    fig.add_trace(
        go.Scatter(
            x=[d["x"] for d in or_result["confidenceIntervals"]],
            y=[d["y1"] for d in or_result["confidenceIntervals"]],
            mode="lines",
            line=dict(width=0),
            showlegend=False,
            yaxis="y2"
        )
    )
    
    fig.add_trace(
        go.Scatter(
            x=[d["x"] for d in or_result["confidenceIntervals"]],
            y=[d["y0"] for d in or_result["confidenceIntervals"]],
            mode="lines",
            line=dict(width=0),
            fillcolor="rgba(255, 0, 0, 0.2)",
            fill="tonexty",
            name="95% CI",
            yaxis="y2"
        )
    )

def add_or_by_quantile_cumulative(
    fig: go.Figure, 
    data: List[Dict[str, Any]], 
    quantile_count: int
) -> None:
    """
    Add odds ratio analysis by quantiles (cumulative).
    
    Parameters:
    -----------
    fig : go.Figure
        Plotly figure to add traces to
    data : List[Dict[str, Any]]
        List of subcohort data (must be exactly 2 subcohorts)
    quantile_count : int
        Number of quantiles to use
    """
    or_result = calculate_OR_by_quantile_cumulative(data, quantile_count)
    
    # Add vertical lines at quantile breakpoints
    for i, d in enumerate(or_result["oddsRatios"]):
        if i > 0:  # Skip first point
            fig.add_shape(
                type="line",
                x0=d["x"], x1=d["x"],
                y0=0, y1=1,
                yref="paper",
                line=dict(color="#aaa", width=1, dash="dash"),
                opacity=0.4
            )
    
    # Add OR points and CI lines
    for d in or_result["oddsRatios"]:
        fig.add_trace(
            go.Scatter(
                x=[d["x"]],
                y=[d["or"]],
                mode="markers",
                marker=dict(color="red", size=8),
                showlegend=False,
                yaxis="y2"
            )
        )
        
        fig.add_shape(
            type="line",
            x0=d["x"], x1=d["x"],
            y0=d["ci95low"], y1=d["ci95high"],
            line=dict(color="red", width=2),
            yref="y2"
        )
    
    # Add OR to legend
    fig.add_trace(
        go.Scatter(
            x=[None],
            y=[None],
            mode="markers",
            marker=dict(color="red", size=8),
            name=f"OR: {data[0]['name']} vs {data[1]['name']}",
            yaxis="y2"
        )
    )
    
    fig.add_trace(
        go.Scatter(
            x=[None],
            y=[None],
            mode="lines",
            line=dict(color="red", width=2),
            name="95% CI",
            yaxis="y2"
        )
    )

def add_or_by_threshold(
    fig: go.Figure, 
    data: List[Dict[str, Any]], 
    threshold: float
) -> None:
    """
    Add odds ratio analysis at a specific threshold.
    
    Parameters:
    -----------
    fig : go.Figure
        Plotly figure to add traces to
    data : List[Dict[str, Any]]
        List of subcohort data (must be exactly 2 subcohorts)
    threshold : float
        Threshold value to calculate OR at
    """
    or_result = calculate_OR_by_threshold(data, threshold)
    
    # Add threshold line
    fig.add_shape(
        type="line",
        x0=or_result["threshold"], x1=or_result["threshold"],
        y0=0, y1=1,
        yref="paper",
        line=dict(color="blue", width=1, dash="dash"),
        opacity=0.8
    )
    
    # Add OR point and CI line
    fig.add_trace(
        go.Scatter(
            x=[or_result["threshold"]],
            y=[or_result["or"]],
            mode="markers",
            marker=dict(color="red", size=8),
            name=f"OR at {or_result['threshold']:.2f}: {or_result['or']:.2f} ({data[0]['name']} vs {data[1]['name']})",
            yaxis="y2"
        )
    )
    
    fig.add_shape(
        type="line",
        x0=or_result["threshold"], x1=or_result["threshold"],
        y0=or_result["ci95low"], y1=or_result["ci95high"],
        line=dict(color="red", width=2),
        yref="y2"
    )
    
    # Add CI to legend
    fig.add_trace(
        go.Scatter(
            x=[None],
            y=[None],
            mode="lines",
            line=dict(color="red", width=2),
            name=f"95% CI: [{or_result['ci95low']:.2f}, {or_result['ci95high']:.2f}]",
            yaxis="y2"
        )
    )

def add_or_by_decile_vs_baseline(
    fig: go.Figure, 
    data: List[Dict[str, Any]], 
    decile_count: int
) -> None:
    """
    Add odds ratio analysis by decile compared to baseline (1st decile).
    
    Parameters:
    -----------
    fig : go.Figure
        Plotly figure to add traces to
    data : List[Dict[str, Any]]
        List of subcohort data (must be exactly 2 subcohorts)
    decile_count : int
        Number of deciles to use
    """
    or_result = calculate_OR_by_decile_vs_baseline(data, decile_count)
    
    # Add decile markers
    for i, breakpoint in enumerate(or_result["decileBreakpoints"]):
        if i > 0:  # Skip first point (minimum value)
            fig.add_shape(
                type="line",
                x0=breakpoint, x1=breakpoint,
                y0=0, y1=1,
                yref="paper",
                line=dict(color="#aaa", width=1, dash="dash"),
                opacity=0.4
            )
            
            # Add decile label
            fig.add_annotation(
                x=breakpoint,
                y=0,
                yref="paper",
                text=f"D{i+1}",
                showarrow=False,
                font=dict(size=8),
                yshift=-15
            )
    
    # Add OR points and CI lines
    x_values = []
    or_values = []
    
    for d in or_result["oddsRatios"]:
        x_values.append(d["x"])
        or_values.append(d["or"])
        
        fig.add_trace(
            go.Scatter(
                x=[d["x"]],
                y=[d["or"]],
                mode="markers",
                marker=dict(color="red", size=8),
                showlegend=False,
                yaxis="y2"
            )
        )
        
        fig.add_shape(
            type="line",
            x0=d["x"], x1=d["x"],
            y0=d["ci95low"], y1=d["ci95high"],
            line=dict(color="red", width=2),
            yref="y2"
        )
    
    # Connect points with line
    fig.add_trace(
        go.Scatter(
            x=x_values,
            y=or_values,
            mode="lines",
            line=dict(color="red", width=1.5, dash="dash"),
            name=f"OR by Decile vs Baseline: {data[0]['name']} vs {data[1]['name']}",
            yaxis="y2"
        )
    )
    
    # Add CI to legend
    fig.add_trace(
        go.Scatter(
            x=[None],
            y=[None],
            mode="lines",
            line=dict(color="red", width=2),
            name="95% CI",
            yaxis="y2"
        )
    )

def add_or_by_decile_vs_cumulative(
    fig: go.Figure, 
    data: List[Dict[str, Any]], 
    decile_count: int
) -> None:
    """
    Add odds ratio analysis by decile vs cumulative lower deciles.
    
    Parameters:
    -----------
    fig : go.Figure
        Plotly figure to add traces to
    data : List[Dict[str, Any]]
        List of subcohort data (must be exactly 2 subcohorts)
    decile_count : int
        Number of deciles to use
    """
    or_result = calculate_OR_by_decile_vs_cumulative(data, decile_count)
    
    # Add decile markers
    for i, breakpoint in enumerate(or_result["decileBreakpoints"]):
        if i > 0:  # Skip first point (minimum value)
            fig.add_shape(
                type="line",
                x0=breakpoint, x1=breakpoint,
                y0=0, y1=1,
                yref="paper",
                line=dict(color="#aaa", width=1, dash="dash"),
                opacity=0.4
            )
            
            # Add decile label
            fig.add_annotation(
                x=breakpoint,
                y=0,
                yref="paper",
                text=f"D{i+1}",
                showarrow=False,
                font=dict(size=8),
                yshift=-15
            )
    
    # Add OR points and CI lines
    x_values = []
    or_values = []
    
    for d in or_result["oddsRatios"]:
        x_values.append(d["x"])
        or_values.append(d["or"])
        
        fig.add_trace(
            go.Scatter(
                x=[d["x"]],
                y=[d["or"]],
                mode="markers",
                marker=dict(color="purple", size=8),
                showlegend=False,
                yaxis="y2"
            )
        )
        
        fig.add_shape(
            type="line",
            x0=d["x"], x1=d["x"],
            y0=d["ci95low"], y1=d["ci95high"],
            line=dict(color="purple", width=2),
            yref="y2"
        )
    
    # Connect points with line
    fig.add_trace(
        go.Scatter(
            x=x_values,
            y=or_values,
            mode="lines",
            line=dict(color="purple", width=1.5, dash="dash"),
            name=f"OR by Decile vs Cumulative Lower: {data[0]['name']} vs {data[1]['name']}",
            yaxis="y2"
        )
    )
    
    # Add CI to legend
    fig.add_trace(
        go.Scatter(
            x=[None],
            y=[None],
            mode="lines",
            line=dict(color="purple", width=2),
            name="95% CI",
            yaxis="y2"
        )
    )

def save_plot_to_file(fig: go.Figure) -> str:
    """
    Save the plot to an HTML file.
    
    Parameters:
    -----------
    fig : go.Figure
        Plotly figure to save
    
    Returns:
    --------
    str
        Path to the saved file
    """
    plot_id = str(uuid.uuid4())
    plot_dir = "temp"
    os.makedirs(plot_dir, exist_ok=True)
    plot_path = os.path.join(plot_dir, f"{plot_id}.html")
    
    fig.write_html(plot_path, include_plotlyjs="cdn")
    
    return f"/temp/{plot_id}.html"

# OR calculation functions
def calculate_OR_by_bin_cumulative(data, bin_size):
    """Calculate odds ratio by histogram bin (cumulative)."""
    all_values = data[0]["values"] + data[1]["values"]
    domain = [min(all_values), max(all_values)]
    
    # Create histogram bins
    bin_edges = np.linspace(domain[0], domain[1], bin_size + 1)
    
    odds_ratios = []
    confidence_intervals = []
    
    # For each bin threshold, calculate OR cumulatively
    for i in range(len(bin_edges) - 1):
        threshold = bin_edges[i]
        
        # Count values greater than or equal to threshold
        a = sum(1 for v in data[0]["values"] if v >= threshold)
        b = len(data[0]["values"]) - a
        c = sum(1 for v in data[1]["values"] if v >= threshold)
        d = len(data[1]["values"]) - c
        
        # Add small constant to avoid division by zero
        epsilon = 0.5
        
        # Calculate odds ratio
        or_value = ((a + epsilon) * (d + epsilon)) / ((b + epsilon) * (c + epsilon))
        
        # Calculate 95% CI
        log_or = np.log(or_value)
        se_log_or = np.sqrt(1/(a + epsilon) + 1/(b + epsilon) + 1/(c + epsilon) + 1/(d + epsilon))
        ci95low = np.exp(log_or - 1.96 * se_log_or)
        ci95high = np.exp(log_or + 1.96 * se_log_or)
        
        odds_ratios.append({
            "x": float(threshold),
            "or": float(or_value),
            "ci95low": float(ci95low),
            "ci95high": float(ci95high)
        })
        
        confidence_intervals.append({
            "x": float(threshold),
            "y0": float(ci95low),
            "y1": float(ci95high)
        })
    
    return {"oddsRatios": odds_ratios, "confidenceIntervals": confidence_intervals}

def calculate_OR_by_quantile_cumulative(data, num_quantiles):
    """Calculate odds ratio by quantiles (cumulative)."""
    all_values = data[0]["values"] + data[1]["values"]
    
    # Calculate quantile breakpoints
    quantile_breaks = [np.quantile(all_values, i / num_quantiles) for i in range(1, num_quantiles)]
    
    # Add min and max to create complete range
    min_value = min(all_values)
    max_value = max(all_values)
    
    odds_ratios = []
    confidence_intervals = []
    
    # Start with the minimum value
    a0 = len(data[0]["values"])  # All values
    b0 = 0  # Should be 0
    c0 = len(data[1]["values"])  # All values
    d0 = 0  # Should be 0
    
    # Add small constant to avoid division by zero
    epsilon = 0.5
    or0 = ((a0 + epsilon) * (d0 + epsilon)) / ((b0 + epsilon) * (c0 + epsilon))
    
    # Calculate 95% CI
    log_or0 = np.log(or0)
    se_log_or0 = np.sqrt(1/(a0 + epsilon) + 1/(b0 + epsilon) + 1/(c0 + epsilon) + 1/(d0 + epsilon))
    ci95low0 = np.exp(log_or0 - 1.96 * se_log_or0)
    ci95high0 = np.exp(log_or0 + 1.96 * se_log_or0)
    
    odds_ratios.append({
        "x": float(min_value),
        "or": float(or0),
        "ci95low": float(ci95low0),
        "ci95high": float(ci95high0)
    })
    
    confidence_intervals.append({
        "x": float(min_value),
        "y0": float(ci95low0),
        "y1": float(ci95high0)
    })
    
    # For each quantile threshold, calculate cumulative OR
    for i in range(len(quantile_breaks) - 1):
        threshold = quantile_breaks[i]
        upper_bound = quantile_breaks[i + 1]
        
        # Count values above threshold for both cohorts
        a = sum(1 for v in data[0]["values"] if v >= threshold)
        b = len(data[0]["values"]) - a
        c = sum(1 for v in data[1]["values"] if v >= threshold)
        d = len(data[1]["values"]) - c
        
        # Add small constant to avoid division by zero
        epsilon = 0.5
        
        # Calculate odds ratio
        or_value = ((a + epsilon) * (d + epsilon)) / ((b + epsilon) * (c + epsilon))
        
        # Calculate 95% CI
        log_or = np.log(or_value)
        se_log_or = np.sqrt(1/(a + epsilon) + 1/(b + epsilon) + 1/(c + epsilon) + 1/(d + epsilon))
        ci95low = np.exp(log_or - 1.96 * se_log_or)
        ci95high = np.exp(log_or + 1.96 * se_log_or)
        
        odds_ratios.append({
            "x": float(threshold),
            "or": float(or_value),
            "ci95low": float(ci95low),
            "ci95high": float(ci95high)
        })
        
        confidence_intervals.append({
            "x": float(threshold),
            "y0": float(ci95low),
            "y1": float(ci95high)
        })
    
    return {"oddsRatios": odds_ratios, "confidenceIntervals": confidence_intervals}

def calculate_OR_by_threshold(data, threshold):
    """Calculate odds ratio at a specific threshold."""
    # Count values above/below threshold for both subcohorts
    a = sum(1 for v in data[0]["values"] if v >= threshold)
    b = len(data[0]["values"]) - a
    c = sum(1 for v in data[1]["values"] if v >= threshold)
    d = len(data[1]["values"]) - c
    
    # Add small constant to avoid division by zero
    epsilon = 0.5
    
    # Calculate odds ratio
    or_value = ((a + epsilon) * (d + epsilon)) / ((b + epsilon) * (c + epsilon))
    
    # Calculate 95% CI
    log_or = np.log(or_value)
    se_log_or = np.sqrt(1/(a + epsilon) + 1/(b + epsilon) + 1/(c + epsilon) + 1/(d + epsilon))
    ci95low = np.exp(log_or - 1.96 * se_log_or)
    ci95high = np.exp(log_or + 1.96 * se_log_or)
    
    return {
        "threshold": float(threshold),
        "or": float(or_value),
        "ci95low": float(ci95low), 
        "ci95high": float(ci95high)
    }

def calculate_OR_by_decile_vs_baseline(data, num_deciles=10):
    """Calculate odds ratio by decile compared to baseline (1st decile)."""
    # Combine all values to determine decile breakpoints
    all_values = data[0]["values"] + data[1]["values"]
    all_values.sort()
    
    # Calculate decile breakpoints
    decile_breakpoints = [np.quantile(all_values, i / num_deciles) for i in range(num_deciles + 1)]
    
    # Create containers for counts in each decile
    cases_by_decile = [0] * num_deciles
    ctrls_by_decile = [0] * num_deciles
    
    # Assign values to appropriate deciles
    for value in data[0]["values"]:
        decile_index = next((i for i in range(1, len(decile_breakpoints)) 
                            if value < decile_breakpoints[i]), len(decile_breakpoints) - 1) - 1
        cases_by_decile[decile_index] += 1
    
    for value in data[1]["values"]:
        decile_index = next((i for i in range(1, len(decile_breakpoints)) 
                            if value < decile_breakpoints[i]), len(decile_breakpoints) - 1) - 1
        ctrls_by_decile[decile_index] += 1
    
    # Calculate baseline odds (1st decile)
    baseline_cases = cases_by_decile[0]
    baseline_ctrls = ctrls_by_decile[0]
    
    # Calculate odds ratios for each decile compared to baseline
    odds_ratios = []
    confidence_intervals = []
    
    for i in range(num_deciles):
        # Values for the current decile
        a = cases_by_decile[i]
        b = ctrls_by_decile[i]
        
        # Values for the baseline (1st decile)
        c = baseline_cases
        d = baseline_ctrls
        
        # Add small constant to avoid division by zero
        epsilon = 0.5
        
        # Calculate odds ratio: (a/b)/(c/d) = (a*d)/(b*c)
        or_value = ((a + epsilon) * (d + epsilon)) / ((b + epsilon) * (c + epsilon))
        
        # Calculate 95% CI
        log_or = np.log(or_value)
        se_log_or = np.sqrt(1/(a + epsilon) + 1/(b + epsilon) + 1/(c + epsilon) + 1/(d + epsilon))
        ci95low = np.exp(log_or - 1.96 * se_log_or)
        ci95high = np.exp(log_or + 1.96 * se_log_or)
        odds_ratios.append({"decile": i + 1,
            "x": float(decile_breakpoints[i]),
            "or": float(or_value),
            "ci95low": float(ci95low),
            "ci95high": float(ci95high),
            "caseCount": int(a),
            "ctrlCount": int(b)
        })
        
        confidence_intervals.append({
            "decile": i + 1,
            "x": float(decile_breakpoints[i]),
            "y0": float(ci95low),
            "y1": float(ci95high)
        })
    
    return {
        "oddsRatios": odds_ratios, 
        "confidenceIntervals": confidence_intervals, 
        "decileBreakpoints": [float(bp) for bp in decile_breakpoints]
    }

def calculate_OR_by_decile_vs_cumulative(data, num_deciles=10):
    """Calculate odds ratio by decile compared to all lower deciles combined."""
    # Combine all values to determine decile breakpoints
    all_values = data[0]["values"] + data[1]["values"]
    all_values.sort()
    
    # Calculate decile breakpoints
    decile_breakpoints = [np.quantile(all_values, i / num_deciles) for i in range(num_deciles + 1)]
    
    # Create containers for counts in each decile
    cases_by_decile = [0] * num_deciles
    ctrls_by_decile = [0] * num_deciles
    
    # Assign values to appropriate deciles
    for value in data[0]["values"]:
        decile_index = next((i for i in range(1, len(decile_breakpoints)) 
                            if value < decile_breakpoints[i]), len(decile_breakpoints) - 1) - 1
        cases_by_decile[decile_index] += 1
    
    for value in data[1]["values"]:
        decile_index = next((i for i in range(1, len(decile_breakpoints)) 
                            if value < decile_breakpoints[i]), len(decile_breakpoints) - 1) - 1
        ctrls_by_decile[decile_index] += 1
    
    # Calculate odds ratios for each decile compared to all lower deciles combined
    odds_ratios = []
    confidence_intervals = []
    
    # First decile has no lower deciles, so set to 1.0 (neutral)
    odds_ratios.append({
        "decile": 1,
        "x": float(decile_breakpoints[0]),
        "or": 1.0,
        "ci95low": 1.0,
        "ci95high": 1.0,
        "caseCount": int(cases_by_decile[0]),
        "ctrlCount": int(ctrls_by_decile[0])
    })
    
    confidence_intervals.append({
        "decile": 1,
        "x": float(decile_breakpoints[0]),
        "y0": 1.0,
        "y1": 1.0
    })
    
    # For deciles 2 and above, compare to all lower deciles combined
    for i in range(1, num_deciles):
        # Values for the current decile
        a = cases_by_decile[i]
        b = ctrls_by_decile[i]
        
        # Sum of values for all lower deciles
        c = sum(cases_by_decile[:i])
        d = sum(ctrls_by_decile[:i])
        
        # Add small constant to avoid division by zero
        epsilon = 0.5
        
        # Calculate odds ratio: (a/b)/(c/d) = (a*d)/(b*c)
        or_value = ((a + epsilon) * (d + epsilon)) / ((b + epsilon) * (c + epsilon))
        
        # Calculate 95% CI
        log_or = np.log(or_value)
        se_log_or = np.sqrt(1/(a + epsilon) + 1/(b + epsilon) + 1/(c + epsilon) + 1/(d + epsilon))
        ci95low = np.exp(log_or - 1.96 * se_log_or)
        ci95high = np.exp(log_or + 1.96 * se_log_or)
        
        odds_ratios.append({
            "decile": i + 1,
            "x": float(decile_breakpoints[i]),
            "or": float(or_value),
            "ci95low": float(ci95low),
            "ci95high": float(ci95high),
            "caseCount": int(a),
            "ctrlCount": int(b),
            "lowerCaseCount": int(c),
            "lowerCtrlCount": int(d)
        })
        
        confidence_intervals.append({
            "decile": i + 1,
            "x": float(decile_breakpoints[i]),
            "y0": float(ci95low),
            "y1": float(ci95high)
        })
    
    return {
        "oddsRatios": odds_ratios, 
        "confidenceIntervals": confidence_intervals, 
        "decileBreakpoints": [float(bp) for bp in decile_breakpoints]
    }

def calculate_percentile(value: float, array: List[float]) -> float:
    """Calculate the percentile of a value in an array."""
    sorted_array = sorted(array)
    position = next((i for i, x in enumerate(sorted_array) if x >= value), len(sorted_array))
    
    if position == len(sorted_array):
        return 100.0  # Value is greater than all elements
    
    return (position / len(sorted_array) * 100)