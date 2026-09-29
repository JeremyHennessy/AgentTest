from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from agenttest.diagnostic_experiments import evaluate_experiment_design


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json_atomic(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temp.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", default="state/organism.json")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    state_path = Path(args.state)
    state = json.loads(state_path.read_text(encoding="utf-8"))
    result = evaluate_experiment_design(state)
    if result.get("source_state_mutated"):
        raise SystemExit("experiment-design diagnostic mutated source state")

    context = {
        "cycle": int(state.get("cycles", 0)),
        "active_ids": [
            item.get("id")
            for item in state.get("experiments", [])
            if item.get("status") == "proposed"
        ],
        "result": result,
    }
    context_hash = hashlib.sha256(
        json.dumps(context, sort_keys=True).encode("utf-8")
    ).hexdigest()

    diagnostics = state.setdefault("system_diagnostics", [])
    existing = next(
        (
            item
            for item in reversed(diagnostics)
            if item.get("kind") == "experiment_design"
            and item.get("context_hash") == context_hash
        ),
        None,
    )

    created = existing is None
    if existing is None:
        existing = {
            "id": f"SD{len(diagnostics) + 1:06d}",
            "kind": "experiment_design",
            "diagnostic_version": result["diagnostic_version"],
            "status": "completed",
            "created_at": _now(),
            "created_cycle": int(state.get("cycles", 0)),
            "baseline_fingerprint": (
                state.get("environment_snapshots", [{}])[-1].get(
                    "baseline_fingerprint"
                )
                if state.get("environment_snapshots")
                else None
            ),
            "context_hash": context_hash,
            "source_state_mutated": False,
            "outcome": result["outcome"],
            "result": result,
        }
        diagnostics.append(existing)
        state["updated_at"] = _now()
        _write_json_atomic(state_path, state)

        journal_path = state_path.parent / "journal.jsonl"
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        with journal_path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "event": "system_diagnostic",
                        "time": _now(),
                        "cycle": int(state.get("cycles", 0)),
                        "diagnostic_id": existing["id"],
                        "kind": existing["kind"],
                        "outcome": existing["outcome"],
                        "source_state_mutated": False,
                    },
                    sort_keys=True,
                )
                + "\n"
            )

    rendered = {"created": created, "diagnostic": existing}
    _write_json_atomic(Path(args.output), rendered)
    print(json.dumps(rendered, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
