import pytest
from pathlib import Path
import re


class TestThemeControlFixes:
    """Test suite to verify that theme control fixes are properly implemented"""
    
    @pytest.fixture
    def dashboard_js_content(self):
        """Load the dashboard JavaScript content"""
        dashboard_js_path = (Path(__file__).parent / "../../src/static/dashboard.js").resolve()
        return dashboard_js_path.read_text(encoding='utf-8')
    
    @pytest.fixture
    def dashboard_py_content(self):
        """Load the dashboard Python socket handler content"""
        dashboard_py_path = (Path(__file__).parent / "../../src/sockets/dashboard.py").resolve()
        return dashboard_py_path.read_text(encoding='utf-8')
    
    def test_event_delegation_implemented(self, dashboard_js_content):
        """Test that event delegation is properly implemented for theme dropdown"""
        # Check that event delegation is set up at document level
        assert 'document.addEventListener(\'change\'' in dashboard_js_content, \
            "Event delegation should be set up at document level for change events"
        
        # Check that it specifically handles theme-dropdown
        assert 'event.target.id === \'theme-dropdown\'' in dashboard_js_content, \
            "Event delegation should specifically check for theme-dropdown ID"
        
        # Check that it calls onThemeChange
        assert 'onThemeChange()' in dashboard_js_content, \
            "Event delegation should call onThemeChange function"
    
    def test_skipDropdownUpdate_parameter_implemented(self, dashboard_js_content):
        """Test that skipDropdownUpdate parameter is properly implemented"""
        # Check function signature
        assert 'function updateGameThemeDisplay(theme, skipDropdownUpdate = false)' in dashboard_js_content, \
            "updateGameThemeDisplay should have skipDropdownUpdate parameter with default false"
        
        # Check that it's used in the function
        assert 'if (themeDropdown && !skipDropdownUpdate)' in dashboard_js_content, \
            "updateGameThemeDisplay should use skipDropdownUpdate parameter to conditionally update dropdown"
    
    def test_socket_events_use_skipDropdownUpdate(self, dashboard_js_content):
        """Test that socket events properly use skipDropdownUpdate parameter"""
        # Check that game_theme_changed uses skipDropdownUpdate=true
        assert 'updateGameThemeDisplay(data.theme, true)' in dashboard_js_content, \
            "game_theme_changed should call updateGameThemeDisplay with skipDropdownUpdate=true"
        
        # Check that game_state_sync uses skipDropdownUpdate=true
        assert 'updateGameThemeDisplay(data.theme, true)' in dashboard_js_content, \
            "game_state_sync should call updateGameThemeDisplay with skipDropdownUpdate=true"
        
        # Check that dashboard_update uses skipDropdownUpdate=true
        assert 'updateGameThemeDisplay(data.game_state.theme, true)' in dashboard_js_content, \
            "dashboard_update should call updateGameThemeDisplay with skipDropdownUpdate=true"
    
    def test_local_state_updated_immediately(self, dashboard_js_content):
        """Test that local theme state is updated immediately on change"""
        # Check that currentGameTheme is updated immediately
        assert 'currentGameTheme = newTheme' in dashboard_js_content, \
            "Local theme state should be updated immediately on change"
        
        # Check that it's used for comparison
        assert 'themeDropdown.value !== currentGameTheme' in dashboard_js_content, \
            "Theme change should compare against current local state"
    
    def test_backend_theme_included_in_dashboard_join(self, dashboard_py_content):
        """Test that backend includes theme in dashboard join response"""
        # Check that the game_state includes theme
        assert "'theme': state.game_theme" in dashboard_py_content, \
            "Backend should include theme in game_state when dashboard joins"
        
        # Check that it's in the dashboard_update data
        assert "'theme': state.game_theme" in dashboard_py_content, \
            "Backend should include theme in dashboard_update data"
    
    def test_backend_theme_change_handler_exists(self, dashboard_py_content):
        """Test that backend has proper theme change handler"""
        # Check that the function exists
        assert 'def on_change_game_theme(' in dashboard_py_content, \
            "Backend should have on_change_game_theme function"
        
        # Check that it updates the state
        assert 'state.game_theme = new_theme' in dashboard_py_content, \
            "Backend should update game_theme state"
        
        # Check that it broadcasts the change
        assert 'socketio.emit(\'game_theme_changed\'' in dashboard_py_content, \
            "Backend should emit game_theme_changed event"
    
    def test_theme_validation(self, dashboard_py_content):
        """Test that backend validates theme values"""
        # Check that only valid themes are accepted
        valid_themes = ['food', 'classic']
        for theme in valid_themes:
            assert f"'{theme}'" in dashboard_py_content, \
                f"Backend should support '{theme}' theme"
    
    def test_event_delegation_placement(self, dashboard_js_content):
        """Test that event delegation is set up early in the script"""
        # Get the first 50 lines to check placement
        first_lines = dashboard_js_content.split('\n')[:50]
        first_lines_text = '\n'.join(first_lines)
        
        # Check that event delegation is set up early
        assert 'document.addEventListener(\'change\'' in first_lines_text, \
            "Event delegation should be set up early in the script, not in window.load event"
    
    def test_onThemeChange_function_definition(self, dashboard_js_content):
        """Test that onThemeChange function is properly defined"""
        # Check function definition
        assert 'function onThemeChange()' in dashboard_js_content, \
            "onThemeChange function should be defined"
        
        # Check that it emits the correct socket event
        assert 'socket.emit(\'change_game_theme\'' in dashboard_js_content, \
            "onThemeChange should emit change_game_theme socket event"
        
        # Check that it sends the correct data
        assert '{ theme: newTheme }' in dashboard_js_content, \
            "onThemeChange should send correct data structure"
    
    def test_updateGameThemeDisplay_function_definition(self, dashboard_js_content):
        """Test that updateGameThemeDisplay function is properly defined"""
        # Check function definition with parameters
        assert 'function updateGameThemeDisplay(theme, skipDropdownUpdate = false)' in dashboard_js_content, \
            "updateGameThemeDisplay should be defined with correct parameters"
        
        # Check that it updates the currentGameTheme
        assert 'currentGameTheme = theme' in dashboard_js_content, \
            "updateGameThemeDisplay should update currentGameTheme"
        
        # Check that it conditionally updates the dropdown
        assert 'if (themeDropdown && !skipDropdownUpdate)' in dashboard_js_content, \
            "updateGameThemeDisplay should conditionally update dropdown based on skipDropdownUpdate"
    
    def test_theme_change_flow_complete(self, dashboard_js_content):
        """Test that the complete theme change flow is implemented"""
        # Check that user can change theme
        assert 'onThemeChange()' in dashboard_js_content, \
            "User should be able to trigger theme change"
        
        # Check that change is sent to server
        assert 'socket.emit(\'change_game_theme\'' in dashboard_js_content, \
            "Theme change should be sent to server"
        
        # Check that server response is handled
        assert 'socket.on(\'game_theme_changed\'' in dashboard_js_content, \
            "Server response should be handled"
        
        # Check that UI is updated without resetting dropdown
        assert 'updateGameThemeDisplay(data.theme, true)' in dashboard_js_content, \
            "UI should be updated without resetting dropdown"
