"""
Integration test for AQM Joe theme functionality.
"""
import pytest
import sys
import os
from unittest.mock import patch, MagicMock

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from sockets.dashboard import on_change_game_theme, compute_success_metrics
from state import state


class TestAqmJoeIntegration:
    """Integration tests for AQM Joe theme."""
    
    def setup_method(self):
        """Reset state before each test."""
        state.reset()
        state.dashboard_clients.add('test_dashboard_sid')
    
    @patch('src.sockets.dashboard.emit')
    @patch('src.sockets.dashboard.socketio')
    @patch('src.sockets.dashboard.request')
    def test_change_to_aqmjoe_theme(self, mock_request, mock_socketio, mock_emit):
        """Test changing theme to aqmjoe via socket event."""
        # Setup mock request
        mock_request.sid = 'test_dashboard_sid'
        
        # Test changing to aqmjoe theme
        theme_data = {'theme': 'aqmjoe'}
        on_change_game_theme(theme_data)
        
        # Verify theme was changed in state
        assert state.game_theme == 'aqmjoe'
        
        # Verify socket emissions were called
        mock_socketio.emit.assert_called()
        
        # Check that the theme change was broadcast
        calls = mock_socketio.emit.call_args_list
        theme_change_call = None
        for call in calls:
            if call[0][0] == 'game_theme_changed':
                theme_change_call = call
                break
        
        assert theme_change_call is not None
        assert theme_change_call[0][1]['theme'] == 'aqmjoe'
    
    @patch('src.sockets.dashboard.emit')
    @patch('src.sockets.dashboard.request')
    def test_invalid_theme_rejected(self, mock_request, mock_emit):
        """Test that invalid themes are rejected."""
        mock_request.sid = 'test_dashboard_sid'
        
        # Test with invalid theme
        theme_data = {'theme': 'invalid_theme'}
        on_change_game_theme(theme_data)
        
        # Verify theme was not changed
        assert state.game_theme != 'invalid_theme'
        
        # Verify error was emitted
        mock_emit.assert_called_with('error', {'message': 'Unsupported theme "invalid_theme". Supported themes: classic, food, aqmjoe'})
    
    @patch('src.sockets.dashboard.emit')  
    @patch('src.sockets.dashboard.request')
    def test_unauthorized_theme_change_rejected(self, mock_request, mock_emit):
        """Test that unauthorized clients cannot change theme."""
        mock_request.sid = 'unauthorized_sid'  # Not in dashboard_clients
        
        theme_data = {'theme': 'aqmjoe'}
        on_change_game_theme(theme_data)
        
        # Verify theme was not changed
        assert state.game_theme != 'aqmjoe'
        
        # Verify error was emitted
        mock_emit.assert_called_with('error', {'message': 'Unauthorized: Not a dashboard client'})
    
    def test_compute_success_metrics_with_aqmjoe_theme(self):
        """Test that success metrics computation works with aqmjoe theme."""
        # Set up state for aqmjoe theme in new mode
        state.game_theme = 'aqmjoe'
        state.game_mode = 'new'
        
        # This is a basic test to ensure the function doesn't crash
        # More detailed testing would require setting up database mocks
        try:
            result = compute_success_metrics('nonexistent_team')
            # Should return default empty result for nonexistent team
            assert result[0] == [[(0, 0) for _ in range(4)] for _ in range(4)]
            assert result[1] == ['A', 'B', 'X', 'Y']
            assert result[2] == 0.0  # success rate
            assert result[3] == 0.0  # normalized score
        except Exception as e:
            pytest.fail(f"compute_success_metrics failed with aqmjoe theme: {e}")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])