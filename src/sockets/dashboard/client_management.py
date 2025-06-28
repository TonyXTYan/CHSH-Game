"""
Client management for dashboard connections.

Handles client tracking, keep-alive functionality, and streaming preferences.
"""

import logging
import weakref
from time import time
from typing import Dict, Any, Optional
from flask import request
from flask_socketio import emit

from src.config import socketio
from src.state import state
from .cache_system import _safe_dashboard_operation

logger = logging.getLogger(__name__)

# Dashboard client activity tracking for keep-alive functionality
dashboard_last_activity: Dict[str, float] = {}

# Per-client preference for teams data streaming (enabled/disabled)
dashboard_teams_streaming: Dict[str, bool] = {}

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

@socketio.on('keep_alive')
def on_keep_alive() -> None:
    """Handle dashboard client keep-alive ping to maintain connection tracking."""
    try:
        sid = request.sid  # type: ignore
        if sid in state.dashboard_clients:
            _atomic_client_update(sid, activity_time=time())
            emit('keep_alive_ack', to=sid)  # type: ignore
    except Exception as e:
        logger.error(f"Error in on_keep_alive: {str(e)}", exc_info=True)

@socketio.on('set_teams_streaming')
def on_set_teams_streaming(data: Dict[str, Any]) -> None:
    """Handle dashboard client preference for teams data streaming on/off."""
    try:
        sid = request.sid  # type: ignore
        if sid in state.dashboard_clients:
            enabled = data.get('enabled', False)
            _atomic_client_update(sid, streaming_enabled=enabled)
            logger.info(f"Dashboard client {sid} set teams streaming to: {enabled}")
    except Exception as e:
        logger.error(f"Error in on_set_teams_streaming: {str(e)}", exc_info=True)

@socketio.on('request_teams_update')
def on_request_teams_update() -> None:
    """Handle explicit request for teams data from streaming-enabled clients."""
    try:
        sid = request.sid  # type: ignore
        if sid in state.dashboard_clients and dashboard_teams_streaming.get(sid, False):
            # Import here to avoid circular imports
            from . import events
            # Send current teams data to this specific client
            events.emit_dashboard_full_update(client_sid=sid)
            logger.info(f"Sent teams update to dashboard client {sid}")
    except Exception as e:
        logger.error(f"Error in on_request_teams_update: {str(e)}", exc_info=True)

def handle_dashboard_disconnect(sid: str) -> None:
    """
    Handle dashboard client disconnect and cleanup tracking data.
    Called when a dashboard client disconnects to clean up their tracking state.
    """
    try:
        # Remove from dashboard clients set
        state.dashboard_clients.discard(sid)
        # Remove from tracking dictionaries
        _atomic_client_update(sid, remove=True)
        logger.info(f"Cleaned up dashboard client data for disconnected client: {sid}")
    except Exception as e:
        logger.error(f"Error handling dashboard disconnect for {sid}: {str(e)}", exc_info=True)