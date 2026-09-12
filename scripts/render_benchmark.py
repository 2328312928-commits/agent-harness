from __future__ import annotations

import argparse
import json
from pathlib import Path

from agent_harness.domain.models import EvalRunSummary
from scripts.run_benchmark import render_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a benchmark report from JSON.")
    parser.add_argument("input")
    parser.add_argument("output")
    args = parser.parse_args()

    summary = EvalRunSummary.model_validate(
        json.loads(Path(args.input).read_text(encoding="utf-8"))
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_report(summary), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()

