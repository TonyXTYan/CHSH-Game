"""
Dashboard package that re-exports all functionality for backward compatibility.

This ensures that existing imports like `from src.sockets.dashboard import ...` continue to work.
"""

# Re-export everything from the split modules for backward compatibility

# Database models and state that tests expect to mock
from src.models.quiz_models import Teams, Answers, PairQuestionRounds, ItemEnum
from src.state import state

# Flask and SocketIO components that tests expect to mock
from src.config import socketio, app, db
from flask_socketio import emit
from flask import request
import time
import logging

# Game logic functions and constants that tests expect to mock
from src.game_logic import start_new_round_for_pair, QUESTION_ITEMS, TARGET_COMBO_REPEATS

# Create logger for compatibility
logger = logging.getLogger(__name__)

# Cache system
from .cache_system import (
    SelectiveCache, selective_cache, _safe_dashboard_operation,
    clear_team_caches, force_clear_all_caches, invalidate_team_caches,
    _hash_cache, _correlation_cache, _success_cache, _classic_stats_cache, _new_stats_cache, _team_process_cache,
    CACHE_SIZE, REFRESH_DELAY_QUICK, REFRESH_DELAY_FULL, MIN_STD_DEV,
    _dashboard_lock, _last_refresh_time, _cached_teams_result,
    _last_team_update_time, _last_full_update_time, _cached_team_metrics, _cached_full_metrics,
    _make_cache_key
)

# Client management
from .client_management import (
    dashboard_last_activity, dashboard_teams_streaming,
    _atomic_client_update, _periodic_cleanup_dashboard_clients,
    on_keep_alive, on_set_teams_streaming, on_request_teams_update,
    handle_dashboard_disconnect
)

# Computations
from .computations import (
    _get_team_id_from_name, compute_team_hashes, compute_success_metrics, compute_correlation_matrix,
    _calculate_team_statistics, _calculate_success_statistics
)

# Team processing
from .team_processing import (
    _compute_team_hashes_optimized, _compute_correlation_matrix_optimized, _compute_success_metrics_optimized,
    _calculate_team_statistics_from_data, _calculate_success_statistics_from_data,
    _process_single_team_optimized, _process_single_team, get_all_teams
)

# Events
from .events import (
    on_toggle_game_mode, emit_dashboard_team_update, emit_dashboard_full_update,
    on_dashboard_join, on_start_game, on_pause_game, on_restart_game
)

# Routes (these are automatically registered when imported)
from . import routes

# Make sure to expose the route functions for compatibility
from .routes import get_dashboard_data, download_csv

# Re-export all public functions and variables
__all__ = [
    # Database models and state
    'Teams', 'Answers', 'PairQuestionRounds', 'ItemEnum', 'state',
    
    # Flask and SocketIO
    'socketio', 'app', 'db', 'emit', 'request', 'time', 'logger',
    
    # Game logic
    'start_new_round_for_pair', 'QUESTION_ITEMS', 'TARGET_COMBO_REPEATS',
    
    # Cache system
    'SelectiveCache', 'selective_cache', '_safe_dashboard_operation',
    'clear_team_caches', 'force_clear_all_caches', 'invalidate_team_caches',
    '_hash_cache', '_correlation_cache', '_success_cache', '_classic_stats_cache', '_new_stats_cache', '_team_process_cache',
    'CACHE_SIZE', 'REFRESH_DELAY_QUICK', 'REFRESH_DELAY_FULL', 'MIN_STD_DEV',
    '_dashboard_lock', '_last_refresh_time', '_cached_teams_result',
    '_last_team_update_time', '_last_full_update_time', '_cached_team_metrics', '_cached_full_metrics',
    '_make_cache_key',
    
    # Client management
    'dashboard_last_activity', 'dashboard_teams_streaming',
    '_atomic_client_update', '_periodic_cleanup_dashboard_clients',
    'on_keep_alive', 'on_set_teams_streaming', 'on_request_teams_update',
    'handle_dashboard_disconnect',
    
    # Computations
    '_get_team_id_from_name', 'compute_team_hashes', 'compute_success_metrics', 'compute_correlation_matrix',
    '_calculate_team_statistics', '_calculate_success_statistics',
    
    # Team processing
    '_compute_team_hashes_optimized', '_compute_correlation_matrix_optimized', '_compute_success_metrics_optimized',
    '_calculate_team_statistics_from_data', '_calculate_success_statistics_from_data',
    '_process_single_team_optimized', '_process_single_team', 'get_all_teams',
    
    # Events
    'on_toggle_game_mode', 'emit_dashboard_team_update', 'emit_dashboard_full_update',
    'on_dashboard_join', 'on_start_game', 'on_pause_game', 'on_restart_game',
    
    # Routes
    'get_dashboard_data', 'download_csv'
]