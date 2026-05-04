#!/usr/bin/env python
"""Generate an AMD evidence pack markdown from benchmark JSON."""

import argparse
import sys
from pathlib import Path

# Ensure imports resolve when running from scripts/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.benchmarking import build_evidence_pack, generate_benchmark_markdown, load_benchmark_results


def main():
    parser = argparse.ArgumentParser(
        description="Generate AMD evidence pack from benchmark results"
    )
    parser.add_argument(
        "--input",
        default="data/amd_benchmark_results.json",
        help="Path to benchmark JSON",
    )
    parser.add_argument(
        "--output",
        default="reports/amd_evidence_pack.md",
        help="Output markdown path",
    )
    args = parser.parse_args()

    summary = load_benchmark_results(args.input)
    if summary is None:
        print(f"Could not load benchmark results from {args.input}")
        sys.exit(1)

    evidence = build_evidence_pack(summary)
    md = generate_benchmark_markdown(evidence)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"Wrote evidence pack to {out}")


if __name__ == "__main__":
    main()
