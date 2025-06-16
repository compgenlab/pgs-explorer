from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import yaml
import os

def create_app():
    """Create and configure the FastAPI application"""
    app = FastAPI(title="PGS Visualizer", description="Tool for visualizing Polygenic Score data")
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allows all origins
        allow_credentials=True,
        allow_methods=["*"],  # Allows all methods (GET, POST, etc.)
        allow_headers=["*"],  # Allows all headers
    )
    
    # Setup static files
    app.mount("/static", StaticFiles(directory="static"), name="static")
    app.mount("/temp", StaticFiles(directory="temp"), name="temp")
    
    return app

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
    with open(config_path, 'r') as file:
        return yaml.safe_load(file)

# Create templates object that can be imported by routers
templates = Jinja2Templates(directory="templates")

# Easy access vars 
config = load_config()

DB_PATH = config['database']['pgs_db_path']
TASK_DB_PATH = config['database']['tasks_db_path']
SESSION_SECRET_KEY = config['session']['secret_key']
SESSION_COOKIE_NAME = config['session']['cookie_name']
SESSION_MAX_AGE = config['session']['max_age']
