"""
Cache management module for dashboard functionality.
Contains functions for invalidating and clearing caches.
"""

import logging
from typing import Optional, List, Dict, Any

from .cache_system import (
    _hash_cache, _correlation_cache, _success_cache, 
    _classic_stats_cache, _new_stats_cache, _team_process_cache
)
from .client_management import _safe_dashboard_operation, _periodic_cleanup_dashboard_clients
from .computations import compute_team_hashes, compute_correlation_matrix, compute_success_metrics
from .statistics import _calculate_team_statistics, _calculate_success_statistics
from .team_processing import _process_single_team

# Configure logging
logger = logging.getLogger(__name__)

# Import global state variables that need to be managed
# These are imported to allow clearing of throttling state
from .team_processing import _last_refresh_time, _cached_teams_result

# Global throttling state for dashboard update functions with differentiated timing
_last_team_update_time = 0
_last_full_update_time = 0
_cached_team_metrics: Optional[Dict[str, Any]] = None
_cached_full_metrics: Optional[Dict[str, Any]] = None


def invalidate_team_caches(team_name: str) -> None:
    """
    Selectively invalidate caches for a specific team only.
    Preserves cached results for all other teams.
    Thread-safe operation with proper error handling.
    """
    global _cached_team_metrics, _cached_full_metrics
    
    try:
        with _safe_dashboard_operation():
            # Selectively invalidate team-specific caches
            total_invalidated = 0
            total_invalidated += compute_team_hashes.cache_invalidate_team(team_name)
            total_invalidated += compute_correlation_matrix.cache_invalidate_team(team_name)
            total_invalidated += compute_success_metrics.cache_invalidate_team(team_name)
            total_invalidated += _calculate_team_statistics.cache_invalidate_team(team_name)
            total_invalidated += _calculate_success_statistics.cache_invalidate_team(team_name)
            total_invalidated += _process_single_team.cache_invalidate_team(team_name)
            
            # Invalidate global throttling caches that may contain this team's data
            # but preserve caches that don't contain this team
            from .team_processing import _cached_teams_result, _last_refresh_time
            if _cached_teams_result is not None:
                # Check if this team is in the cached result
                team_in_cache = any(team.get('team_name') == team_name for team in _cached_teams_result)
                if team_in_cache:
                    # Clear the cache by setting module-level variables
                    import src.dashboard.team_processing as team_proc_module
                    team_proc_module._cached_teams_result = None
                    team_proc_module._last_refresh_time = 0
                    logger.debug(f"Cleared get_all_teams cache containing team {team_name}")
            
            # Clear throttling caches if they contained this team's data
            if _cached_team_metrics is not None and 'cached_teams' in _cached_team_metrics:
                cached_teams = _cached_team_metrics.get('cached_teams', [])
                if any(team.get('team_name') == team_name for team in cached_teams):
                    # Clear the cache by setting module-level variables
                    import src.dashboard.cache_management as cache_mgmt_module
                    cache_mgmt_module._cached_team_metrics = None
                    cache_mgmt_module._last_team_update_time = 0
                    logger.debug(f"Cleared team metrics cache containing team {team_name}")
            
            if _cached_full_metrics is not None and 'cached_teams' in _cached_full_metrics:
                cached_teams = _cached_full_metrics.get('cached_teams', [])
                if any(team.get('team_name') == team_name for team in cached_teams):
                    # Clear the cache by setting module-level variables
                    import src.dashboard.cache_management as cache_mgmt_module
                    cache_mgmt_module._cached_full_metrics = None
                    cache_mgmt_module._last_full_update_time = 0
                    logger.debug(f"Cleared full metrics cache containing team {team_name}")
            
            logger.debug(f"Selectively invalidated {total_invalidated} cache entries for team {team_name}")
            
    except Exception as e:
        logger.error(f"Error invalidating team caches for {team_name}: {str(e)}", exc_info=True)


def clear_team_caches() -> None:
    """
    Clear all team-related caches and throttling state to prevent stale data.
    Thread-safe operation with proper error handling to prevent lock issues.
    
    Note: This function now clears ALL caches. For selective invalidation of
    specific teams, use invalidate_team_caches(team_name) instead.
    """
    global _last_team_update_time, _last_full_update_time, _cached_team_metrics, _cached_full_metrics
    
    try:
        with _safe_dashboard_operation():
            # Clear all selective caches
            compute_team_hashes.cache_clear()
            compute_correlation_matrix.cache_clear()
            compute_success_metrics.cache_clear()
            _calculate_team_statistics.cache_clear()
            _calculate_success_statistics.cache_clear()
            _process_single_team.cache_clear()
            
            # Clear get_all_teams cache since it depends on caches we just cleared
            import src.dashboard.team_processing as team_proc_module
            team_proc_module._last_refresh_time = 0
            team_proc_module._cached_teams_result = None
            
            # FIXED: Reset throttling timers when cached teams data is removed to prevent inconsistent state
            # When we remove cached teams data, we must also reset throttling to avoid serving
            # empty teams list with stale metrics in subsequent throttled calls
            if _cached_team_metrics is not None and 'cached_teams' in _cached_team_metrics:
                # Reset team update throttling to ensure consistency
                _last_team_update_time = 0
                _cached_team_metrics = None
                
            if _cached_full_metrics is not None and 'cached_teams' in _cached_full_metrics:
                # Reset full update throttling to ensure consistency
                _last_full_update_time = 0
                _cached_full_metrics = None
            
            logger.debug("Cleared all team caches and reset throttling state to ensure data consistency")
            
        # Perform periodic cleanup of dashboard client data
        # Note: This is outside the main lock to prevent potential deadlocks
        _periodic_cleanup_dashboard_clients()
        
    except Exception as e:
        logger.error(f"Error clearing team caches: {str(e)}", exc_info=True)


def force_clear_all_caches() -> None:
    """
    Force clear ALL caches including throttling state. Use only when data integrity requires it.
    This is more aggressive than clear_team_caches() and should be used sparingly.
    """
    global _last_team_update_time, _last_full_update_time, _cached_team_metrics, _cached_full_metrics
    
    try:
        with _safe_dashboard_operation():
            # Clear all selective caches
            compute_team_hashes.cache_clear()
            compute_correlation_matrix.cache_clear()
            compute_success_metrics.cache_clear()
            _calculate_team_statistics.cache_clear()
            _calculate_success_statistics.cache_clear()
            _process_single_team.cache_clear()
            
            # Force clear ALL throttling state
            import src.dashboard.team_processing as team_proc_module
            team_proc_module._last_refresh_time = 0
            team_proc_module._cached_teams_result = None
            _last_team_update_time = 0
            _last_full_update_time = 0
            _cached_team_metrics = None
            _cached_full_metrics = None
            
            logger.info("Force cleared all caches and throttling state")
            
        _periodic_cleanup_dashboard_clients()
        
    except Exception as e:
        logger.error(f"Error in force_clear_all_caches: {str(e)}", exc_info=True)