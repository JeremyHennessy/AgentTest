from __future__ import annotations

import json
from pathlib import Path

from world2_reachability import enumerate_reachability, sample_reachability


def main() -> int:
    report = {
        "enumerated": enumerate_reachability(
            seeds=(1, 2, 3, 4, 5),
            horizon=8,
            max_sequences=50000,
        ),
        "sampled": sample_reachability(
            seeds=(1, 2, 3, 4, 5, 6, 7, 8),
            horizon=12,
            sample_count=20000,
            sampler_seed=20261004,
        ),
    }
    output = Path("artifacts/world2_reachability_report.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "enumerated_sequence_count": report["enumerated"]["sequence_count"],
        "enumerated_counts": report["enumerated"]["phenomenon_path_counts"],
        "sampled_sequence_count": report["sampled"]["sample_count"],
        "sampled_counts": report["sampled"]["phenomenon_path_counts"],
        "artifact": str(output),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
