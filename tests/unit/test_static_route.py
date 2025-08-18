import os
from src.config import app
import src.routes.static  # ensure routes are registered


def test_static_subdirectory_serving(tmp_path):
    client = app.test_client()
    # Ensure subdirectory file exists
    sub_dir = os.path.join(app.static_folder, 'sub')
    os.makedirs(sub_dir, exist_ok=True)
    file_path = os.path.join(sub_dir, 'hello.txt')
    with open(file_path, 'w') as f:
        f.write('hello world')

    resp = client.get('/sub/hello.txt')
    assert resp.status_code == 200
    assert resp.data.decode().strip() == 'hello world'

def test_serve_dashboard():
    client = app.test_client()
    resp = client.get('/dashboard')
    assert resp.status_code == 200
    assert b'Host Dashboard' in resp.data

def test_serve_about():
    client = app.test_client()
    resp = client.get('/about')
    assert resp.status_code == 200
    assert b'url=https://github.com/TonyXTYan/CHSH-Game' in resp.data

def test_serve_index():
    client = app.test_client()
    resp = client.get('/index')
    assert resp.status_code == 200
    assert b'CHSH Game' in resp.data

def test_serve_fallback_to_index():
    client = app.test_client()
    resp = client.get('/nonexistentfile.txt')
    assert resp.status_code == 200
    assert b'CHSH Game' in resp.data

def test_serve_forbidden_traversal():
    client = app.test_client()
    resp = client.get('/../secret.txt')
    assert resp.status_code == 403

def test_serve_missing_index_returns_404(tmp_path, monkeypatch):
    client = app.test_client()
    # Temporarily point static folder to empty temp dir without index.html
    original = app.static_folder
    try:
        os.makedirs(tmp_path, exist_ok=True)
        monkeypatch.setattr(app, 'static_folder', str(tmp_path))
        resp = client.get('/nonexistent')
        assert resp.status_code == 404
        assert b'index.html not found' in resp.data
    finally:
        monkeypatch.setattr(app, 'static_folder', original)

def test_get_server_id():
    client = app.test_client()
    resp = client.get('/api/server/id')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'instance_id' in data
