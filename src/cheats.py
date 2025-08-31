import re
from typing import Literal, Optional, Tuple
from src.models.quiz_models import ItemEnum

CHEAT_RE = re.compile(r"^cheat-(com|hint|tony|kevin)(?:$|[-_\s].*)", re.IGNORECASE)


def parse_cheat_type(team_name: Optional[str]) -> str:
    """Parse cheat type from team name.

    Returns one of 'com', 'hint', 'tony', 'kevin', or 'none'.
    Parsing is case-insensitive and tolerant of extra suffixes.
    """
    try:
        name = (team_name or "").strip()
        match = CHEAT_RE.match(name)
        if not match:
            return "none"
        return match.group(1).lower()
    except Exception:
        return "none"


def get_required_parity(
    p1_item: ItemEnum, p2_item: ItemEnum
) -> Literal["same", "different"]:
    """Determine the required parity for a pair of items."""
    try:
        items = {p1_item, p2_item}
        return "different" if ItemEnum.B in items and ItemEnum.Y in items else "same"
    except Exception:
        return "same"


def recommend_answers(
    parity: str, known_left: Optional[bool] = None, known_right: Optional[bool] = None
) -> Tuple[bool, bool]:
    """Recommend answers for players based on parity and known answers."""
    if parity not in {"same", "different"}:
        parity = "same"

    if known_left is not None:
        left = known_left
        right = known_left if parity == "same" else not known_left
        return left, right

    if known_right is not None:
        right = known_right
        left = known_right if parity == "same" else not known_right
        return left, right

    if parity == "same":
        return True, True
    return True, False
