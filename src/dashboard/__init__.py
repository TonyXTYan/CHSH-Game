# Dashboard package for CHSH Game application
# Broken down from the overly large src/sockets/dashboard.py file

# Import key functions and classes that need to be accessible
from .cache_system import (
    SelectiveCache, 
    selective_cache, 
    _make_cache_key,
    _hash_cache,
    _correlation_cache,
    _success_cache,
    _classic_stats_cache,
    _new_stats_cache,
    _team_process_cache
)

from .client_management import (
    _safe_dashboard_operation,
    _atomic_client_update,
    _get_team_id_from_name,
    _periodic_cleanup_dashboard_clients,
    dashboard_last_activity,
    dashboard_teams_streaming
)

from .computations import (
    compute_team_hashes,
    compute_success_metrics,
    compute_correlation_matrix,
    compute_correlation_stats
)

from .statistics import (
    _calculate_team_statistics,
    _calculate_success_statistics,
    _compute_team_hashes_optimized,
    _compute_correlation_matrix_optimized,
    _compute_success_metrics_optimized,
    _calculate_team_statistics_from_data,
    _calculate_success_statistics_from_data
)

from .team_processing import (
    _process_single_team_optimized,
    _process_single_team,
    get_all_teams
)

from .cache_management import (
    invalidate_team_caches,
    clear_team_caches,
    force_clear_all_caches
)

from .update_emitters import (
    emit_dashboard_team_update,
    emit_dashboard_full_update
)

from .socket_handlers import (
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

from .http_routes import (
    get_dashboard_data,
    download_csv
)

__all__ = [
    # Cache system
    'SelectiveCache', 'selective_cache', '_make_cache_key',
    '_hash_cache', '_correlation_cache', '_success_cache',
    '_classic_stats_cache', '_new_stats_cache', '_team_process_cache',
    
    # Client management
    '_safe_dashboard_operation', '_atomic_client_update',
    '_get_team_id_from_name', '_periodic_cleanup_dashboard_clients',
    'dashboard_last_activity', 'dashboard_teams_streaming',
    
    # Computations
    'compute_team_hashes', 'compute_success_metrics',
    'compute_correlation_matrix', 'compute_correlation_stats',
    
    # Statistics
    '_calculate_team_statistics', '_calculate_success_statistics',
    '_compute_team_hashes_optimized', '_compute_correlation_matrix_optimized',
    '_compute_success_metrics_optimized', '_calculate_team_statistics_from_data',
    '_calculate_success_statistics_from_data',
    
    # Team processing
    '_process_single_team_optimized', '_process_single_team', 'get_all_teams',
    
    # Cache management
    'invalidate_team_caches', 'clear_team_caches', 'force_clear_all_caches',
    
    # Update emitters
    'emit_dashboard_team_update', 'emit_dashboard_full_update',
    
    # Socket handlers
    'on_keep_alive', 'on_set_teams_streaming', 'on_request_teams_update',
    'on_toggle_game_mode', 'on_dashboard_join', 'on_start_game',
    'on_pause_game', 'on_restart_game', 'handle_dashboard_disconnect',
    
    # HTTP routes
    'get_dashboard_data', 'download_csv'
]