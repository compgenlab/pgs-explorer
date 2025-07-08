import os
import json

def process_search(request_data: Dict[str, Any]) -> str:
    try:
        existing, html_path, json_path = generate_request_hash(request_data)
        if existing:
            return f"/{html_path}"
    except Exception as e:
        print(f"Error in process_search: {str(e)}")
        import traceback
        traceback.print_exc()
        raise e
