"""
Screen a large universe down to a candidate list using formula-only rankings.

Used by ``run_daily_paper_trade`` and ``run_sp500_screened_job``: sort by
``expected_return`` (from ``build_research_output(..., use_llm=False)``), then
take the union of the top and bottom ``pool_n`` names.
"""
from __future__ import annotations

from typing import Any, List, Sequence


def _ticker(rec: Any) -> str:
    if isinstance(rec, dict):
        return str(rec.get("ticker", "")).strip().upper()
    return str(getattr(rec, "ticker", "")).strip().upper()


def _expected_return(rec: Any) -> float:
    if isinstance(rec, dict):
        try:
            return float(rec.get("expected_return", 0.0))
        except (TypeError, ValueError):
            return 0.0
    try:
        return float(getattr(rec, "expected_return", 0.0))
    except (TypeError, ValueError):
        return 0.0


def select_candidates_by_expected_return(
    recommendations: Sequence[Any],
    *,
    k_long: int,
    k_short: int,
    pool_mult: int = 3,
    max_candidates: int | None = None,
) -> List[str]:
    """
    Return sorted unique tickers: union of top ``pool_n`` and bottom ``pool_n``
    by expected return (descending sort).

    ``pool_n = (k_long + k_short) * max(1, pool_mult)``, matching
    ``run_daily_paper_trade`` behaviour.

    If ``max_candidates`` is set to ``N``, take the **best** ``ceil(N/2)`` names by
    expected return (long-candidate side), then the **worst** ``floor(N/2)`` (short-candidate
    side), de-duplicated — e.g. ``N=30`` → 15 top + 15 bottom from the formula ranking
    (technical-driven when ``use_llm=False``).
    """
    recs = list(recommendations)
    if not recs:
        return []

    pool_n = max(0, int((int(k_long) + int(k_short)) * max(1, int(pool_mult))))
    prelim_sorted = sorted(recs, key=_expected_return, reverse=True)
    top_pool = [_ticker(r) for r in prelim_sorted[:pool_n]]
    bot_pool = [_ticker(r) for r in prelim_sorted[-pool_n:]]

    cap = int(max_candidates) if max_candidates is not None and max_candidates > 0 else None

    if cap is None:
        out: List[str] = []
        seen: set[str] = set()
        for t in top_pool + bot_pool:
            if not t or t in seen:
                continue
            seen.add(t)
            out.append(t)
        return out

    # Explicit long-tail / short-tail split for the research pool (not alternating).
    half_long = (cap + 1) // 2
    half_short = cap // 2
    seen: set[str] = set()
    out: List[str] = []

    for r in prelim_sorted[:half_long]:
        t = _ticker(r)
        if t and t not in seen:
            seen.add(t)
            out.append(t)

    for r in reversed(prelim_sorted[-half_short:] if half_short else []):
        t = _ticker(r)
        if t and t not in seen:
            seen.add(t)
            out.append(t)

    return out
