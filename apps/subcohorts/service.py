import os
import json
import uuid
import sqlite3
import numpy as np
from scipy import stats
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from apps.core.database import DB_PATH

def process_subcohort_plot(request_data):
    try:
        # Extract parameters from request_data
        pgs_id = request_data["pgs_id"]
        score_type = request_data["score_type"]
        base_cohort = request_data["base_cohort"]
        subcohorts = request_data["subcohorts"]
        plot_title = request_data.get("plot_title", "")
        display_or = request_data.get("display_or", False)
        normalize_bins = request_data.get("normalize_bins", False)
        bin_size = request_data.get("bin_size")
        or_calculation_type = request_data.get("or_calculation_type")
        threshold_value = request_data.get("threshold_value")
        quantile_count = request_data.get("quantile_count")
        decile_count = request_data.get("decile_count")
        
        # Connect to the database
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor() 
        
        try:
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
            
            # Get base cohort sample IDs from ancestry groups
            if base_cohort != "ALL":
                cursor.execute("SELECT sample_ids FROM ancestry_groups WHERE population = ?", (base_cohort,))
            else: 
                cursor.execute("SELECT sample_ids FROM ancestry_groups")
            cohort_result = cursor.fetchone()

            if not cohort_result:
                raise ValueError(f"Base cohort '{base_cohort}' not found in database")

            # Parse the JSON array of sample IDs
            base_sample_ids = json.loads(cohort_result[0])

            # Filter to include only samples that exist in our data
            base_valid_samples = [
                {"SAMPLE_ID": sample_id, "SCORE": score_dict[sample_id]}
                for sample_id in base_sample_ids
                if sample_id in score_dict
            ]
            
            base_scores = [sample["SCORE"] for sample in base_valid_samples]
            
            # Process subcohorts
            subcohort_data = []
            table_data = []
            
            for subcohort in subcohorts:
                if not subcohort.get("active", True):
                    continue
                    
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
        finally:
            conn.close()
        
        # Generate plot using Plotly
        fig = make_subplots(specs=[[{"secondary_y": display_or}]])
        
        # Set plot dimensions
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
        kde_xs = np.linspace(min(base_scores), max(base_scores), 1000)
        kde = stats.gaussian_kde(base_scores)
        kde_ys = kde(kde_xs)
        
        fig.add_trace(
            go.Scatter(
                x=kde_xs,
                y=kde_ys,
                mode="lines",
                line=dict(color="#1f77b4", width=2),
                name=f"{base_cohort} ({len(base_scores)} samples, density)"
            )
        )
        
        # Calculate histogram bins
        bin_size_value = bin_size or 30
        bins = np.histogram_bin_edges(
            np.concatenate([base_scores] + [sc["values"] for sc in subcohort_data]),
            bins=bin_size_value
        )
        
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
        
        # Add odds ratio calculation if requested
        if display_or and len(subcohort_data) == 2:
            data = subcohort_data  # Just using the values and names
            
            if or_calculation_type == "bin":
                # Calculate OR by bin (cumulative)
                or_result = calculate_OR_by_bin_cumulative(data, bin_size)
                
                # Add OR line and CI area
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
                
            elif or_calculation_type == "quantile":
                # Calculate OR by quantile (cumulative)
                quantile_count = quantile_count or 10
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
                
            elif or_calculation_type == "threshold":
                # Calculate OR by threshold
                threshold = threshold_value or 0
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
                
            elif or_calculation_type == "decileBaseline":
                # Calculate OR by decile vs baseline
                decile_count = decile_count or 10
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
                
            elif or_calculation_type == "decileCumulative":
                # Calculate OR by decile vs cumulative lower deciles
                decile_count = decile_count or 10
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
    
        # Save plot to file
        plot_id = str(uuid.uuid4())
        plot_dir = "temp"
        os.makedirs(plot_dir, exist_ok=True)
        plot_path = os.path.join(plot_dir, f"{plot_id}.html")
        
        fig.write_html(plot_path, include_plotlyjs="cdn")
        
        # Return the file path
        return f"/temp/{plot_id}.html"
        
    except Exception as e:
        # Log the error
        print(f"Error generating subcohort plot: {str(e)}")
        raise e


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
