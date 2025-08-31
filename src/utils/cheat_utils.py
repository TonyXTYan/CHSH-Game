"""
Shared utilities for cheat detection and handling.
Extracted to avoid code duplication across modules.
"""
import re
from typing import Literal

# Cheat detection regex
CHEAT_RE = re.compile(r'^cheat-(com|hint|tony|kevin)(?:$|[-_\s].*)', re.IGNORECASE)

# Synthetic partner session ID format template
SYNTHETIC_SID_TEMPLATE = "auto_{cheat_type}_t{team_id}_r{round_id}_p{player_slot}_{timestamp}"

def parse_cheat_type(team_name: str) -> Literal["none", "com", "hint", "tony", "kevin"]:
    """
    Parse cheat type from team name.
    Returns: "none", "com", "hint", "tony", or "kevin"
    """
    try:
        name = (team_name or "").strip()
        m = CHEAT_RE.match(name)
        if not m:
            return "none"
        return m.group(1).lower()
    except Exception:
        # Never throw from parsing; default to no-cheat on any error
        return "none"

def create_synthetic_partner_sid(cheat_type: str, team_id: int, round_id: int, player_slot: int, timestamp: int) -> str:
    """
    Create a synthetic partner session ID for auto-filled answers.
    
    Args:
        cheat_type: The type of cheat ("tony" or "kevin")
        team_id: The team ID
        round_id: The round ID
        player_slot: The player slot (1 or 2)
        timestamp: Timestamp in microseconds for uniqueness
        
    Returns:
        Formatted synthetic session ID
    """
    return SYNTHETIC_SID_TEMPLATE.format(
        cheat_type=cheat_type,
        team_id=team_id,
        round_id=round_id,
        player_slot=player_slot,
        timestamp=timestamp
    )

def is_synthetic_sid(sid: str) -> bool:
    """Check if a session ID is synthetic (auto-generated)."""
    return sid.startswith("auto_")