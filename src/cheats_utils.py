import re
from typing import Optional, Tuple
from src.models.quiz_models import ItemEnum

CHEAT_RE = re.compile(r'^cheat-(com|hint|tony|kevin)(?:$|[^a-zA-Z].*)', re.IGNORECASE)

def parse_cheat_type(team_name: Optional[str]) -> str:
    """Parse team name for cheat prefix.

    Returns one of 'none', 'com', 'hint', 'tony', 'kevin'.
    Any parsing error results in 'none'.
    """
    try:
        name = (team_name or "").strip()
        m = CHEAT_RE.match(name)
        if not m:
            return "none"
        return m.group(1).lower()
    except Exception:
        return "none"

def get_required_parity(p1_item: ItemEnum, p2_item: ItemEnum) -> str:
    """Determine required parity for a pair of items.

    BY or YB => 'different', otherwise 'same'.
    """
    if ((p1_item == ItemEnum.B and p2_item == ItemEnum.Y) or
            (p1_item == ItemEnum.Y and p2_item == ItemEnum.B)):
        return "different"
    return "same"

def recommend_answers(
    p1_item: ItemEnum,
    p2_item: ItemEnum,
    p1_answer: Optional[bool] = None,
    p2_answer: Optional[bool] = None,
) -> Tuple[bool, bool]:
    """Recommend answers based on required parity and known responses."""
    parity = get_required_parity(p1_item, p2_item)
    if p1_answer is None and p2_answer is None:
        if parity == "same":
            return True, True
        return True, False
    if p1_answer is not None and p2_answer is None:
        if parity == "same":
            return p1_answer, p1_answer
        return p1_answer, not p1_answer
    if p2_answer is not None and p1_answer is None:
        if parity == "same":
            return p2_answer, p2_answer
        return not p2_answer, p2_answer
    # If both answers known, simply return them
    return bool(p1_answer), bool(p2_answer)
