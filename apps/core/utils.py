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

def cleanup_temp_files(max_size_in_gb=10):
    """
    Cleans up temporary heatmap files when the directory exceeds the specified size limit.
    
    Args:
        max_size_in_gb: Maximum allowed size of the temp directory in GB
    """
    temp_dir = "temp"
    max_size_in_bytes = max_size_in_gb * 1024 * 1024 * 1024
    
    # Check if the directory exists
    if not os.path.exists(temp_dir):
        return
    
    # Get all HTML files in the temp directory with their stats
    files = []
    total_size = 0
    
    for filename in os.listdir(temp_dir):
        if filename.endswith(".html"):
            filepath = os.path.join(temp_dir, filename)
            file_stats = os.stat(filepath)
            file_size = file_stats.st_size
            access_time = file_stats.st_atime  # Last access time
            
            files.append({
                "path": filepath,
                "size": file_size,
                "last_accessed": access_time
            })
            
            total_size += file_size
    
    print(f"Current temp directory size: {total_size / (1024 * 1024):.2f} MB")
    
    # If we're under the limit, do nothing
    if total_size <= max_size_in_bytes:
        return
    
    print(f"Temp directory size ({total_size / (1024 * 1024 * 1024):.2f} GB) exceeds limit of {max_size_in_gb} GB")
    
    # Sort files by last access time (oldest first)
    files.sort(key=lambda x: x["last_accessed"])
    
    # Remove files until we're under the limit
    deleted_count = 0
    freed_space = 0
    
    while total_size > max_size_in_bytes and files:
        file_to_remove = files.pop(0)  # Get the oldest file
        
        try:
            os.remove(file_to_remove["path"])
            freed_space += file_to_remove["size"]
            total_size -= file_to_remove["size"]
            deleted_count += 1
            print(f"Deleted: {os.path.basename(file_to_remove['path'])}")
        except Exception as e:
            print(f"Error deleting {file_to_remove['path']}: {e}")
    
    print(f"Cleanup complete: Deleted {deleted_count} files, freed {freed_space / (1024 * 1024):.2f} MB")
