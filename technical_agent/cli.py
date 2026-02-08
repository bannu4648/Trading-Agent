"""Command-line interface for the technical analyst agent."""

from __future__ import annotations

import argparse
import json
from typing import List

from .agent import TechnicalAnalystAgent
from .config import config_from_env
from .utils.serialization import to_serializable


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Technical analyst agent runner")
    parser.add_argument("--tickers", required=True, help="Comma-separated tickers")
    parser.add_argument("--start", dest="start_date", required=False, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", dest="end_date", required=False, help="End date YYYY-MM-DD")
    parser.add_argument("--interval", default="1d", help="Data interval (default 1d)")
    parser.add_argument(
        "--extra-signal-module",
        action="append",
        default=[],
        help="Additional Python module path to load custom signals",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Disable LLM summaries and use rule-based summaries instead",
    )
    parser.add_argument("--output", help="Optional output file path")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    tickers: List[str] = [t.strip() for t in args.tickers.split(",") if t.strip()]

    config = config_from_env()
    config.extra_signal_modules = args.extra_signal_module
    if args.no_llm:
        config.enable_llm_summary = False

    agent = TechnicalAnalystAgent(config=config)
    result = agent.run(
        tickers=tickers,
        start_date=args.start_date,
        end_date=args.end_date,
        interval=args.interval,
    )
    output_json = json.dumps(result, default=to_serializable, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(output_json)
    else:
        print(output_json)


if __name__ == "__main__":
    main()
