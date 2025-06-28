"""
Dashboard functionality for the CHSH Game.

This module serves as the main entry point for dashboard functionality,
importing and re-exporting functions from the modular dashboard components.
"""

# Import all functions from the modular dashboard components
from .dashboard_cache import (
    invalidate_team_caches,
    clear_team_caches,
    force_clear_all_caches
)

from .dashboard_statistics import (
    compute_team_hashes,
    compute_correlation_matrix,
    compute_success_metrics,
    _calculate_team_statistics,
    _calculate_success_statistics
)

from .dashboard_handlers import (
    on_keep_alive,
    on_set_teams_streaming,
    on_request_teams_update,
    on_toggle_game_mode,
    on_dashboard_join,
    on_start_game,
    on_pause_game,
    on_restart_game,
    handle_dashboard_disconnect,
    dashboard_teams_streaming
)

from .dashboard_utils import (
    get_all_teams,
    emit_dashboard_team_update,
    emit_dashboard_full_update,
    get_dashboard_data,
    download_csv
)

# Re-export all functions for backward compatibility
__all__ = [
    # Cache functions
    'invalidate_team_caches',
    'clear_team_caches',
    'force_clear_all_caches',
    
    # Statistics functions
    'compute_team_hashes',
    'compute_correlation_matrix',
    'compute_success_metrics',
    '_calculate_team_statistics',
    '_calculate_success_statistics',
    
    # Handler functions  
    'on_keep_alive',
    'on_set_teams_streaming',
    'on_request_teams_update',
    'on_toggle_game_mode',
    'on_dashboard_join',
    'on_start_game',
    'on_pause_game',
    'on_restart_game',
    'handle_dashboard_disconnect',
    'dashboard_teams_streaming',
    
    # Utility functions
    'get_all_teams',
    'emit_dashboard_team_update',
    'emit_dashboard_full_update',
    'get_dashboard_data',
    'download_csv'
]
