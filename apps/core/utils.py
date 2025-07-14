import os
import json 
import hashlib

def generate_request_hash(request_data, request_type=None):
    """Generate a hash for request data."""
    data_with_type = request_data.copy()
    if request_type:
        data_with_type['_request_type'] = request_type
    
    request_json = json.dumps(data_with_type, sort_keys=True)
    return hashlib.md5(request_json.encode()).hexdigest()

def check_cache(request_hash, request_type=None):
    """Check if a cached file exists."""
    os.makedirs("temp", exist_ok=True)
    
    for filename in os.listdir("temp"):
        if not filename.endswith(".html"):
            continue
            
        if request_hash not in filename:
            continue
            
        if request_type and request_type not in filename:
            continue
            
        # Update access time
        cached_filepath = os.path.join("temp", filename)
        os.utime(cached_filepath)
        print(f"Using cached {request_type or 'file'}: {filename}")
        return f"/temp/{filename}"
    
    return None

def get_cache_paths(request_hash, request_type=None):
    """Generate file paths for caching."""
    os.makedirs("temp", exist_ok=True)
    
    if request_type:
        html_path = f"temp/{request_hash}_{request_type}.html"
        json_path = f"temp/{request_hash}_{request_type}.json"
    else:
        html_path = f"temp/{request_hash}.html"
        json_path = f"temp/{request_hash}.json"
    
    return html_path, json_path

def process_cache_request(request_data, request_type=None):
    """
    Complete cache processing: generate hash, check cache, return paths.
    
    Returns:
        (cache_hit, file_path, json_path)
        - If cache_hit is True: file_path is cached file, json_path is None
        - If cache_hit is False: file_path and json_path are paths to create
    """
    request_hash = generate_request_hash(request_data, request_type)
    
    # Check for existing cache
    cached_file = check_cache(request_hash, request_type)
    if cached_file:
        return True, cached_file, None
    
    # Generate new paths
    html_path, json_path = get_cache_paths(request_hash, request_type)
    return False, html_path, json_path
def generate_score_hover_texts(pgs_ids, pgs_metadata):
    """Create hover text for PGS score points."""
    hover_text = []

    for pgs_id in pgs_ids:
        meta = pgs_metadata.get(pgs_id, {})
        if not meta: 
            print(f"Missing metadata for {pgs_id}.")

        hover_info: (
            f"PGS ID: {pgs_id}<br>"
            f"Name: {meta.get('PGS_Name', 'N/A')}<br>"
            f"Trait: {meta.get('Reported_Trait', 'N/A')}<br>"
            f"PMID: {meta.get('Publication_PMID', 'N/A')}<br>"
            f"DOI: {meta.get('Publication_DOI', 'N/A')}<br>"
        )