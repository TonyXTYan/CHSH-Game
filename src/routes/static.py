import os
from flask import send_from_directory, abort
from src.config import app
from pathlib import Path

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    static_folder_path = app.static_folder
    if path == "dashboard": # Specific route for dashboard
        return send_from_directory(static_folder_path, 'dashboard.html')
    if path == "about": # Specific route for about.html
        return send_from_directory(static_folder_path, 'about.html')
    
    # Normalize the path to prevent path traversal attacks
    normalized_path = os.path.normpath(path)
    
    # Ensure the normalized path does not contain any ".." segments
    if ".." in normalized_path.split(os.sep):
        abort(403)  # Forbidden - attempt to traverse directories
    
    # Sanitize the file name to remove special characters
    from werkzeug.utils import secure_filename
    safe_path = secure_filename(normalized_path)
    
    # Resolve the full requested path
    requested_path = os.path.realpath(os.path.join(static_folder_path, safe_path))
    static_folder_realpath = os.path.realpath(static_folder_path)
    if not requested_path.startswith(static_folder_realpath + os.sep):
        abort(403)  # Forbidden - attempt to access outside of static folder
    
    # Check if the file exists
    if safe_path != "" and os.path.exists(requested_path) and os.path.isfile(requested_path):
        # Use safe send_from_directory which handles paths securely
        return send_from_directory(static_folder_path, safe_path)
    else:
        index_path = os.path.join(static_folder_path, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, 'index.html')
        else:
            return "index.html not found", 404
