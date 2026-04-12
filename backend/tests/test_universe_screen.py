"""Tests for universe.screen candidate selection."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SCREEN = Path(__file__).resolve().parent.parent / "universe" / "screen.py"
_spec = importlib.util.spec_from_file_location("universe_screen_under_test", _SCREEN)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
select_candidates_by_expected_return = _mod.select_candidates_by_expected_return


def test_select_candidates_union_top_and_bottom_pools() -> None:
    recs = [{"ticker": f"T{i}", "expected_return": float(i)} for i in range(10)]
    out = select_candidates_by_expected_return(recs, k_long=2, k_short=2, pool_mult=1)
    # pool_n = 4 → top T9..T6, bottom T3..T0
    assert set(out) == {f"T{i}" for i in range(10) if i <= 3 or i >= 6}


def test_max_candidates_caps_size() -> None:
    recs = [{"ticker": f"T{i}", "expected_return": float(i)} for i in range(20)]
    out = select_candidates_by_expected_return(
        recs, k_long=5, k_short=5, pool_mult=1, max_candidates=5
    )
    assert len(out) == 5
    # ceil(5/2)=3 best + floor(5/2)=2 worst → T19,T18,T17 and T0,T1
    assert out[:3] == ["T19", "T18", "T17"]
    assert set(out[3:]) == {"T0", "T1"}


def test_max_candidates_half_long_half_short_30() -> None:
    recs = [{"ticker": f"T{i:02d}", "expected_return": float(i)} for i in range(100)]
    out = select_candidates_by_expected_return(
        recs, k_long=5, k_short=5, pool_mult=3, max_candidates=30
    )
    assert len(out) == 30
    best15 = {f"T{i:02d}" for i in range(85, 100)}
    worst15 = {f"T{i:02d}" for i in range(15)}
    assert set(out) == best15 | worst15
    assert out[:15] == [f"T{i:02d}" for i in range(99, 84, -1)]


def test_empty_recommendations() -> None:
    assert select_candidates_by_expected_return([], k_long=3, k_short=3) == []


def test_object_style_recommendations() -> None:
    class R:
        def __init__(self, t: str, er: float) -> None:
            self.ticker = t
            self.expected_return = er

    recs = [R("AAA", 0.5), R("BBB", -0.2), R("CCC", 0.1)]
    out = select_candidates_by_expected_return(recs, k_long=1, k_short=1, pool_mult=1)
    assert set(out) == {"AAA", "BBB", "CCC"}
