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
    
    # Prevent path traversal attacks by ensuring the resolved path is within the static folder
    requested_path = os.path.abspath(os.path.join(static_folder_path, path))
    if not requested_path.startswith(os.path.abspath(static_folder_path)):
        abort(403)  # Forbidden - attempt to access outside of static folder
    
    # Check if the file exists
    if path != "" and os.path.exists(requested_path) and os.path.isfile(requested_path):
        # Use safe send_from_directory which handles paths securely
        return send_from_directory(static_folder_path, path)
    else:
        index_path = os.path.join(static_folder_path, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, 'index.html')
        else:
            return "index.html not found", 404
