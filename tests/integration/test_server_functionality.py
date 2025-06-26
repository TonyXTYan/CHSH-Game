#!/usr/bin/env python3
"""
Integration tests for Flask server functionality.
Tests that the server is working correctly after startup - pages load, 
elements are present, API endpoints work, etc.
"""

import pytest
import requests
import json
import time
from bs4 import BeautifulSoup


@pytest.mark.integration
class TestServerFunctionality:
    """Test class for server functionality after startup"""
    
    BASE_URL = "http://localhost:8080"
    
    def test_server_is_running(self):
        """Test that the server is accessible and responding"""
        response = requests.get(self.BASE_URL, timeout=10)
        assert response.status_code == 200, f"Server not responding: {response.status_code}"
    
    def test_main_page_loads(self):
        """Test that the main page (index.html) loads correctly"""
        response = requests.get(self.BASE_URL, timeout=10)
        assert response.status_code == 200
        assert "text/html" in response.headers.get("Content-Type", "")
        
        # Parse HTML content
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Check page title
        title = soup.find('title')
        assert title is not None, "Page title not found"
        assert "CHSH Game - Participant" in title.get_text()
        
        # Check main heading
        header = soup.find('h1', id='gameHeader')
        assert header is not None, "Main header not found"
        assert "CHSH Game" in header.get_text()
    
    def test_main_page_key_elements(self):
        """Test that key elements are present on the main page"""
        response = requests.get(self.BASE_URL, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Test team creation section
        create_team_btn = soup.find('button', id='createTeamBtn')
        assert create_team_btn is not None, "Create team button not found"
        assert "Create Team" in create_team_btn.get_text()
        
        team_name_input = soup.find('input', id='teamNameInput')
        assert team_name_input is not None, "Team name input not found"
        assert team_name_input.get('placeholder') == "Enter Team Name"
        
        # Test question section (should be hidden initially)
        question_section = soup.find('div', id='questionSection')
        assert question_section is not None, "Question section not found"
        assert 'hidden' in question_section.get('class', [])
        
        # Test answer buttons
        true_btn = soup.find('button', id='trueBtn')
        false_btn = soup.find('button', id='falseBtn')
        assert true_btn is not None, "True button not found"
        assert false_btn is not None, "False button not found"
        assert "True" in true_btn.get_text()
        assert "False" in false_btn.get_text()
        
        # Test status message
        status_message = soup.find('div', id='statusMessage')
        assert status_message is not None, "Status message not found"
    
    def test_dashboard_page_loads(self):
        """Test that the dashboard page loads correctly"""
        response = requests.get(f"{self.BASE_URL}/dashboard", timeout=10)
        assert response.status_code == 200
        assert "text/html" in response.headers.get("Content-Type", "")
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Check page title
        title = soup.find('title')
        assert title is not None, "Dashboard title not found"
        assert "CHSH Game - Host Dashboard" in title.get_text()
        
        # Check main heading
        header = soup.find('h1')
        assert header is not None, "Dashboard header not found"
        assert "Host Dashboard" in header.get_text()
    
    def test_dashboard_key_elements(self):
        """Test that key elements are present on the dashboard"""
        response = requests.get(f"{self.BASE_URL}/dashboard", timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Test metric cards - now merged into comprehensive stats card
        active_teams_count = soup.find('div', id='active-teams-count')
        assert active_teams_count is not None, "Active teams count not found"
        
        connected_players_count = soup.find('div', id='connected-players-count')
        assert connected_players_count is not None, "Connected players count not found"
        
        ready_players_count = soup.find('div', id='ready-players-count')
        assert ready_players_count is not None, "Ready players count not found"
        
        total_responses_count = soup.find('div', id='total-responses-count')
        assert total_responses_count is not None, "Total responses count not found"
        
        # Test game control buttons
        start_game_btn = soup.find('button', id='start-game-btn')
        assert start_game_btn is not None, "Start game button not found"
        assert "Start Game" in start_game_btn.get_text()
        
        pause_game_btn = soup.find('button', id='pause-game-btn')
        assert pause_game_btn is not None, "Pause game button not found"
        assert "Pause" in pause_game_btn.get_text()
        
        # Test teams table
        teams_table = soup.find('table', id='active-teams-table')
        assert teams_table is not None, "Teams table not found"
        
        # Check table headers
        headers = teams_table.find('thead').find_all('th')
        expected_headers = ['Team Name', 'Status', 'Current Round', 'Stats Sig', 'Trace Avg', 'Balance', 'Balanced', 'CHSH Value', 'Details']
        header_texts = [h.get_text().strip() for h in headers]
        
        for expected in expected_headers:
            assert any(expected in header for header in header_texts), f"Table header '{expected}' not found"
        
        # Test answer log section
        answer_log_table = soup.find('table', id='answer-log-table')
        assert answer_log_table is not None, "Answer log table not found"
        
        toggle_answers_btn = soup.find('button', id='toggle-answers-btn')
        assert toggle_answers_btn is not None, "Toggle answers button not found"
        
        # Test advanced controls section
        advanced_controls_header = soup.find('div', id='advanced-controls-header')
        assert advanced_controls_header is not None, "Advanced controls header not found"
        
        toggle_mode_btn = soup.find('button', id='toggle-mode-btn')
        assert toggle_mode_btn is not None, "Toggle mode button not found"
    
    def test_about_page_loads(self):
        """Test that the about page loads correctly"""
        response = requests.get(f"{self.BASE_URL}/about", timeout=10)
        assert response.status_code == 200
        assert "text/html" in response.headers.get("Content-Type", "")
    
    def test_static_css_files_load(self):
        """Test that CSS files are served correctly"""
        # Test main styles
        response = requests.get(f"{self.BASE_URL}/styles.css", timeout=10)
        assert response.status_code == 200
        assert "text/css" in response.headers.get("Content-Type", "")
        assert len(response.content) > 0, "CSS file is empty"
        
        # Test dashboard styles
        response = requests.get(f"{self.BASE_URL}/dashboard.css", timeout=10)
        assert response.status_code == 200
        assert "text/css" in response.headers.get("Content-Type", "")
        assert len(response.content) > 0, "Dashboard CSS file is empty"
    
    def test_static_js_files_load(self):
        """Test that JavaScript files are served correctly"""
        # Test main app.js
        response = requests.get(f"{self.BASE_URL}/app.js", timeout=10)
        assert response.status_code == 200
        assert "application/javascript" in response.headers.get("Content-Type", "") or "text/javascript" in response.headers.get("Content-Type", "")
        assert len(response.content) > 0, "app.js file is empty"
        
        # Test socket handlers
        response = requests.get(f"{self.BASE_URL}/socket-handlers.js", timeout=10)
        assert response.status_code == 200
        assert "application/javascript" in response.headers.get("Content-Type", "") or "text/javascript" in response.headers.get("Content-Type", "")
        assert len(response.content) > 0, "socket-handlers.js file is empty"
        
        # Test dashboard.js
        response = requests.get(f"{self.BASE_URL}/dashboard.js", timeout=10)
        assert response.status_code == 200
        assert "application/javascript" in response.headers.get("Content-Type", "") or "text/javascript" in response.headers.get("Content-Type", "")
        assert len(response.content) > 0, "dashboard.js file is empty"
    
    def test_api_server_id_endpoint(self):
        """Test that the server ID API endpoint works"""
        response = requests.get(f"{self.BASE_URL}/api/server/id", timeout=10)
        assert response.status_code == 200
        assert "application/json" in response.headers.get("Content-Type", "")
        
        data = response.json()
        assert "instance_id" in data, "Server ID response missing instance_id"
        assert isinstance(data["instance_id"], str), "instance_id should be a string"
        assert len(data["instance_id"]) > 0, "instance_id should not be empty"
    
    def test_dashboard_data_api_endpoint(self):
        """Test that the dashboard data API endpoint works"""
        response = requests.get(f"{self.BASE_URL}/api/dashboard/data", timeout=10)
        assert response.status_code == 200
        assert "application/json" in response.headers.get("Content-Type", "")
        
        data = response.json()
        # Check expected structure - this endpoint returns answers data
        assert "answers" in data, "Dashboard data missing answers"
        
        # Verify data types
        assert isinstance(data["answers"], list), "answers should be a list"
        
        # If there are answers, check the structure of the first one
        if data["answers"]:
            answer = data["answers"][0]
            expected_keys = ['answer_id', 'team_id', 'team_name', 'player_session_id', 
                           'question_round_id', 'assigned_item', 'response_value', 'timestamp']
            for key in expected_keys:
                assert key in answer, f"Answer missing key: {key}"
    
    def test_download_csv_endpoint(self):
        """Test that the CSV download endpoint works"""
        response = requests.get(f"{self.BASE_URL}/download", timeout=10)
        assert response.status_code == 200
        
        # Check content type for CSV
        content_type = response.headers.get("Content-Type", "")
        assert "text/csv" in content_type or "application/csv" in content_type, f"Expected CSV content type, got: {content_type}"
        
        # Check download headers
        content_disposition = response.headers.get("Content-Disposition", "")
        assert "attachment" in content_disposition, "CSV should be served as attachment"
        assert "filename=" in content_disposition, "CSV download should have filename"
        
        # Basic content check - should be CSV format
        content = response.text
        assert len(content) > 0, "CSV download should not be empty"
        # Basic CSV structure check (should have headers or at least some content structure)
        lines = content.strip().split('\n')
        assert len(lines) >= 1, "CSV should have at least one line"
    
    def test_nonexistent_page_fallback(self):
        """Test that nonexistent pages fall back to index.html"""
        response = requests.get(f"{self.BASE_URL}/nonexistent-page", timeout=10)
        assert response.status_code == 200  # Should fall back to index.html
        
        soup = BeautifulSoup(response.content, 'html.parser')
        title = soup.find('title')
        assert title is not None
        assert "CHSH Game - Participant" in title.get_text()
    
    def test_path_traversal_protection(self):
        """Test that path traversal attacks are blocked"""
        dangerous_paths = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd"
        ]
        
        for path in dangerous_paths:
            response = requests.get(f"{self.BASE_URL}/{path}", timeout=10)
            # Should either be forbidden or fall back to index.html, not serve system files
            assert response.status_code in [200, 403, 404], f"Unexpected response for path traversal: {response.status_code}"
            
            if response.status_code == 200:
                # If 200, should be the index.html fallback, not a system file
                soup = BeautifulSoup(response.content, 'html.parser')
                title = soup.find('title')
                assert title is not None and "CHSH Game" in title.get_text(), "Path traversal may have succeeded"
    
    def test_server_performance_basic(self):
        """Test basic server performance and responsiveness"""
        start_time = time.time()
        response = requests.get(self.BASE_URL, timeout=10)
        end_time = time.time()
        
        assert response.status_code == 200
        response_time = end_time - start_time
        assert response_time < 5.0, f"Server response too slow: {response_time:.2f}s"
    
    def test_multiple_concurrent_requests(self):
        """Test that server handles multiple concurrent requests"""
        import concurrent.futures
        import threading
        
        def make_request():
            response = requests.get(self.BASE_URL, timeout=10)
            return response.status_code
        
        # Make 5 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request) for _ in range(5)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        # All requests should succeed
        assert all(status == 200 for status in results), f"Some concurrent requests failed: {results}"
        assert len(results) == 5, "Not all concurrent requests completed"
    
    def test_content_security_headers(self):
        """Test that appropriate security headers are present (if configured)"""
        response = requests.get(self.BASE_URL, timeout=10)
        headers = response.headers
        
        # These are optional but good to test if present
        # Note: Not failing tests if headers are missing, just documenting expectations
        security_headers = [
            'X-Content-Type-Options',
            'X-Frame-Options', 
            'X-XSS-Protection'
        ]
        
        present_headers = []
        for header in security_headers:
            if header in headers:
                present_headers.append(header)
        
        # Log which security headers are present (informational)
        print(f"Security headers present: {present_headers}")
        
        # Always pass - this is informational only
        assert True, "Security headers check completed"
    
    def test_error_handling_404(self):
        """Test that 404 errors are handled gracefully for static files"""
        # Try to access a file that definitely doesn't exist
        response = requests.get(f"{self.BASE_URL}/definitely-does-not-exist.png", timeout=10)
        
        # Should either return 404 or fall back to index.html (200)
        assert response.status_code in [200, 404], f"Unexpected status for missing file: {response.status_code}"
        
        if response.status_code == 200:
            # If 200, should be index.html fallback
            soup = BeautifulSoup(response.content, 'html.parser')
            title = soup.find('title')
            assert title is not None and "CHSH Game" in title.get_text()