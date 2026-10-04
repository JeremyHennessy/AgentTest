from __future__ import annotations

import json
from pathlib import Path

from world2_reachability import enumerate_reachability


def main() -> int:
    report = enumerate_reachability(
        seeds=(1, 2, 3, 4, 5),
        horizon=8,
        max_sequences=50000,
    )
    output = Path("artifacts/world2_reachability_report.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "sequence_count": report["sequence_count"],
        "phenomenon_path_counts": report["phenomenon_path_counts"],
        "artifact": str(output),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
