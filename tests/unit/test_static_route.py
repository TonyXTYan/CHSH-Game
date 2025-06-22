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
