from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

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

# Create templates object that can be imported by routers
templates = Jinja2Templates(directory="templates")