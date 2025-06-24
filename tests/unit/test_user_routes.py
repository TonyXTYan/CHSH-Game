"""
NOTE: This test file is currently written as a unit test, but due to the app/db coupling in the project and the integration server setup in tests/conftest.py, these tests should be moved to tests/integration/ and rewritten as integration tests.

- Now rewritten to use the running integration server (http://localhost:8080) and the requests library.
- The integration server is started automatically for tests in tests/integration/.
- This will ensure proper coverage and avoid Flask/SQLAlchemy context issues.
"""
import requests
import pytest

BASE_URL = "http://localhost:8080"

@pytest.mark.integration
def test_create_user():
    response = requests.post(f"{BASE_URL}/users", json={
        'username': 'alice',
        'email': 'alice@example.com'
    })
    assert response.status_code == 201
    data = response.json()
    assert data['username'] == 'alice'
    assert data['email'] == 'alice@example.com'

@pytest.mark.integration
def test_get_users():
    # Create a user to ensure at least one exists
    requests.post(f"{BASE_URL}/users", json={
        'username': 'bob',
        'email': 'bob@example.com'
    })
    response = requests.get(f"{BASE_URL}/users")
    assert response.status_code == 200
    data = response.json()
    assert any(u['username'] == 'bob' for u in data)

@pytest.mark.integration
def test_get_user():
    # Create a user and get its ID
    create_resp = requests.post(f"{BASE_URL}/users", json={
        'username': 'carol',
        'email': 'carol@example.com'
    })
    user_id = create_resp.json()['id']
    response = requests.get(f"{BASE_URL}/users/{user_id}")
    assert response.status_code == 200
    data = response.json()
    assert data['username'] == 'carol'

@pytest.mark.integration
def test_update_user():
    # Create a user and get its ID
    create_resp = requests.post(f"{BASE_URL}/users", json={
        'username': 'dave',
        'email': 'dave@example.com'
    })
    user_id = create_resp.json()['id']
    response = requests.put(f"{BASE_URL}/users/{user_id}", json={'username': 'dave2'})
    assert response.status_code == 200
    data = response.json()
    assert data['username'] == 'dave2'

@pytest.mark.integration
def test_delete_user():
    # Create a user and get its ID
    create_resp = requests.post(f"{BASE_URL}/users", json={
        'username': 'eve',
        'email': 'eve@example.com'
    })
    user_id = create_resp.json()['id']
    response = requests.delete(f"{BASE_URL}/users/{user_id}")
    assert response.status_code == 204
    # Confirm user is deleted
    get_resp = requests.get(f"{BASE_URL}/users/{user_id}")
    assert get_resp.status_code == 404 