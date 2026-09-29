from __future__ import annotations

import argparse
import json
from pathlib import Path

from .core import AgentCore
from .evolution import propose_growth_experiment
from .state import StateStore


def _store(path: str) -> StateStore:
    return StateStore(path)


def _print(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(prog="agenttest")
    parser.add_argument(
        "--state",
        default="state/organism.json",
        help="Path to persistent organism state.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    cycle = sub.add_parser("cycle", help="Run one observe-question-experiment cycle.")
    cycle.add_argument("--stimulus", default=None)

    sub.add_parser("status", help="Print the current state.")

    propose = sub.add_parser("propose", help="Write the next reversible growth experiment.")
    propose.add_argument("--output", default="state/next_experiment.json")

    outcome = sub.add_parser("outcome", help="Record evidence from an experiment.")
    outcome.add_argument("experiment_id")
    outcome.add_argument("outcome")
    outcome.add_argument("--evidence-strength", type=float, default=0.5)

    args = parser.parse_args()
    store = _store(args.state)
    core = AgentCore(store)

    if args.command == "cycle":
        _print(core.cycle(args.stimulus))
    elif args.command == "status":
        _print(store.load())
    elif args.command == "propose":
        proposal = propose_growth_experiment(store.load())
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(proposal, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        _print(proposal)
    elif args.command == "outcome":
        _print(
            core.record_outcome(
                args.experiment_id,
                args.outcome,
                args.evidence_strength,
            )
        )


if __name__ == "__main__":
    main()
