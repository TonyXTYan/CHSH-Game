from src.sockets.dashboard import _is_aqmjoe_success


def test_aqmjoe_food_food_never_both_peas():
    assert _is_aqmjoe_success('X', 'Y', True, True) is False  # Peas, Peas -> fail
    assert _is_aqmjoe_success('X', 'Y', True, False) is True   # Peas, Carrots -> ok
    assert _is_aqmjoe_success('X', 'X', False, False) is True  # Carrots, Carrots -> ok


def test_aqmjoe_mixed_color_food_green_requires_peas():
    # Color is Green -> Food must be Peas
    assert _is_aqmjoe_success('A', 'X', True, True) is True    # Green, Peas -> ok
    assert _is_aqmjoe_success('A', 'X', True, False) is False  # Green, Carrots -> fail
    # Red <-> Carrots succeeds (optional symmetry in design)
    assert _is_aqmjoe_success('B', 'Y', False, False) is True  # Red, Carrots -> ok


def test_aqmjoe_color_color_neutral_success():
    assert _is_aqmjoe_success('A', 'B', True, True) is True
    assert _is_aqmjoe_success('A', 'A', False, True) is True
