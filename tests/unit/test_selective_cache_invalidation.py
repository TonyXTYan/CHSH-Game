import pytest
from unittest.mock import patch, MagicMock
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from src.sockets.dashboard import (
    SelectiveCache, 
    selective_cache,
    invalidate_team_caches,
    clear_team_caches,
    _make_cache_key
)


class TestSelectiveCache:
    """Test the SelectiveCache class functionality."""
    
    def test_basic_cache_operations(self):
        """Test basic cache get/set operations."""
        cache = SelectiveCache(maxsize=3)
        
        # Test set and get
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"
        assert cache.get("nonexistent") is None
        
        # Test LRU eviction
        cache.set("key2", "value2")
        cache.set("key3", "value3")
        cache.set("key4", "value4")  # Should evict key1
        
        assert cache.get("key1") is None  # Evicted
        assert cache.get("key2") == "value2"
        assert cache.get("key3") == "value3"
        assert cache.get("key4") == "value4"
    
    def test_lru_ordering(self):
        """Test that LRU ordering works correctly."""
        cache = SelectiveCache(maxsize=2)
        
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        
        # Access key1 to make it most recently used
        cache.get("key1")
        
        # Add key3, should evict key2 (least recently used)
        cache.set("key3", "value3")
        
        assert cache.get("key1") == "value1"  # Still there
        assert cache.get("key2") is None     # Evicted
        assert cache.get("key3") == "value3"  # New entry
    
    def test_clear_all(self):
        """Test clearing all cache entries."""
        cache = SelectiveCache()
        
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        
        cache.clear_all()
        
        assert cache.get("key1") is None
        assert cache.get("key2") is None
        assert len(cache._cache) == 0
        assert len(cache._access_order) == 0


class TestTeamKeyMatching:
    """Test the _is_team_key method for precise team matching."""
    
    def test_simple_team_name_keys(self):
        """Test matching simple team name keys."""
        cache = SelectiveCache()
        
        # Exact matches should work
        assert cache._is_team_key("Team1", "Team1") == True
        assert cache._is_team_key("TeamAlpha", "TeamAlpha") == True
        
        # Substring matches should NOT work
        assert cache._is_team_key("Team11", "Team1") == False
        assert cache._is_team_key("Team1_backup", "Team1") == False
        assert cache._is_team_key("MyTeam1", "Team1") == False
    
    def test_function_cache_keys_first_parameter(self):
        """Test matching function cache keys where team_name is first parameter."""
        cache = SelectiveCache()
        
        # Should match when team_name is first parameter
        assert cache._is_team_key("('Team1',)", "Team1") == True
        assert cache._is_team_key("('Team1', 'arg2')", "Team1") == True
        assert cache._is_team_key("('Team1', 123, True)", "Team1") == True
        
        # Should NOT match similar team names
        assert cache._is_team_key("('Team11',)", "Team1") == False
        assert cache._is_team_key("('Team11', 'arg2')", "Team1") == False
        assert cache._is_team_key("('MyTeam1', 'arg2')", "Team1") == False
    
    def test_function_cache_keys_other_parameters(self):
        """Test matching function cache keys where team_name is not first parameter."""
        cache = SelectiveCache()
        
        # Should match when team_name appears as other parameters
        assert cache._is_team_key("('arg1', 'Team1')", "Team1") == True
        assert cache._is_team_key("('arg1', 'Team1', 'arg3')", "Team1") == True
        assert cache._is_team_key("(123, 'Team1', True)", "Team1") == True
        
        # Should NOT match substring cases
        assert cache._is_team_key("('arg1', 'Team11')", "Team1") == False
        assert cache._is_team_key("('arg1', 'MyTeam1')", "Team1") == False
        assert cache._is_team_key("('arg1', 'Team1_backup')", "Team1") == False
    
    def test_edge_cases_with_special_characters(self):
        """Test team names with special characters."""
        cache = SelectiveCache()
        
        # Team names with special regex characters
        assert cache._is_team_key("('Team.1',)", "Team.1") == True
        assert cache._is_team_key("('Team+1',)", "Team+1") == True
        assert cache._is_team_key("('Team[1]',)", "Team[1]") == True
        assert cache._is_team_key("('Team(1)',)", "Team(1)") == True
        
        # Should not match similar names with special chars
        assert cache._is_team_key("('Team.11',)", "Team.1") == False
        assert cache._is_team_key("('Team+11',)", "Team+1") == False
    
    def test_whitespace_handling(self):
        """Test handling of whitespace in cache keys."""
        cache = SelectiveCache()
        
        # Should handle whitespace around commas
        assert cache._is_team_key("('arg1',  'Team1')", "Team1") == True
        assert cache._is_team_key("('arg1', 'Team1'  )", "Team1") == True
        assert cache._is_team_key("('Team1'  ,  'arg2')", "Team1") == True
        
        # Should not match with whitespace differences in team name
        assert cache._is_team_key("('Team 1',)", "Team1") == False
        assert cache._is_team_key("('Team1 ',)", "Team1") == False


class TestSelectiveCacheInvalidation:
    """Test the selective cache invalidation functionality."""
    
    def test_invalidate_by_team_basic(self):
        """Test basic selective invalidation by team."""
        cache = SelectiveCache()
        
        # Populate cache with different teams
        cache.set("('Team1',)", "result1")
        cache.set("('Team2',)", "result2")
        cache.set("('Team11',)", "result11")  # Similar name that should NOT be invalidated
        cache.set("('OtherTeam',)", "other")
        
        # Invalidate Team1 - should only affect Team1, not Team11
        invalidated = cache.invalidate_by_team("Team1")
        
        assert invalidated == 1
        assert cache.get("('Team1',)") is None      # Invalidated
        assert cache.get("('Team2',)") == "result2"  # Preserved
        assert cache.get("('Team11',)") == "result11"  # Preserved (this is the key test!)
        assert cache.get("('OtherTeam',)") == "other"  # Preserved
    
    def test_invalidate_by_team_multiple_entries(self):
        """Test invalidating multiple entries for the same team."""
        cache = SelectiveCache()
        
        # Multiple entries for Team1
        cache.set("('Team1',)", "hash_result")
        cache.set("('Team1', 'correlation')", "correlation_result")
        cache.set("('Team1', 'stats')", "stats_result")
        
        # Entries for other teams
        cache.set("('Team2',)", "team2_result")
        cache.set("('Team11', 'stats')", "team11_result")
        
        # Invalidate Team1
        invalidated = cache.invalidate_by_team("Team1")
        
        assert invalidated == 3  # Should invalidate 3 Team1 entries
        assert cache.get("('Team1',)") is None
        assert cache.get("('Team1', 'correlation')") is None
        assert cache.get("('Team1', 'stats')") is None
        
        # Other teams should be preserved
        assert cache.get("('Team2',)") == "team2_result"
        assert cache.get("('Team11', 'stats')") == "team11_result"
    
    def test_substring_matching_bug_fix(self):
        """
        Test the specific bug fix: ensure Team1 invalidation doesn't affect Team11, Team21, etc.
        This is the core test for the reported bug.
        """
        cache = SelectiveCache()
        
        # Set up cache entries with teams that contain "Team1" as substring
        test_cases = [
            ("Team1", "Team1 should be invalidated"),
            ("Team11", "Team11 should NOT be invalidated"), 
            ("Team21", "Team21 should NOT be invalidated"),
            ("MyTeam1", "MyTeam1 should NOT be invalidated"),
            ("Team1_backup", "Team1_backup should NOT be invalidated"),
            ("SuperTeam1", "SuperTeam1 should NOT be invalidated"),
        ]
        
        # Populate cache
        for team_name, description in test_cases:
            cache.set(f"('{team_name}',)", description)
            cache.set(f"('{team_name}', 'extra')", f"{description} - extra")
        
        # Invalidate Team1
        invalidated = cache.invalidate_by_team("Team1")
        
        # Should only invalidate exactly 2 entries for "Team1"
        assert invalidated == 2
        
        # Verify Team1 entries are gone
        assert cache.get("('Team1',)") is None
        assert cache.get("('Team1', 'extra')") is None
        
        # Verify all other teams are preserved
        for team_name, description in test_cases[1:]:  # Skip Team1
            assert cache.get(f"('{team_name}',)") == description
            assert cache.get(f"('{team_name}', 'extra')") == f"{description} - extra"
    
    def test_special_characters_in_team_names(self):
        """Test invalidation works correctly with special characters in team names."""
        cache = SelectiveCache()
        
        special_teams = [
            "Team.1",    # Dot
            "Team+1",    # Plus  
            "Team[1]",   # Brackets
            "Team(1)",   # Parentheses
            "Team^1",    # Caret
            "Team$1",    # Dollar
        ]
        
        # Populate cache
        for team in special_teams:
            cache.set(f"('{team}',)", f"result_{team}")
        
        # Also add similar teams that should NOT be invalidated
        cache.set("('Team.11',)", "should_not_be_invalidated")
        cache.set("('Team+11',)", "should_not_be_invalidated")
        
        # Invalidate Team.1
        invalidated = cache.invalidate_by_team("Team.1")
        assert invalidated == 1
        assert cache.get("('Team.1',)") is None
        assert cache.get("('Team.11',)") == "should_not_be_invalidated"
        
        # Invalidate Team+1  
        invalidated = cache.invalidate_by_team("Team+1")
        assert invalidated == 1
        assert cache.get("('Team+1',)") is None
        assert cache.get("('Team+11',)") == "should_not_be_invalidated"


class TestSelectiveCacheDecorator:
    """Test the selective_cache decorator functionality."""
    
    def test_decorator_basic_functionality(self):
        """Test that the decorator provides caching functionality."""
        test_cache = SelectiveCache()
        call_count = 0
        
        @selective_cache(test_cache)
        def expensive_function(team_name, value):
            nonlocal call_count
            call_count += 1
            return f"result_{team_name}_{value}"
        
        # First call should execute function
        result1 = expensive_function("Team1", "test")
        assert result1 == "result_Team1_test"
        assert call_count == 1
        
        # Second call should use cache
        result2 = expensive_function("Team1", "test")
        assert result2 == "result_Team1_test"
        assert call_count == 1  # Should not increase
        
        # Different parameters should execute function
        result3 = expensive_function("Team2", "test")
        assert result3 == "result_Team2_test"
        assert call_count == 2
    
    def test_decorator_team_invalidation(self):
        """Test that decorator supports team-specific invalidation."""
        test_cache = SelectiveCache()
        call_count = 0
        
        @selective_cache(test_cache)
        def team_function(team_name):
            nonlocal call_count
            call_count += 1
            return f"computed_{team_name}_{call_count}"
        
        # Populate cache for multiple teams
        result_team1 = team_function("Team1")
        result_team2 = team_function("Team2")
        assert call_count == 2
        
        # Verify caching works
        assert team_function("Team1") == result_team1
        assert team_function("Team2") == result_team2
        assert call_count == 2  # Still 2, used cache
        
        # Invalidate Team1 only
        invalidated = team_function.cache_invalidate_team("Team1")
        assert invalidated == 1
        
        # Team1 should recompute, Team2 should use cache
        new_result_team1 = team_function("Team1")
        cached_result_team2 = team_function("Team2")
        
        assert new_result_team1 != result_team1  # Should be different (recomputed)
        assert cached_result_team2 == result_team2  # Should be same (cached)
        assert call_count == 3  # Only Team1 was recomputed


class TestMakeCacheKey:
    """Test the _make_cache_key function."""
    
    def test_string_arguments(self):
        """Test cache key generation with string arguments."""
        key = _make_cache_key("Team1", "arg2")
        assert key == "('Team1', 'arg2')"
    
    def test_mixed_arguments(self):
        """Test cache key generation with mixed argument types."""
        key = _make_cache_key("Team1", 123, True, None)
        assert key == "('Team1', 123, True, None)"
    
    def test_keyword_arguments(self):
        """Test cache key generation with keyword arguments."""
        key = _make_cache_key("Team1", value=123, flag=True)
        assert key == "('Team1', flag=True, value=123)"
    
    def test_special_characters(self):
        """Test cache key generation with special characters."""
        key = _make_cache_key("Team.1", "arg+2")
        assert key == "('Team.1', 'arg+2')"


class TestIntegrationWithDashboardFunctions:
    """Integration tests with actual dashboard functions."""
    
    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        """Set up mocks for dashboard functions."""
        # Mock database and app context requirements
        with patch('src.sockets.dashboard._get_team_id_from_name') as mock_get_id:
            mock_get_id.return_value = None  # Return None to avoid DB queries
            yield
    
    def test_invalidate_team_caches_function(self):
        """Test the global invalidate_team_caches function."""
        # Clear all caches first
        clear_team_caches()
        
        # Import the cache instances
        from src.sockets.dashboard import _hash_cache, _correlation_cache
        
        # Manually populate some cache entries
        _hash_cache.set("('Team1',)", ("hash1", "hash2"))
        _hash_cache.set("('Team11',)", ("hash11", "hash22"))
        _correlation_cache.set("('Team1',)", "correlation_data")
        _correlation_cache.set("('Team2',)", "correlation_data_2")
        
        # Test selective invalidation
        invalidate_team_caches("Team1")
        
        # Verify Team1 caches are cleared, but Team11 and Team2 are preserved
        assert _hash_cache.get("('Team1',)") is None
        assert _hash_cache.get("('Team11',)") == ("hash11", "hash22")  # Should be preserved!
        assert _correlation_cache.get("('Team1',)") is None
        assert _correlation_cache.get("('Team2',)") == "correlation_data_2"  # Should be preserved!
    
    def test_clear_team_caches_function(self):
        """Test the global clear_team_caches function."""
        from src.sockets.dashboard import _hash_cache, _correlation_cache
        
        # Populate caches
        _hash_cache.set("('Team1',)", "data1")
        _hash_cache.set("('Team2',)", "data2")
        _correlation_cache.set("('Team1',)", "corr1")
        
        # Clear all caches
        clear_team_caches()
        
        # Verify all caches are empty
        assert _hash_cache.get("('Team1',)") is None
        assert _hash_cache.get("('Team2',)") is None
        assert _correlation_cache.get("('Team1',)") is None