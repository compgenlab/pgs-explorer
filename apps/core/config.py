from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import yaml
import os
import sys

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
    config_path = os.path.join(os.path.dirname(__file__), "..", "..", 'config.yaml')
    if not os.path.exists(config_path):
        sys.stderr.write("ERROR: Missing config file: config.yaml!!!\n\n")
        sys.exit(1)

    with open(config_path, 'r') as file:
        cfg = yaml.safe_load(file)
        if not 'database' in cfg:
            cfg['database'] = {}
        
        if not 'db_path' in cfg['database']:
            cfg['database']['db_path'] = ""
        if not 'pgs_db_path' in cfg['database']:
            cfg['database']['pgs_db_path'] = ""
        if not 'tasks_db_path' in cfg['database']:
            cfg['database']['tasks_db_path'] = ""

        return cfg

def update_config_env(config):
    if 'PGS_DB_PATH' in os.environ:
        config['database']['pgs_db_path'] = os.environ['PGS_DB_PATH']
    if 'TASKS_DB_PATH' in os.environ:
        config['database']['tasks_db_path'] = os.environ['TASKS_DB_PATH']
    if 'DB_PATH' in os.environ:
        config['database']['db_path'] = os.environ['DB_PATH']
    if 'SESSION_SECRET_KEY' in os.environ:
        config['session']['secret_key'] = os.environ['SESSION_SECRET_KEY']

    return config

# Create templates object that can be imported by routers
templates = Jinja2Templates(directory="templates")

# Easy access vars 
config = update_config_env(load_config())

PGS_DB_PATH = config['database']['pgs_db_path']
TASK_DB_PATH = config['database']['tasks_db_path']
DB_PATH = config['database']['db_path']

SESSION_SECRET_KEY = config['session']['secret_key']
SESSION_COOKIE_NAME = config['session']['cookie_name']
SESSION_MAX_AGE = config['session']['max_age']
