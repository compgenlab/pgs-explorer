#!/usr/bin/env python
"""
Setup script for PGS Visualizer
This script creates the necessary directory structure and files
"""

import os
import shutil
import sys

def create_directory(path):
    """Create directory if it doesn't exist"""
    if not os.path.exists(path):
        os.makedirs(path)
        print(f"Created directory: {path}")
    else:
        print(f"Directory already exists: {path}")

def create_file(path, content):
    """Create file with given content"""
    with open(path, 'w') as f:
        f.write(content)
    print(f"Created file: {path}")

def main():
    """Main setup function"""
    print("Setting up PGS Visualizer application...")
    
    # Create directory structure
    create_directory("db")
    create_directory("data/pgs")
    create_directory("data/samples")
    create_directory("static/css")
    create_directory("static/js")
    create_directory("templates")
    create_directory("cohorts")
    
    # Copy template files
    print("\nSetting up template and static files...")
    
    # Check if files exist in the current directory
    required_files = [
        "app.py",
        "requirements.txt",
        "README.md",
        "templates/base.html",
        "templates/index.html",
        "templates/heatmap.html",
        "templates/distribution.html",
        "templates/metadata.html",
        "static/css/styles.css",
        "static/js/main.js"
    ]
    
    missing_files = [f for f in required_files if not os.path.exists(f)]
    
    if missing_files:
        print("The following files are missing:")
        for f in missing_files:
            print(f"  - {f}")
        print("\nPlease make sure all required files are in the appropriate directories.")
    else:
        print("All required files found!")
    
    # Create sample cohort files
    print("\nCreating sample cohort files...")
    
    sample_cohort = """sample1
sample2
sample3
sample4
sample5
"""
    
    create_file("cohorts/example_cohort.txt", sample_cohort)
    
    # Final instructions
    print("\nSetup complete!")
    print("\nTo run the application:")
    print("1. Install dependencies: pip install -r requirements.txt")
    print("2. Start the server: uvicorn app:app --reload")
    print("3. Open http://127.0.0.1:8000 in your browser")
    
    print("\nNote: You'll need to add your PGS data to the database before using the application.")
    print("The initialization script in app.py will create the database schema when you first run the application.")

if __name__ == "__main__":
    main()