# Dashboard package initialization
# Re-exports all public functions to maintain compatibility with existing imports

# Cache management and operations
from .cache_management import (
    dashboard_last_activity,
    dashboard_teams_streaming,
    _atomic_client_update,
    _safe_dashboard_operation,
    invalidate_team_caches,
    clear_team_caches,
    force_clear_all_caches,
    _periodic_cleanup_dashboard_clients,
    SelectiveCache,
    selective_cache,
    _make_cache_key,
    REFRESH_DELAY_QUICK,
    REFRESH_DELAY_FULL,
    # Internal caches (for tests)
    _hash_cache,
    _correlation_cache,
    _success_cache,
    _classic_stats_cache,
    _new_stats_cache,
    _team_process_cache
)

# Team data processing
from .team_data import (
    compute_team_hashes,
    compute_correlation_matrix, 
    compute_success_metrics,
    _get_team_id_from_name
)

# Statistics calculations
from .statistics import (
    _calculate_team_statistics,
    _calculate_success_statistics
)

# Team processing and data retrieval
from .team_processing import (
    get_all_teams,
    _process_single_team,
    emit_dashboard_team_update,
    emit_dashboard_full_update
)

# Socket event handlers
from .events import (
    on_keep_alive,
    on_set_teams_streaming,
    on_request_teams_update,
    on_toggle_game_mode,
    on_dashboard_join,
    on_start_game,
    on_pause_game,
    on_restart_game,
    handle_dashboard_disconnect
)

# HTTP routes are imported automatically via decorators in routes.py
from . import routes

# This ensures all modules are loaded and their decorators are registered
__all__ = [
    # Cache management
    'dashboard_last_activity',
    'dashboard_teams_streaming', 
    '_atomic_client_update',
    '_safe_dashboard_operation',
    'invalidate_team_caches',
    'clear_team_caches',
    'force_clear_all_caches',
    '_periodic_cleanup_dashboard_clients',
    'SelectiveCache',
    'selective_cache',
    '_make_cache_key',
    'REFRESH_DELAY_QUICK',
    'REFRESH_DELAY_FULL',
    '_hash_cache',
    '_correlation_cache',
    '_success_cache',
    '_classic_stats_cache',
    '_new_stats_cache',
    '_team_process_cache',
    
    # Team data processing
    'compute_team_hashes',
    'compute_correlation_matrix',
    'compute_success_metrics',
    '_get_team_id_from_name',
    
    # Statistics
    '_calculate_team_statistics',
    '_calculate_success_statistics',
    
    # Team processing
    'get_all_teams',
    '_process_single_team',
    'emit_dashboard_team_update',
    'emit_dashboard_full_update',
    
    # Events
    'on_keep_alive',
    'on_set_teams_streaming',
    'on_request_teams_update', 
    'on_toggle_game_mode',
    'on_dashboard_join',
    'on_start_game',
    'on_pause_game',
    'on_restart_game',
    'handle_dashboard_disconnect'
]