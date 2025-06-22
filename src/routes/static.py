import os
import uuid
from flask import send_from_directory, abort, jsonify
from src.config import app
from pathlib import Path

# Unique ID for server instance
server_instance_id = str(uuid.uuid4())

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    static_folder_path = app.static_folder
    
    # Handle root path explicitly
    if path == "":
        return send_from_directory(static_folder_path, 'index.html')
        
    # Handle specific routes
    if path == "dashboard":
        return send_from_directory(static_folder_path, 'dashboard.html')
    if path == "about":
        return send_from_directory(static_folder_path, 'about.html')
    if path == "index":
        return send_from_directory(static_folder_path, 'index.html')
    
    # Normalize the path to prevent path traversal attacks
    normalized_path = os.path.normpath(path)
    
    # Ensure the normalized path does not contain any ".." segments
    if ".." in normalized_path.split(os.sep):
        abort(403)  # Forbidden - attempt to traverse directories
    
    # Sanitize each path component to avoid directory traversal while still
    # allowing subdirectories (secure_filename strips path separators)
    from werkzeug.utils import secure_filename
    safe_parts = [secure_filename(part) for part in normalized_path.split(os.sep)
                  if part not in ("", ".")]
    safe_path = os.path.join(*safe_parts)
    
    # Resolve the full requested path
    requested_path = os.path.realpath(os.path.join(static_folder_path, safe_path))
    static_folder_realpath = os.path.realpath(static_folder_path)
    if not requested_path.startswith(static_folder_realpath + os.sep) and path != "":
        abort(403)  # Forbidden - attempt to access outside of static folder
    
    # Check if the file exists
    if os.path.exists(requested_path) and os.path.isfile(requested_path):
        # Use safe send_from_directory which handles paths securely
        return send_from_directory(static_folder_path, safe_path)
    else:
        # If the file doesn't exist, serve index.html as fallback
        index_path = os.path.join(static_folder_path, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, 'index.html')
        else:
            return "index.html not found", 404

@app.route('/api/server/id')
def get_server_id():
    """Return the unique server instance ID"""
    return jsonify({'instance_id': server_instance_id})
