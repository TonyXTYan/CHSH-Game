import os
from flask import send_from_directory
from src.config import app

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    static_folder_path = app.static_folder
    if path == "dashboard": # Specific route for dashboard
        return send_from_directory(static_folder_path, 'dashboard.html')
    if path == "about": # Specific route for about.html
        return send_from_directory(static_folder_path, 'about.html')
    if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
        return send_from_directory(static_folder_path, path)
    else:
        index_path = os.path.join(static_folder_path, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, 'index.html')
        else:
            return "index.html not found", 404
