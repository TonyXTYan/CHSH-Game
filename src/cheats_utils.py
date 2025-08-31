import logging
import re
from typing import Literal

logger = logging.getLogger(__name__)

CHEAT_RE = re.compile(r'^cheat-(com|hint|tony|kevin)(?:$|[-_\s].*)', re.IGNORECASE)

def parse_cheat_type(team_name: str) -> Literal['none','com','hint','tony','kevin']:
    """Parse the cheat type from a team name.

    Returns one of 'com', 'hint', 'tony', 'kevin', or 'none' if no cheat prefix is detected.
    Parsing is case-insensitive and tolerant of suffixes after the cheat type.
    Any errors result in a safe default of 'none'.
    """
    try:
        name = (team_name or '').strip()
        m = CHEAT_RE.match(name)
        if not m:
            return 'none'
        return m.group(1).lower()
    except Exception as e:
        logger.warning(f"Failed to parse cheat type from {team_name!r}: {e}")
        return 'none'
