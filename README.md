# PGS Visualizer

An interactive web application for visualizing and exploring Polygenic Score (PGS) data.

## Features

- **Heatmap Visualization**: Generate interactive heatmaps with hierarchical clustering to visualize patterns across PGS IDs and samples
- **Distribution Analysis**: Compare score distributions across different cohorts or PGS IDs
- **Metadata Explorer**: Browse detailed metadata for each PGS ID
- **Interactive UI**: User-friendly interface with form-based configuration
- **Export Options**: Download visualizations as PNG or HTML files

## Installation

### Prerequisites

- Python 3.8+
- SQLite database with PGS data 

### Setup

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/pgs-visualizer.git
   cd pgs-visualizer
   ```

2. Create a virtual environment and activate it:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Create the required directories:
   ```
   mkdir -p db static/css static/js templates
   ```


## Directory Structure

```
pgs-visualizer/
├── db/                    # Directory for SQLite database
├── data/                  # Data directory for input files
│   ├── pgs/               # PGS metadata files
│   └── samples/           # Sample score files
├── static/                # Static files
│   ├── css/               # CSS files
│   └── js/                # JavaScript files
├── templates/             # HTML templates
│   ├── base.html          # Base template
│   ├── index.html         # Home page
│   ├── heatmap.html       # Heatmap page
│   ├── distribution.html  # Distribution page
│   └── metadata.html      # Metadata page
├── app.py                 # FastAPI application
└── requirements.txt       # Python dependencies
```

## Running the Application

1. Start the application:
   ```
   uvicorn app:app --host 0.0.0.0 --port 5000
   ```

## Data Requirements

The application expects a SQLite database with the following tables:

1. `pgs_metadata` - Contains information about each PGS ID
2. `scores` - Contains score data in a long format (PGS_ID, SCORE_TYPE, SAMPLE_ID, SCORE)

The initialization script will create these tables if the database doesn't exist.

## API Endpoints

The application provides the following API endpoints:

### Metadata
- `GET /api/metadata/{pgs_id}` - Get metadata for a specific PGS ID
- `GET /api/pgs_list` - Get a list of all available PGS IDs

### Scores
- `GET /api/score_types` - Get a list of all available score types
- `GET /api/score_types/{pgs_id}` - Get score types available for a specific PGS ID
- `GET /api/pgs_data/{pgs_id}` - Get scores for a specific PGS ID

### Heatmap
- `POST /api/generate_heatmap` - Generate a heatmap based on specified parameters

## Acknowledgments

- [Plotly](https://plotly.com/python/) for interactive visualizations
- [FastAPI](https://fastapi.tiangolo.com/) for the web framework
- [Bootstrap](https://getbootstrap.com/) for the frontend design