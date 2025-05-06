import os
import json 
import hashlib

def generate_request_hash(request_data, request_type=None):
    """
    TODO
    """
    os.makedirs("temp", exist_ok=True)

    data_with_type = request_data.copy()
    data_with_type['_request_type'] = request_type
    request_json = json.dumps(data_with_type, sort_keys=True)

    request_hash = hashlib.md5(request_json.encode()).hexdigest()
    existing_file_html = check_existing_files(request_hash)

    if existing_file_html:
        return True, existing_file_html, None

    html_path = f"temp/{request_hash}.html"
    json_path = f"temp/{request_hash}.json"

    return False, html_path, json_path

def check_existing_files(request_hash):
    # Check if we already have a file with this hash
    for filename in os.listdir("temp"):
        if filename.endswith(".html") == f"{request_hash}":
            # Found a cached file, update its access time
            cached_filepath = os.path.join("temp", filename)
            os.utime(cached_filepath)
            
            print(f"Using cached request: {filename}")
            
            # Return file path with empty statistics
            return True
    
    return None