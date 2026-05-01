import pytest
from src.config import app

@pytest.fixture
def test_client():
    return app.test_client()

def test_get_server_id(test_client):
    """Test that /api/server/id endpoint returns valid instance ID"""
    # Make GET request to endpoint
    response = test_client.get('/api/server/id')
    
    # Assert response status code is 200
    assert response.status_code == 200
    
    # Assert response is JSON
    json_data = response.get_json()
    assert json_data is not None
    
    # Assert instance_id exists and is non-empty string
    assert 'instance_id' in json_data
    assert isinstance(json_data['instance_id'], str)
    assert len(json_data['instance_id']) > 0