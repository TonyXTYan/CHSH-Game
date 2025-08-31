import logging
import re

logger = logging.getLogger(__name__)

CHEAT_RE = re.compile(r'^cheat-(com|hint|tony|kevin)(?:$|[-_\s].*)', re.IGNORECASE)

def parse_cheat_type(team_name: str) -> str:
    """Return cheat type extracted from team name or 'none'.

    Parsing is case-insensitive and tolerant of suffixes separated by
    dashes, underscores or whitespace. Any errors are swallowed and
    treated as no-cheat to avoid disrupting normal play.
    """
    try:
        name = (team_name or "").strip()
        match = CHEAT_RE.match(name)
        if not match:
            return "none"
        cheat = match.group(1).lower()
        logger.info("Cheat team detected", extra={"team_name": name, "cheat_type": cheat})
        return cheat
    except Exception:
        return "none"
