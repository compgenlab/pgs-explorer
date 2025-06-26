import os
import json
import uuid
import numpy as np
from typing import List, Dict, Any, Tuple
from scipy import stats
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from database import db

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
            plot_params["subcohorts"],
            plot_params["user_id"]
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
        print(f"Error generating subcohort plot: {str(e)}")
        raise e

def extract_plot_parameters(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract and validate plot parameters from request data."""
    # Required parameters
    required_params = extract_required_parameters(request_data)
    
    # Optional parameters
    optional_params = extract_optional_parameters(request_data)
    
    # Validate required fields
    validate_required_parameters(required_params)
    
    # Combine all parameters
    return {**required_params, **optional_params}

def extract_required_parameters(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract required parameters from request data."""
    return {
        "pgs_id": request_data.get("pgs_id"),
        "score_type": request_data.get("score_type"),
        "base_cohort": request_data.get("base_cohort"),
        "subcohorts": request_data.get("subcohorts", []),
        "user_id": request_data.get("user_id", None)
    }

def extract_optional_parameters(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract optional parameters with defaults from request data."""
    return {
        "plot_title": request_data.get("plot_title", ""),
        "display_or": request_data.get("display_or", False),
        "normalize_bins": request_data.get("normalize_bins", False),
        "bin_size": request_data.get("bin_size", 30),
        "or_calculation_type": request_data.get("or_calculation_type"),
        "threshold_value": request_data.get("threshold_value"),
        "quantile_count": request_data.get("quantile_count", 10),
        "decile_count": request_data.get("decile_count", 10)
    }

def validate_required_parameters(params: Dict[str, Any]) -> None:
    """Validate that all required parameters are present."""
    missing = []
    if not params["pgs_id"]: missing.append("pgs_id")
    if not params["score_type"]: missing.append("score_type")
    if not params["base_cohort"]: missing.append("base_cohort")
    if not params["subcohorts"]: missing.append("subcohorts")
    
    if missing:
        raise ValueError(f"Missing required parameters: {', '.join(missing)}")

def get_cohort_data(
    pgs_id: str, 
    score_type: str, 
    base_cohort: str, 
    subcohorts: List[Dict[str, Any]],
    user_id: str
) -> Tuple[List[float], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Retrieve score data for base cohort and subcohorts."""
    # Get all scores for this PGS ID
    score_dict = fetch_pgs_scores(pgs_id, score_type, user_id)
    
    # Get base cohort data
    base_scores = fetch_base_cohort_scores(base_cohort, score_dict)
    
    # Process subcohorts
    subcohort_data, table_data = process_subcohorts(
        subcohorts, score_dict, base_scores
    )
    
    return base_scores, subcohort_data, table_data

def fetch_pgs_scores(pgs_id: str, score_type: str, user_id: str) -> Dict[str, float]:
    """Fetch scores for a PGS ID."""
    score_dict = db.get_scores_for_pgs(pgs_id, score_type, user_id=user_id)
    
    if not score_dict:
        raise ValueError(f"No data found for PGS '{pgs_id}' and Score Type '{score_type}'")
    
    return score_dict

def fetch_base_cohort_scores(base_cohort: str, score_dict: Dict[str, float]) -> List[float]:
    """Fetch and filter scores for the base cohort."""
    # Get base cohort sample IDs
    base_sample_ids = db.ancestry.get_sample_ids_by_cohort(base_cohort)
    
    # Filter to include only samples that exist in our data
    base_valid_samples = filter_valid_samples(base_sample_ids, score_dict)
    
    if not base_valid_samples:
        raise ValueError(f"No valid samples found for base cohort '{base_cohort}'")
    
    return [sample["SCORE"] for sample in base_valid_samples]

def filter_valid_samples(sample_ids: List[str], score_dict: Dict[str, float]) -> List[Dict[str, Any]]:
    """Filter sample IDs to only those with scores."""
    return [
        {"SAMPLE_ID": sample_id, "SCORE": score_dict[sample_id]}
        for sample_id in sample_ids
        if sample_id in score_dict
    ]

def process_subcohorts(
    subcohorts: List[Dict[str, Any]], 
    score_dict: Dict[str, float], 
    base_scores: List[float]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Process all subcohorts and create data structures."""
    subcohort_data = []
    table_data = []
    
    for subcohort in subcohorts:
        if not subcohort.get("active", True):
            continue
        
        # Process individual subcohort
        cohort_result = process_single_subcohort(
            subcohort, score_dict, base_scores
        )
        
        if cohort_result:
            subcohort_data.append(cohort_result["subcohort_info"])
            table_data.extend(cohort_result["table_entries"])
    
    return subcohort_data, table_data

def process_single_subcohort(
    subcohort: Dict[str, Any], 
    score_dict: Dict[str, float], 
    base_scores: List[float]
) -> Dict[str, Any]:
    """Process a single subcohort."""
    # Get sample IDs for subcohort
    sample_ids = get_subcohort_sample_ids(subcohort)
    
    # Filter valid samples
    valid_samples = filter_valid_samples(sample_ids, score_dict)
    
    if not valid_samples:
        return None
    
    # Extract scores
    subcohort_scores = [sample["SCORE"] for sample in valid_samples]
    
    # Create table entries with percentiles
    table_entries = create_table_entries(valid_samples, base_scores, subcohort["name"])
    
    return {
        "subcohort_info": {
            "name": subcohort["name"],
            "color": subcohort["color"],
            "values": subcohort_scores
        },
        "table_entries": table_entries
    }

def get_subcohort_sample_ids(subcohort: Dict[str, Any]) -> List[str]:
    """Get sample IDs for a subcohort."""
    if "sample_ids" not in subcohort:
        return db.ancestry.sample_ids_by_cohort(subcohort["name"])
    return subcohort["sample_ids"]

def create_table_entries(
    valid_samples: List[Dict[str, Any]], 
    base_scores: List[float], 
    subcohort_name: str
) -> List[Dict[str, str]]:
    """Create table entries with percentile calculations."""
    table_entries = []
    
    for sample in valid_samples:
        percentile = calculate_percentile(sample["SCORE"], base_scores)
        table_entries.append({
            "SAMPLE_ID": sample["SAMPLE_ID"],
            "SCORE": f"{sample['SCORE']:.4f}",
            "PERCENTILE": f"{percentile:.2f}",
            "SUBCOHORT": subcohort_name
        })
    
    return table_entries

def generate_subcohort_plot(
    base_scores: List[float], 
    subcohort_data: List[Dict[str, Any]], 
    plot_params: Dict[str, Any]
) -> go.Figure:
    """Generate the subcohort comparison plot with optional OR analysis."""
    # Create base figure
    fig = create_base_figure(plot_params["display_or"])
    
    # Configure layout
    configure_plot_layout(fig, plot_params)
    
    # Add visualizations in the correct order for proper layering
    # 1. First add subcohort histograms (background layer)
    add_subcohort_histograms(
        fig, base_scores, subcohort_data, 
        plot_params["bin_size"], plot_params["normalize_bins"]
    )
    
    # 2. Then add base cohort curve (foreground layer)
    add_base_cohort_curve(fig, base_scores, plot_params["base_cohort"])
    
    # 3. Add odds ratio if requested (top layer)
    if plot_params["display_or"] and len(subcohort_data) == 2:
        add_odds_ratio_analysis(fig, subcohort_data, plot_params)
    
    return fig

def create_base_figure(display_or: bool) -> go.Figure:
    """Create the base plotly figure with optional secondary y-axis."""
    return make_subplots(specs=[[{"secondary_y": display_or}]])

def configure_plot_layout(fig: go.Figure, plot_params: Dict[str, Any]) -> None:
    """Configure the plot layout and styling."""
    title = plot_params["plot_title"] or f"Distribution of {plot_params['pgs_id']} - {plot_params['score_type']}"
    
    fig.update_layout(
        title=title,
        xaxis_title="Score",
        yaxis_title="Density" if not plot_params["normalize_bins"] else "Proportion of Samples",
        width=1000,
        height=600,
        margin=dict(l=60, r=160, t=50, b=50),
        legend=dict(x=1.05, y=0.5),
        template="plotly_white",
        # Ensure proper layering
        plot_bgcolor='white',
        # Add grid for better readability
        xaxis=dict(showgrid=True, gridwidth=1, gridcolor='lightgray'),
        yaxis=dict(showgrid=True, gridwidth=1, gridcolor='lightgray')
    )

def add_base_cohort_curve(fig: go.Figure, base_scores: List[float], base_cohort: str) -> None:
    """Add base cohort density curve to the plot."""
    # Calculate KDE
    kde_data = calculate_kde(base_scores)
    
    # Add trace with higher z-order to ensure it's on top
    fig.add_trace(
        go.Scatter(
            x=kde_data["x"],
            y=kde_data["y"],
            mode="lines",
            line=dict(color="#1f77b4", width=3),  # Slightly thicker line for better visibility
            name=f"{base_cohort} ({len(base_scores)} samples, density)",
            # Ensure this trace appears on top
            hovertemplate="<b>%{fullData.name}</b><br>Score: %{x:.4f}<br>Density: %{y:.4f}<extra></extra>"
        )
    )

def calculate_kde(scores: List[float]) -> Dict[str, np.ndarray]:
    """Calculate kernel density estimation."""
    kde_xs = np.linspace(min(scores), max(scores), 1000)
    kde = stats.gaussian_kde(scores)
    kde_ys = kde(kde_xs)
    
    return {"x": kde_xs, "y": kde_ys}

def add_subcohort_histograms(
    fig: go.Figure, 
    base_scores: List[float], 
    subcohort_data: List[Dict[str, Any]], 
    bin_size: int, 
    normalize_bins: bool
) -> None:
    """Add subcohort histograms to the plot."""
    # Calculate bins
    bins = calculate_histogram_bins(base_scores, subcohort_data, bin_size)
    
    # Add histogram for each subcohort
    for subcohort in subcohort_data:
        add_single_histogram(fig, subcohort, bins, normalize_bins)

def calculate_histogram_bins(
    base_scores: List[float], 
    subcohort_data: List[Dict[str, Any]], 
    bin_size: int
) -> np.ndarray:
    """Calculate histogram bins based on all data."""
    all_scores = base_scores.copy()
    for subcohort in subcohort_data:
        all_scores.extend(subcohort["values"])
    
    return np.histogram_bin_edges(all_scores, bins=bin_size)

def add_single_histogram(
    fig: go.Figure, 
    subcohort: Dict[str, Any], 
    bins: np.ndarray, 
    normalize_bins: bool
) -> None:
    """Add a single subcohort histogram to the plot."""
    hist, _ = np.histogram(subcohort["values"], bins=bins)
    
    # Normalize if requested
    if normalize_bins:
        hist = hist / len(subcohort["values"])
    
    # Calculate bin centers
    bin_centers = [(bins[i] + bins[i+1])/2 for i in range(len(bins)-1)]
    
    fig.add_trace(
        go.Bar(
            x=bin_centers,
            y=hist,
            opacity=0.5,  # Reduced opacity for better transparency
            width=bins[1]-bins[0],
            name=f"{subcohort['name']} ({len(subcohort['values'])} samples)",
            marker_color=subcohort["color"],
            marker_line_color="black",
            marker_line_width=0.5,
            # Better hover template
            hovertemplate="<b>%{fullData.name}</b><br>Score: %{x:.4f}<br>Count: %{y}<extra></extra>"
        )
    )

def add_odds_ratio_analysis(
    fig: go.Figure, 
    subcohort_data: List[Dict[str, Any]], 
    plot_params: Dict[str, Any]
) -> None:
    """Add odds ratio analysis to the plot."""
    # Configure secondary y-axis
    configure_or_axis(fig)
    
    # Add reference line
    add_or_reference_line(fig)
    
    # Route to appropriate OR calculation
    or_type = plot_params["or_calculation_type"]
    or_functions = {
        "bin": lambda: add_or_by_bin_cumulative(fig, subcohort_data, plot_params["bin_size"]),
        "quantile": lambda: add_or_by_quantile_cumulative(fig, subcohort_data, plot_params["quantile_count"]),
        "threshold": lambda: add_or_by_threshold(fig, subcohort_data, plot_params["threshold_value"] or 0),
        "decileBaseline": lambda: add_or_by_decile_vs_baseline(fig, subcohort_data, plot_params["decile_count"]),
        "decileCumulative": lambda: add_or_by_decile_vs_cumulative(fig, subcohort_data, plot_params["decile_count"])
    }
    
    if or_type in or_functions:
        or_functions[or_type]()

def configure_or_axis(fig: go.Figure) -> None:
    """Configure the secondary y-axis for odds ratio."""
    fig.update_layout(
        yaxis2=dict(
            title="Odds Ratio",
            side="right",
            type="log",
            overlaying="y",
            showgrid=False
        )
    )

def add_or_reference_line(fig: go.Figure) -> None:
    """Add reference line at OR = 1."""
    fig.add_shape(
        type="line",
        x0=0, x1=1,
        y0=1, y1=1,
        xref="paper",
        yref="y2",
        line=dict(color="black", width=1, dash="dash"),
        opacity=0.6
    )

def add_or_by_bin_cumulative(fig: go.Figure, data: List[Dict[str, Any]], bin_size: int) -> None:
    """Add odds ratio analysis by histogram bin (cumulative)."""
    or_result = calculate_OR_by_bin_cumulative(data, bin_size)
    
    # Extract data
    x_values = [d["x"] for d in or_result["oddsRatios"]]
    or_values = [d["or"] for d in or_result["oddsRatios"]]
    ci_lower = [d["y0"] for d in or_result["confidenceIntervals"]]
    ci_upper = [d["y1"] for d in or_result["confidenceIntervals"]]
    
    # Add OR line
    add_or_line(fig, x_values, or_values, data[0]['name'], data[1]['name'])
    
    # Add confidence interval
    add_confidence_interval(fig, x_values, ci_lower, ci_upper)

def add_or_line(fig: go.Figure, x_values: List[float], or_values: List[float], 
                name1: str, name2: str) -> None:
    """Add odds ratio line to plot."""
    fig.add_trace(
        go.Scatter(
            x=x_values,
            y=or_values,
            mode="lines+markers",  # Add markers for better visibility
            line=dict(color="red", width=3),  # Thicker line
            marker=dict(color="red", size=4),
            name=f"OR: {name1} vs {name2}",
            yaxis="y2",
            # Better hover template
            hovertemplate="<b>OR: %{fullData.name}</b><br>Score: %{x:.4f}<br>OR: %{y:.3f}<extra></extra>"
        )
    )

def add_confidence_interval(fig: go.Figure, x_values: List[float], 
                          ci_lower: List[float], ci_upper: List[float]) -> None:
    """Add confidence interval band to plot."""
    # Add confidence interval as a filled area
    fig.add_trace(
        go.Scatter(
            x=x_values + x_values[::-1],  # x, then x reversed
            y=ci_upper + ci_lower[::-1],  # upper, then lower reversed
            fill='toself',
            fillcolor="rgba(255, 0, 0, 0.15)",  # More transparent
            line=dict(color="rgba(255,255,255,0)"),  # Invisible line
            name="95% CI",
            yaxis="y2",
            showlegend=True,
            hoverinfo='skip'  # Skip hover for CI band
        )
    )

def add_or_by_quantile_cumulative(fig: go.Figure, data: List[Dict[str, Any]], 
                                 quantile_count: int) -> None:
    """Add odds ratio analysis by quantiles (cumulative)."""
    or_result = calculate_OR_by_quantile_cumulative(data, quantile_count)
    
    # Add quantile markers
    add_quantile_markers(fig, or_result["oddsRatios"])
    
    # Add OR points with CI
    add_or_points_with_ci(fig, or_result["oddsRatios"], data[0]['name'], data[1]['name'])

def add_quantile_markers(fig: go.Figure, odds_ratios: List[Dict[str, Any]]) -> None:
    """Add vertical lines at quantile breakpoints."""
    for i, d in enumerate(odds_ratios):
        if i > 0:  # Skip first point
            fig.add_shape(
                type="line",
                x0=d["x"], x1=d["x"],
                y0=0, y1=1,
                yref="paper",
                line=dict(color="#aaa", width=1, dash="dash"),
                opacity=0.4
            )

def add_or_points_with_ci(fig: go.Figure, odds_ratios: List[Dict[str, Any]], 
                         name1: str, name2: str) -> None:
    """Add OR points with confidence intervals."""
    for d in odds_ratios:
        # Add point
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
        
        # Add CI line
        fig.add_shape(
            type="line",
            x0=d["x"], x1=d["x"],
            y0=d["ci95low"], y1=d["ci95high"],
            line=dict(color="red", width=2),
            yref="y2"
        )
    
    # Add legend entries
    add_or_legend_entries(fig, name1, name2)

def add_or_legend_entries(fig: go.Figure, name1: str, name2: str) -> None:
    """Add legend entries for OR visualization."""
    fig.add_trace(
        go.Scatter(
            x=[None], y=[None],
            mode="markers",
            marker=dict(color="red", size=8),
            name=f"OR: {name1} vs {name2}",
            yaxis="y2"
        )
    )
    
    fig.add_trace(
        go.Scatter(
            x=[None], y=[None],
            mode="lines",
            line=dict(color="red", width=2),
            name="95% CI",
            yaxis="y2"
        )
    )

def add_or_by_threshold(fig: go.Figure, data: List[Dict[str, Any]], threshold: float) -> None:
    """Add odds ratio analysis at a specific threshold."""
    or_result = calculate_OR_by_threshold(data, threshold)
    
    # Add threshold line
    add_threshold_line(fig, threshold)
    
    # Add OR point and CI
    add_threshold_or_point(fig, or_result, data[0]['name'], data[1]['name'])

def add_threshold_line(fig: go.Figure, threshold: float) -> None:
    """Add vertical line at threshold."""
    fig.add_shape(
        type="line",
        x0=threshold, x1=threshold,
        y0=0, y1=1,
        yref="paper",
        line=dict(color="blue", width=1, dash="dash"),
        opacity=0.8
    )

def add_threshold_or_point(fig: go.Figure, or_result: Dict[str, float], 
                          name1: str, name2: str) -> None:
    """Add OR point and CI for threshold analysis."""
    # Add point
    fig.add_trace(
        go.Scatter(
            x=[or_result["threshold"]],
            y=[or_result["or"]],
            mode="markers",
            marker=dict(color="red", size=8),
            name=f"OR at {or_result['threshold']:.2f}: {or_result['or']:.2f} ({name1} vs {name2})",
            yaxis="y2"
        )
    )
    
    # Add CI line
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
            x=[None], y=[None],
            mode="lines",
            line=dict(color="red", width=2),
            name=f"95% CI: [{or_result['ci95low']:.2f}, {or_result['ci95high']:.2f}]",
            yaxis="y2"
        )
    )

def add_or_by_decile_vs_baseline(fig: go.Figure, data: List[Dict[str, Any]], 
                                decile_count: int) -> None:
    """Add odds ratio analysis by decile compared to baseline."""
    or_result = calculate_OR_by_decile_vs_baseline(data, decile_count)
    
    # Add decile markers
    add_decile_markers(fig, or_result["decileBreakpoints"])
    
    # Add OR visualization
    add_decile_or_visualization(
        fig, or_result["oddsRatios"], 
        data[0]['name'], data[1]['name'], 
        "red", "OR by Decile vs Baseline"
    )

def add_or_by_decile_vs_cumulative(fig: go.Figure, data: List[Dict[str, Any]], 
                                  decile_count: int) -> None:
    """Add odds ratio analysis by decile vs cumulative lower deciles."""
    or_result = calculate_OR_by_decile_vs_cumulative(data, decile_count)
    
    # Add decile markers
    add_decile_markers(fig, or_result["decileBreakpoints"])
    
    # Add OR visualization
    add_decile_or_visualization(
        fig, or_result["oddsRatios"], 
        data[0]['name'], data[1]['name'], 
        "purple", "OR by Decile vs Cumulative Lower"
    )

def add_decile_markers(fig: go.Figure, breakpoints: List[float]) -> None:
    """Add vertical lines and labels for decile breakpoints."""
    for i, breakpoint in enumerate(breakpoints):
        if i > 0:  # Skip first point
            fig.add_shape(
                type="line",
                x0=breakpoint, x1=breakpoint,
                y0=0, y1=1,
                yref="paper",
                line=dict(color="#aaa", width=1, dash="dash"),
                opacity=0.4
            )
            
            fig.add_annotation(
                x=breakpoint,
                y=0,
                yref="paper",
                text=f"D{i+1}",
                showarrow=False,
                font=dict(size=8),
                yshift=-15
            )

def add_decile_or_visualization(fig: go.Figure, odds_ratios: List[Dict[str, Any]], 
                               name1: str, name2: str, color: str, label: str) -> None:
    """Add decile OR points, CI lines, and connecting line."""
    x_values = []
    or_values = []
    
    # Add points and CI lines
    for d in odds_ratios:
        x_values.append(d["x"])
        or_values.append(d["or"])
        
        # Add point
        fig.add_trace(
            go.Scatter(
                x=[d["x"]],
                y=[d["or"]],
                mode="markers",
                marker=dict(color=color, size=8),
                showlegend=False,
                yaxis="y2"
            )
        )
        
        # Add CI line
        fig.add_shape(
            type="line",
            x0=d["x"], x1=d["x"],
            y0=d["ci95low"], y1=d["ci95high"],
            line=dict(color=color, width=2),
            yref="y2"
        )
    
    # Add connecting line
    fig.add_trace(
        go.Scatter(
            x=x_values,
            y=or_values,
            mode="lines",
            line=dict(color=color, width=1.5, dash="dash"),
            name=f"{label}: {name1} vs {name2}",
            yaxis="y2"
        )
    )
    
    # Add CI to legend
    fig.add_trace(
        go.Scatter(
            x=[None], y=[None],
            mode="lines",
            line=dict(color=color, width=2),
            name="95% CI",
            yaxis="y2"
        )
    )

def save_plot_to_file(fig: go.Figure) -> str:
    """Save the plot to an HTML file."""
    plot_id = str(uuid.uuid4())
    plot_dir = "temp"
    os.makedirs(plot_dir, exist_ok=True)
    plot_path = os.path.join(plot_dir, f"{plot_id}.html")
    
    fig.write_html(plot_path, include_plotlyjs="cdn")
    
    return f"/temp/{plot_id}.html"

# OR calculation functions remain the same as they are pure mathematical functions
def calculate_OR_by_bin_cumulative(data, bin_size):
    """Calculate odds ratio by histogram bin (cumulative)."""
    return perform_or_calculation(
        data, bin_size,
        lambda vals, edges, i: calculate_cumulative_or_at_threshold(data, edges[i])
    )

def perform_or_calculation(data, num_divisions, calculation_func):
    """Generic function to perform OR calculations."""
    all_values = data[0]["values"] + data[1]["values"]
    domain = [min(all_values), max(all_values)]
    
    # Create divisions
    divisions = np.linspace(domain[0], domain[1], num_divisions + 1)
    
    odds_ratios = []
    confidence_intervals = []
    
    for i in range(len(divisions) - 1):
        result = calculation_func(all_values, divisions, i)
        odds_ratios.append(result["or_point"])
        confidence_intervals.append(result["ci_point"])
    
    return {"oddsRatios": odds_ratios, "confidenceIntervals": confidence_intervals}

def calculate_cumulative_or_at_threshold(data, threshold):
    """Calculate OR for values above threshold."""
    a = sum(1 for v in data[0]["values"] if v >= threshold)
    b = len(data[0]["values"]) - a
    c = sum(1 for v in data[1]["values"] if v >= threshold)
    d = len(data[1]["values"]) - c
    
    or_stats = calculate_or_statistics(a, b, c, d)
    
    return {
        "or_point": {
            "x": float(threshold),
            "or": or_stats["or"],
            "ci95low": or_stats["ci95low"],
            "ci95high": or_stats["ci95high"]
        },
        "ci_point": {
            "x": float(threshold),
            "y0": or_stats["ci95low"],
            "y1": or_stats["ci95high"]
        }
    }

def calculate_or_statistics(a, b, c, d):
    """Calculate odds ratio and confidence intervals."""
    epsilon = 0.5
    
    or_value = ((a + epsilon) * (d + epsilon)) / ((b + epsilon) * (c + epsilon))
    
    log_or = np.log(or_value)
    se_log_or = np.sqrt(1/(a + epsilon) + 1/(b + epsilon) + 1/(c + epsilon) + 1/(d + epsilon))
    ci95low = np.exp(log_or - 1.96 * se_log_or)
    ci95high = np.exp(log_or + 1.96 * se_log_or)
    
    return {
        "or": float(or_value),
        "ci95low": float(ci95low),
        "ci95high": float(ci95high)
    }

def calculate_OR_by_quantile_cumulative(data, num_quantiles):
    """Calculate odds ratio by quantiles (cumulative)."""
    all_values = data[0]["values"] + data[1]["values"]
    quantile_breaks = [np.quantile(all_values, i / num_quantiles) for i in range(1, num_quantiles)]
    
    # Add min value at start
    min_value = min(all_values)
    
    odds_ratios = []
    confidence_intervals = []
    
    # Start with minimum value
    result = calculate_cumulative_or_at_threshold(data, min_value)
    odds_ratios.append(result["or_point"])
    confidence_intervals.append(result["ci_point"])
    
    # Add quantile thresholds
    for threshold in quantile_breaks:
        result = calculate_cumulative_or_at_threshold(data, threshold)
        odds_ratios.append(result["or_point"])
        confidence_intervals.append(result["ci_point"])
    
    return {"oddsRatios": odds_ratios, "confidenceIntervals": confidence_intervals}

def calculate_OR_by_threshold(data, threshold):
    """Calculate odds ratio at a specific threshold."""
    result = calculate_cumulative_or_at_threshold(data, threshold)
    
    return {
        "threshold": float(threshold),
        "or": result["or_point"]["or"],
        "ci95low": result["or_point"]["ci95low"],
        "ci95high": result["or_point"]["ci95high"]
    }

def calculate_OR_by_decile_vs_baseline(data, num_deciles=10):
    """Calculate odds ratio by decile compared to baseline (1st decile)."""
    # Get decile assignments
    decile_data = assign_to_deciles(data, num_deciles)
    
    # Calculate baseline odds
    baseline_cases = decile_data["cases_by_decile"][0]
    baseline_ctrls = decile_data["ctrls_by_decile"][0]
    
    # Calculate OR for each decile
    odds_ratios = []
    confidence_intervals = []
    
    for i in range(num_deciles):
        a = decile_data["cases_by_decile"][i]
        b = decile_data["ctrls_by_decile"][i]
        c = baseline_cases
        d = baseline_ctrls
        
        or_stats = calculate_or_statistics(a, b, c, d)
        
        odds_ratios.append({
            "decile": i + 1,
            "x": float(decile_data["breakpoints"][i]),
            "or": or_stats["or"],
            "ci95low": or_stats["ci95low"],
            "ci95high": or_stats["ci95high"],
            "caseCount": int(a),
            "ctrlCount": int(b)
        })
        
        confidence_intervals.append({
            "decile": i + 1,
            "x": float(decile_data["breakpoints"][i]),
            "y0": or_stats["ci95low"],
            "y1": or_stats["ci95high"]
        })
    
    return {
        "oddsRatios": odds_ratios,
        "confidenceIntervals": confidence_intervals,
        "decileBreakpoints": [float(bp) for bp in decile_data["breakpoints"]]
    }

def calculate_OR_by_decile_vs_cumulative(data, num_deciles=10):
    """Calculate odds ratio by decile compared to all lower deciles combined."""
    # Get decile assignments
    decile_data = assign_to_deciles(data, num_deciles)
    
    odds_ratios = []
    confidence_intervals = []
    
    # First decile has no lower deciles
    odds_ratios.append({
        "decile": 1,
        "x": float(decile_data["breakpoints"][0]),
        "or": 1.0,
        "ci95low": 1.0,
        "ci95high": 1.0,
        "caseCount": int(decile_data["cases_by_decile"][0]),
        "ctrlCount": int(decile_data["ctrls_by_decile"][0])
    })
    
    confidence_intervals.append({
        "decile": 1,
        "x": float(decile_data["breakpoints"][0]),
        "y0": 1.0,
        "y1": 1.0
    })
    
    # For remaining deciles
    for i in range(1, num_deciles):
        a = decile_data["cases_by_decile"][i]
        b = decile_data["ctrls_by_decile"][i]
        c = sum(decile_data["cases_by_decile"][:i])
        d = sum(decile_data["ctrls_by_decile"][:i])
        
        or_stats = calculate_or_statistics(a, b, c, d)
        
        odds_ratios.append({
            "decile": i + 1,
            "x": float(decile_data["breakpoints"][i]),
            "or": or_stats["or"],
            "ci95low": or_stats["ci95low"],
            "ci95high": or_stats["ci95high"],
            "caseCount": int(a),
            "ctrlCount": int(b),
            "lowerCaseCount": int(c),
            "lowerCtrlCount": int(d)
        })
        
        confidence_intervals.append({
            "decile": i + 1,
            "x": float(decile_data["breakpoints"][i]),
            "y0": or_stats["ci95low"],
            "y1": or_stats["ci95high"]
        })
    
    return {
        "oddsRatios": odds_ratios,
        "confidenceIntervals": confidence_intervals,
        "decileBreakpoints": [float(bp) for bp in decile_data["breakpoints"]]
    }

def assign_to_deciles(data, num_deciles):
    """Assign values to deciles and count by group."""
    # Combine and sort all values
    all_values = data[0]["values"] + data[1]["values"]
    all_values.sort()
    
    # Calculate decile breakpoints
    decile_breakpoints = [np.quantile(all_values, i / num_deciles) for i in range(num_deciles + 1)]
    
    # Initialize counts
    cases_by_decile = [0] * num_deciles
    ctrls_by_decile = [0] * num_deciles
    
    # Assign to deciles
    for value in data[0]["values"]:
        decile_idx = get_decile_index(value, decile_breakpoints)
        cases_by_decile[decile_idx] += 1
    
    for value in data[1]["values"]:
        decile_idx = get_decile_index(value, decile_breakpoints)
        ctrls_by_decile[decile_idx] += 1
    
    return {
        "cases_by_decile": cases_by_decile,
        "ctrls_by_decile": ctrls_by_decile,
        "breakpoints": decile_breakpoints
    }

def get_decile_index(value, breakpoints):
    """Get the decile index for a value."""
    for i in range(1, len(breakpoints)):
        if value < breakpoints[i]:
            return i - 1
    return len(breakpoints) - 2  # Last decile

def calculate_percentile(value: float, array: List[float]) -> float:
    """Calculate the percentile of a value in an array."""
    sorted_array = sorted(array)
    position = next((i for i, x in enumerate(sorted_array) if x >= value), len(sorted_array))
    
    if position == len(sorted_array):
        return 100.0  # Value is greater than all elements
    
    return (position / len(sorted_array) * 100)