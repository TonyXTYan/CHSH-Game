import unittest
import threading
import time
from src.state import AppState

class TestAppState(unittest.TestCase):
    def setUp(self):
        self.state = AppState()
        
    def test_thread_safety(self):
        """Test thread safety of state operations"""
        # Create a team
        self.state.create_team("test_team", 1)
        
        # Define functions to run in threads
        def add_players():
            for i in range(100):
                self.state.add_player_to_team(f"player_{i}", "test_team")
                time.sleep(0.001)
                
        def remove_players():
            for i in range(100):
                self.state.remove_player_from_team(f"player_{i}")
                time.sleep(0.001)
        
        # Create and start threads
        thread1 = threading.Thread(target=add_players)
        thread2 = threading.Thread(target=remove_players)
        
        thread1.start()
        thread2.start()
        
        # Wait for threads to complete
        thread1.join()
        thread2.join()
        
        # Verify state is consistent
        team_info = self.state.get_team_info("test_team")
        self.assertIsNotNone(team_info)
        
    def test_add_remove_player(self):
        """Test adding and removing players from teams"""
        # Create a team
        self.state.create_team("test_team", 1)
        
        # Add a player
        result = self.state.add_player_to_team("player1", "test_team")
        self.assertTrue(result)
        
        # Verify player was added
        team_info = self.state.get_team_info("test_team")
        self.assertIn("player1", team_info["players"])
        
        # Get player's team
        team_name = self.state.get_player_team("player1")
        self.assertEqual(team_name, "test_team")
        
        # Remove the player
        team_name, count = self.state.remove_player_from_team("player1")
        self.assertEqual(team_name, "test_team")
        self.assertEqual(count, 0)
        
        # Verify player was removed
        team_info = self.state.get_team_info("test_team")
        self.assertNotIn("player1", team_info["players"])
        
    def test_team_round_management(self):
        """Test team round management"""
        # Create a team
        self.state.create_team("test_team", 1)
        
        # Update team round
        result = self.state.update_team_round("test_team", 123)
        self.assertTrue(result)
        
        # Verify round was updated
        team_info = self.state.get_team_info("test_team")
        self.assertEqual(team_info["current_db_round_id"], 123)
        self.assertEqual(len(team_info["answered_current_round"]), 0)
        
        # Add a player
        self.state.add_player_to_team("player1", "test_team")
        
        # Mark player as answered
        count = self.state.mark_player_answered("test_team", "player1")
        self.assertEqual(count, 1)
        
        # Verify player was marked
        team_info = self.state.get_team_info("test_team")
        self.assertTrue(team_info["answered_current_round"]["player1"])
        
    def test_game_state_management(self):
        """Test game state management"""
        # Default state
        self.assertFalse(self.state.is_game_started())
        self.assertFalse(self.state.is_game_paused())
        
        # Set game started
        self.state.set_game_started(True)
        self.assertTrue(self.state.is_game_started())
        
        # Set game paused
        self.state.set_game_paused(True)
        self.assertTrue(self.state.is_game_paused())
        
        # Reset state
        self.state.reset()
        self.assertFalse(self.state.is_game_started())
        self.assertFalse(self.state.is_game_paused())
        
    def test_dashboard_client_management(self):
        """Test dashboard client management"""
        # Add dashboard client
        self.state.add_dashboard_client("dash1")
        
        # Verify client was added
        self.assertIn("dash1", self.state.dashboard_clients)
        
        # Remove dashboard client
        self.state.remove_dashboard_client("dash1")
        
        # Verify client was removed
        self.assertNotIn("dash1", self.state.dashboard_clients)
        
    def test_connected_player_management(self):
        """Test connected player management"""
        # Add connected player
        self.state.add_connected_player("player1")
        
        # Verify player was added
        self.assertIn("player1", self.state.connected_players)
        
        # Remove connected player
        self.state.remove_connected_player("player1")
        
        # Verify player was removed
        self.assertNotIn("player1", self.state.connected_players)
        
    def test_team_removal(self):
        """Test team removal"""
        # Create a team
        self.state.create_team("test_team", 1)
        self.state.team_id_to_name[1] = "test_team"
        
        # Remove the team
        result = self.state.remove_team("test_team")
        self.assertTrue(result)
        
        # Verify team was removed
        self.assertNotIn("test_team", self.state.active_teams)
        self.assertNotIn(1, self.state.team_id_to_name)

if __name__ == '__main__':
    unittest.main()
