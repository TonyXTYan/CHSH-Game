"""
Dashboard Client Management

This module handles dashboard client tracking, thread safety utilities,
and helper functions for managing dashboard client state.
"""

import threading
import logging
import weakref
from contextlib import contextmanager
from time import time
from typing import Dict, Optional
from src.state import state
from src.models.quiz_models import Teams

logger = logging.getLogger(__name__)

# Cache configuration and throttling constants
REFRESH_DELAY_QUICK = 1.0  # seconds - maximum refresh rate for team updates and data fetching
REFRESH_DELAY_FULL = 3.0  # seconds - maximum refresh rate for expensive full dashboard updates

# Dashboard client activity tracking for keep-alive functionality
dashboard_last_activity: Dict[str, float] = {}

# Per-client preference for teams data streaming (enabled/disabled)
dashboard_teams_streaming: Dict[str, bool] = {}

# Single lock for all dashboard operations to prevent deadlocks
# This lock protects:
# - Cache operations (LRU cache clearing, throttling state)
# - Dashboard client tracking (activity and streaming preferences)
# - All shared state modifications
_dashboard_lock = threading.RLock()

@contextmanager
def _safe_dashboard_operation():
    """
    Context manager for safe dashboard operations with proper error handling.
    Ensures lock is always released even if exceptions occur.
    """
    _dashboard_lock.acquire()
    try:
        yield
    except Exception as e:
        logger.error(f"Error in dashboard operation: {str(e)}", exc_info=True)
        raise
    finally:
        _dashboard_lock.release()

def _atomic_client_update(sid: str, activity_time: Optional[float] = None, 
                         streaming_enabled: Optional[bool] = None, 
                         remove: bool = False) -> None:
    """
    Atomically update dashboard client tracking data.
    Ensures both dictionaries are updated together to prevent inconsistencies.
    
    Args:
        sid: Client session ID
        activity_time: Time to set for last activity (if not None)
        streaming_enabled: Streaming preference to set (if not None)
        remove: If True, remove client from tracking dictionaries
    """
    with _safe_dashboard_operation():
        if remove:
            dashboard_last_activity.pop(sid, None)
            dashboard_teams_streaming.pop(sid, None)
            logger.debug(f"Atomically removed dashboard client data for {sid}")
        else:
            if activity_time is not None:
                dashboard_last_activity[sid] = activity_time
            if streaming_enabled is not None:
                dashboard_teams_streaming[sid] = streaming_enabled
            logger.debug(f"Atomically updated dashboard client data for {sid}")

def _get_team_id_from_name(team_name: str) -> Optional[int]:
    """Helper function to resolve team_name to team_id from state or database."""
    try:
        # First check active teams
        team_info = state.active_teams.get(team_name)
        if team_info and 'team_id' in team_info:
            return team_info['team_id']
        
        # Fall back to database lookup
        team = Teams.query.filter_by(team_name=team_name).first()
        return team.team_id if team else None
    except Exception as e:
        logger.error(f"Error getting team_id for team_name {team_name}: {str(e)}", exc_info=True)
        return None

def _periodic_cleanup_dashboard_clients() -> None:
    """
    Periodic cleanup of stale dashboard client data.
    Removes tracking for clients not in active dashboard_clients set.
    Thread-safe with atomic operations to prevent inconsistencies.
    """
    try:
        with _safe_dashboard_operation():
            # Get current active dashboard clients
            active_clients = set(state.dashboard_clients)
            
            # Clean up tracking dictionaries atomically
            stale_activity_clients = set(dashboard_last_activity.keys()) - active_clients
            stale_streaming_clients = set(dashboard_teams_streaming.keys()) - active_clients
            
            # Remove stale clients atomically
            for sid in stale_activity_clients:
                del dashboard_last_activity[sid]
                
            for sid in stale_streaming_clients:
                del dashboard_teams_streaming[sid]
                
            if stale_activity_clients or stale_streaming_clients:
                logger.info(f"Cleaned up {len(stale_activity_clients)} stale activity clients "
                           f"and {len(stale_streaming_clients)} stale streaming clients")
    except Exception as e:
        logger.error(f"Error in periodic cleanup: {str(e)}", exc_info=True)