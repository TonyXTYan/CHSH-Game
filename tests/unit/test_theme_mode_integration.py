import pytest
from unittest.mock import Mock, patch
from src.state import state
from src.sockets.dashboard import on_change_game_theme, on_toggle_game_mode


class TestThemeModeIntegration:
    """Integration tests for theme-mode linking functionality."""
    
    def setup_method(self):
        """Setup for each test method."""
        # Reset state before each test
        state.game_mode = 'simplified'
        state.game_theme = 'food'
    
    @patch('src.sockets.dashboard.emit')
    @patch('src.sockets.dashboard.socketio')
    @patch('src.sockets.dashboard.force_clear_all_caches')
    @patch('src.sockets.dashboard.request')
    def test_theme_mode_linking_aqmjoe_theme_forces_aqmjoe_mode(self, mock_request, mock_clear_caches, mock_socketio, mock_emit):
        """Test that selecting aqmjoe theme forces aqmjoe mode."""
        # Setup mock request
        mock_request.sid = 'test_sid'
        state.dashboard_clients.add('test_sid')
        
        # Change theme to aqmjoe
        data = {'theme': 'aqmjoe'}
        on_change_game_theme(data)
        
        # Verify both theme and mode are set to aqmjoe
        assert state.game_theme == 'aqmjoe'
        assert state.game_mode == 'aqmjoe'
        
        # Verify events were emitted
        mock_socketio.emit.assert_any_call('game_theme_changed', {'theme': 'aqmjoe'})
        mock_socketio.emit.assert_any_call('game_mode_changed', {'mode': 'aqmjoe'})
    
    @patch('src.sockets.dashboard.emit')
    @patch('src.sockets.dashboard.socketio')
    @patch('src.sockets.dashboard.force_clear_all_caches')
    @patch('src.sockets.dashboard.request')
    def test_theme_mode_linking_leaving_aqmjoe_theme(self, mock_request, mock_clear_caches, mock_socketio, mock_emit):
        """Test that leaving aqmjoe theme switches to simplified mode."""
        # Setup mock request
        mock_request.sid = 'test_sid'
        state.dashboard_clients.add('test_sid')
        
        # Start with aqmjoe theme and mode
        state.game_theme = 'aqmjoe'
        state.game_mode = 'aqmjoe'
        
        # Change theme to food
        data = {'theme': 'food'}
        on_change_game_theme(data)
        
        # Verify theme is food and mode is simplified
        assert state.game_theme == 'food'
        assert state.game_mode == 'simplified'
    
    @patch('src.sockets.dashboard.emit_dashboard_full_update')
    @patch('src.sockets.dashboard.socketio')
    @patch('src.sockets.dashboard.force_clear_all_caches')
    @patch('src.sockets.dashboard.request')
    def test_mode_toggle_cycle(self, mock_request, mock_clear_caches, mock_socketio, mock_emit_update):
        """Test the three-mode toggle cycle."""
        # Setup mock request
        mock_request.sid = 'test_sid'
        state.dashboard_clients.add('test_sid')
        
        # Start with classic mode
        state.game_mode = 'classic'
        state.game_theme = 'classic'
        
        # Toggle to simplified
        on_toggle_game_mode()
        assert state.game_mode == 'simplified'
        assert state.game_theme == 'food'  # Should auto-switch theme
        
        # Toggle to aqmjoe
        on_toggle_game_mode()
        assert state.game_mode == 'aqmjoe'
        assert state.game_theme == 'aqmjoe'  # Should auto-switch theme
        
        # Toggle back to classic
        on_toggle_game_mode()
        assert state.game_mode == 'classic'
        assert state.game_theme == 'food'  # Should auto-switch theme when leaving aqmjoe
    
    def test_backward_compatibility_new_mode(self):
        """Test that 'new' mode is properly handled as 'simplified'."""
        from src.game_logic import get_effective_combo_repeats
        
        # Test that 'new' mode gets same treatment as 'simplified'
        new_repeats = get_effective_combo_repeats('new')
        simplified_repeats = get_effective_combo_repeats('simplified')
        classic_repeats = get_effective_combo_repeats('classic')
        aqmjoe_repeats = get_effective_combo_repeats('aqmjoe')
        
        assert new_repeats == simplified_repeats
        assert new_repeats != classic_repeats
        assert aqmjoe_repeats == classic_repeats
    
    def teardown_method(self):
        """Cleanup after each test method."""
        state.dashboard_clients.clear()
        state.game_mode = 'simplified'
        state.game_theme = 'food'