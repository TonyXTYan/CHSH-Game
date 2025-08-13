import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from src.sockets.dashboard import on_change_game_theme, on_dashboard_join
from src.state import GameState


class TestDashboardThemeControl:
    """Test suite for dashboard theme control functionality"""
    
    @pytest.fixture
    def mock_socket(self):
        """Mock socket for testing"""
        socket = Mock()
        socket.emit = Mock()
        return socket
    
    @pytest.fixture
    def mock_state(self):
        """Mock game state"""
        state = Mock(spec=GameState)
        state.game_theme = 'food'
        state.game_mode = 'new'
        state.game_started = False
        state.answer_stream_enabled = False
        state.connected_players = []
        return state
    
    @pytest.fixture
    def mock_request(self):
        """Mock request object"""
        request = Mock()
        request.sid = 'test_sid_123'
        return request
    
    def test_on_change_game_theme_updates_state_and_broadcasts(self, mock_socket, mock_state, mock_request):
        """Test that theme change properly updates state and broadcasts to all clients"""
        # Arrange
        data = {'theme': 'classic'}
        
        # Act
        on_change_game_theme(mock_socket, data, mock_state, mock_request)
        
        # Assert
        assert mock_state.game_theme == 'classic'
        mock_socket.emit.assert_called_once_with(
            'game_theme_changed', 
            {'theme': 'classic'}, 
            room='dashboard_clients'
        )
    
    def test_on_change_game_theme_invalid_theme(self, mock_socket, mock_state, mock_request):
        """Test that invalid theme values are rejected"""
        # Arrange
        data = {'theme': 'invalid_theme'}
        
        # Act
        on_change_game_theme(mock_socket, data, mock_state, mock_request)
        
        # Assert
        assert mock_state.game_theme == 'food'  # Should remain unchanged
        mock_socket.emit.assert_not_called()
    
    def test_on_change_game_theme_missing_theme(self, mock_socket, mock_state, mock_request):
        """Test that missing theme data is handled gracefully"""
        # Arrange
        data = {}
        
        # Act
        on_change_game_theme(mock_socket, data, mock_state, mock_request)
        
        # Assert
        assert mock_state.game_theme == 'food'  # Should remain unchanged
        mock_socket.emit.assert_not_called()
    
    def test_on_dashboard_join_includes_theme_in_game_state(self, mock_socket, mock_state, mock_request):
        """Test that dashboard join includes current theme in game state"""
        # Arrange
        mock_state.game_theme = 'classic'
        mock_state.game_mode = 'new'
        mock_state.game_started = False
        mock_state.answer_stream_enabled = False
        mock_state.connected_players = []
        
        # Act
        on_dashboard_join(mock_socket, mock_request, mock_state)
        
        # Assert
        # Verify that the emit was called with game_state containing theme
        mock_socket.emit.assert_called()
        call_args = mock_socket.emit.call_args_list
        
        # Find the call that contains game_state
        game_state_call = None
        for call in call_args:
            if call[0][0] == 'dashboard_update':
                data = call[0][1]
                if 'game_state' in data and 'theme' in data['game_state']:
                    game_state_call = call
                    break
        
        assert game_state_call is not None, "dashboard_update should include game_state with theme"
        assert game_state_call[0][1]['game_state']['theme'] == 'classic'
    
    def test_theme_change_preserves_other_state(self, mock_socket, mock_state, mock_request):
        """Test that theme change doesn't affect other game state"""
        # Arrange
        original_mode = mock_state.game_mode
        original_started = mock_state.game_started
        data = {'theme': 'classic'}
        
        # Act
        on_change_game_theme(mock_socket, data, mock_state, mock_request)
        
        # Assert
        assert mock_state.game_theme == 'classic'
        assert mock_state.game_mode == original_mode
        assert mock_state.game_started == original_started
    
    def test_multiple_theme_changes(self, mock_socket, mock_state, mock_request):
        """Test that multiple theme changes work correctly"""
        # Arrange
        themes = ['food', 'classic', 'food']
        
        # Act & Assert
        for i, theme in enumerate(themes):
            data = {'theme': theme}
            on_change_game_theme(mock_socket, data, mock_state, mock_request)
            
            assert mock_state.game_theme == theme
            assert mock_socket.emit.call_count == i + 1
    
    def test_theme_change_with_connected_players(self, mock_socket, mock_state, mock_request):
        """Test theme change when players are connected"""
        # Arrange
        mock_state.connected_players = ['player1', 'player2']
        data = {'theme': 'classic'}
        
        # Act
        on_change_game_theme(mock_socket, data, mock_state, mock_request)
        
        # Assert
        assert mock_state.game_theme == 'classic'
        mock_socket.emit.assert_called_once_with(
            'game_theme_changed', 
            {'theme': 'classic'}, 
            room='dashboard_clients'
        )
    
    def test_theme_change_broadcasts_to_dashboard_clients(self, mock_socket, mock_state, mock_request):
        """Test that theme change broadcasts specifically to dashboard clients"""
        # Arrange
        data = {'theme': 'classic'}
        
        # Act
        on_change_game_theme(mock_socket, data, mock_state, mock_request)
        
        # Assert
        mock_socket.emit.assert_called_once_with(
            'game_theme_changed', 
            {'theme': 'classic'}, 
            room='dashboard_clients'
        )
    
    def test_theme_change_handles_none_data(self, mock_socket, mock_state, mock_request):
        """Test that None data is handled gracefully"""
        # Arrange
        data = None
        
        # Act
        on_change_game_theme(mock_socket, data, mock_state, mock_request)
        
        # Assert
        assert mock_state.game_theme == 'food'  # Should remain unchanged
        mock_socket.emit.assert_not_called()
    
    def test_theme_change_handles_empty_string(self, mock_socket, mock_state, mock_request):
        """Test that empty string theme is handled gracefully"""
        # Arrange
        data = {'theme': ''}
        
        # Act
        on_change_game_theme(mock_socket, data, mock_state, mock_request)
        
        # Assert
        assert mock_state.game_theme == 'food'  # Should remain unchanged
        mock_socket.emit.assert_not_called()


class TestDashboardThemeIntegration:
    """Integration tests for theme control with dashboard updates"""
    
    @pytest.fixture
    def mock_socket(self):
        """Mock socket for testing"""
        socket = Mock()
        socket.emit = Mock()
        return socket
    
    @pytest.fixture
    def mock_state(self):
        """Mock game state"""
        state = Mock(spec=GameState)
        state.game_theme = 'food'
        state.game_mode = 'new'
        state.game_started = False
        state.answer_stream_enabled = False
        state.connected_players = []
        return state
    
    @pytest.fixture
    def mock_request(self):
        """Mock request object"""
        request = Mock()
        request.sid = 'test_sid_123'
        return request
    
    def test_dashboard_join_sends_complete_theme_state(self, mock_socket, mock_state, mock_request):
        """Test that dashboard join sends complete theme information"""
        # Arrange
        mock_state.game_theme = 'classic'
        
        # Act
        on_dashboard_join(mock_socket, mock_request, mock_state)
        
        # Assert
        mock_socket.emit.assert_called()
        
        # Check that the dashboard_update includes theme in game_state
        dashboard_update_calls = [
            call for call in mock_socket.emit.call_args_list 
            if call[0][0] == 'dashboard_update'
        ]
        
        assert len(dashboard_update_calls) > 0, "Should emit dashboard_update"
        
        for call in dashboard_update_calls:
            data = call[0][1]
            if 'game_state' in data:
                assert 'theme' in data['game_state'], "game_state should include theme"
                assert data['game_state']['theme'] == 'classic'
    
    def test_theme_sync_after_dashboard_join(self, mock_socket, mock_state, mock_request):
        """Test that theme is properly synced after dashboard joins"""
        # Arrange
        mock_state.game_theme = 'classic'
        
        # Act
        on_dashboard_join(mock_socket, mock_request, mock_state)
        
        # Assert
        # Verify that the theme is included in the initial state
        mock_socket.emit.assert_called()
        
        # Find the dashboard_update call
        dashboard_update_call = None
        for call in mock_socket.emit.call_args_list:
            if call[0][0] == 'dashboard_update':
                data = call[0][1]
                if 'game_state' in data:
                    dashboard_update_call = call
                    break
        
        assert dashboard_update_call is not None, "Should emit dashboard_update with game_state"
        data = dashboard_update_call[0][1]
        assert data['game_state']['theme'] == 'classic'
