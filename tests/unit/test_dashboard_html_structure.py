import pytest
from pathlib import Path
import re


class TestDashboardHTMLStructure:
    """Test suite for dashboard HTML structure and theme control setup"""
    
    @pytest.fixture
    def dashboard_html_content(self):
        """Load the dashboard HTML content"""
        dashboard_path = Path("src/static/dashboard.html")
        return dashboard_path.read_text(encoding='utf-8')
    
    def test_theme_dropdown_exists(self, dashboard_html_content):
        """Test that the theme dropdown exists with correct ID"""
        # Check that theme dropdown exists
        assert 'id="theme-dropdown"' in dashboard_html_content, "Theme dropdown should exist with id 'theme-dropdown'"
        
        # Check that it's a select element
        assert '<select' in dashboard_html_content, "Theme dropdown should be a select element"
        
        # Check that it has the correct class attribute
        assert 'class="control-btn theme-dropdown"' in dashboard_html_content, "Theme dropdown should have correct class attributes"
    
    def test_theme_dropdown_options(self, dashboard_html_content):
        """Test that the theme dropdown has the correct options"""
        # Check for food theme option
        assert 'value="food"' in dashboard_html_content, "Theme dropdown should have 'food' option"
        assert 'value="classic"' in dashboard_html_content, "Theme dropdown should have 'classic' option"
        
        # Check that the options are properly formatted
        assert 'option value="food"' in dashboard_html_content, "Food theme option should be properly formatted"
        assert 'option value="classic"' in dashboard_html_content, "Classic theme option should be properly formatted"
    
    def test_theme_dropdown_in_advanced_controls(self, dashboard_html_content):
        """Test that the theme dropdown is in the advanced controls section"""
        # Check that theme dropdown is inside advanced controls
        advanced_controls_pattern = r'<div[^>]*id="advanced-controls-content"[^>]*>.*?id="theme-dropdown".*?</div>'
        assert re.search(advanced_controls_pattern, dashboard_html_content, re.DOTALL), \
            "Theme dropdown should be inside advanced-controls-content div"
    
    def test_theme_indicator_exists(self, dashboard_html_content):
        """Test that the theme indicator element exists"""
        assert 'id="current-game-theme"' in dashboard_html_content, "Theme indicator should exist with id 'current-game-theme'"
    
    def test_theme_description_exists(self, dashboard_html_content):
        """Test that the theme description element exists"""
        assert 'id="theme-description-text"' in dashboard_html_content, "Theme description should exist with id 'theme-description-text'"
    
    def test_theme_control_section_structure(self, dashboard_html_content):
        """Test that the theme control section has proper structure"""
        # Check that theme controls are properly labeled
        assert '<h4>Theme</h4>' in dashboard_html_content, "Theme control section should be labeled with h4"
        
        # Check that there's a label for the dropdown
        assert 'for="theme-dropdown"' in dashboard_html_content, "Theme dropdown should have a proper label"
    
    def test_advanced_controls_toggle(self, dashboard_html_content):
        """Test that advanced controls can be toggled"""
        # Check that advanced controls header exists (clickable toggle)
        assert 'id="advanced-controls-header"' in dashboard_html_content, "Advanced controls header should exist for toggling"
        
        # Check that advanced controls content is initially hidden
        assert 'style="display: none;"' in dashboard_html_content, "Advanced controls should be initially hidden"
    
    def test_theme_dropdown_accessibility(self, dashboard_html_content):
        """Test that the theme dropdown has proper accessibility attributes"""
        # Check for proper labeling
        assert 'aria-label' in dashboard_html_content or 'for=' in dashboard_html_content, \
            "Theme dropdown should have proper labeling for accessibility"
        
        # Check that it's not disabled by default (disabled is a boolean attribute; absence means enabled)
        assert 'disabled' not in dashboard_html_content, \
            "Theme dropdown should not be disabled by default"


class TestDashboardJavaScriptIntegration:
    """Test suite for JavaScript integration with HTML structure"""
    
    @pytest.fixture
    def dashboard_js_content(self):
        """Load the dashboard JavaScript content"""
        dashboard_js_path = Path("src/static/dashboard.js")
        return dashboard_js_path.read_text(encoding='utf-8')
    
    def test_event_delegation_setup(self, dashboard_js_content):
        """Test that event delegation is properly set up for theme dropdown"""
        # Check that event delegation is set up at document level
        assert 'document.addEventListener(\'change\'' in dashboard_js_content, \
            "Event delegation should be set up at document level for change events"
        
        # Check that it specifically handles theme-dropdown
        assert 'event.target.id === \'theme-dropdown\'' in dashboard_js_content, \
            "Event delegation should specifically check for theme-dropdown ID"
    
    def test_onThemeChange_function_exists(self, dashboard_js_content):
        """Test that the onThemeChange function is defined"""
        assert 'function onThemeChange()' in dashboard_js_content, \
            "onThemeChange function should be defined"
    
    def test_updateGameThemeDisplay_function_exists(self, dashboard_js_content):
        """Test that the updateGameThemeDisplay function is defined"""
        assert 'function updateGameThemeDisplay(' in dashboard_js_content, \
            "updateGameThemeDisplay function should be defined"
    
    def test_skipDropdownUpdate_parameter(self, dashboard_js_content):
        """Test that updateGameThemeDisplay supports skipDropdownUpdate parameter"""
        # Check function signature
        assert 'skipDropdownUpdate = false' in dashboard_js_content, \
            "updateGameThemeDisplay should have skipDropdownUpdate parameter with default false"
        
        # Check that it's used in the function
        assert '!skipDropdownUpdate' in dashboard_js_content, \
            "updateGameThemeDisplay should use skipDropdownUpdate parameter"
    
    def test_socket_theme_change_handling(self, dashboard_js_content):
        """Test that socket events properly handle theme changes"""
        # Check for game_theme_changed event handler
        assert 'socket.on(\'game_theme_changed\'' in dashboard_js_content, \
            "Should handle game_theme_changed socket event"
        
        # Check that it calls updateGameThemeDisplay with skipDropdownUpdate
        assert 'updateGameThemeDisplay(data.theme, true)' in dashboard_js_content, \
            "game_theme_changed should call updateGameThemeDisplay with skipDropdownUpdate=true"
    
    def test_theme_change_socket_emission(self, dashboard_js_content):
        """Test that theme changes emit the correct socket event"""
        # Check that onThemeChange emits change_game_theme
        assert 'socket.emit(\'change_game_theme\'' in dashboard_js_content, \
            "onThemeChange should emit change_game_theme socket event"
        
        # Check that it sends the correct data structure
        assert '{ theme: newTheme }' in dashboard_js_content, \
            "Theme change should send correct data structure"
    
    def test_local_state_management(self, dashboard_js_content):
        """Test that local theme state is properly managed"""
        # Check that currentGameTheme is updated immediately
        assert 'currentGameTheme = newTheme' in dashboard_js_content, \
            "Local theme state should be updated immediately on change"
        
        # Check that it's used for comparison
        assert 'themeDropdown.value !== currentGameTheme' in dashboard_js_content, \
            "Theme change should compare against current local state"
