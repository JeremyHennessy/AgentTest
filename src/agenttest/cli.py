from __future__ import annotations

import argparse
import json
from pathlib import Path

from .core import AgentCore
from .evolution import propose_growth_experiment
from .perception import repository_snapshot
from .proposal_review import review_change_proposal
from .self_proposal import propose_self_change
from .state import StateStore, utc_now


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
    cycle.add_argument(
        "--self-observe",
        action="store_true",
        help="Sense the current repository before choosing a question.",
    )
    cycle.add_argument(
        "--cognition",
        action="store_true",
        help="Allow an optional configured model to propose one validated candidate thought.",
    )
    cycle.add_argument("--root", default=".", help="Repository root for self-observation.")

    sub.add_parser("status", help="Print the current state.")

    propose = sub.add_parser("propose", help="Write the next reversible growth experiment.")
    propose.add_argument("--output", default="state/next_experiment.json")

    propose_change = sub.add_parser(
        "propose-change",
        help="Create or reuse one evidence-backed self-authored change manifest.",
    )
    propose_change.add_argument("--output", default="state/next_change.json")

    review_change = sub.add_parser(
        "review-change",
        help="Review the active self-authored manifest for evidence relevance.",
    )
    review_change.add_argument("--output", default="state/next_change_review.json")

    outcome = sub.add_parser("outcome", help="Record evidence from an experiment.")
    outcome.add_argument("experiment_id")
    outcome.add_argument("outcome")
    outcome.add_argument("--evidence-strength", type=float, default=0.5)

    args = parser.parse_args()
    store = _store(args.state)
    core = AgentCore(store)

    if args.command == "cycle":
        observation = repository_snapshot(args.root) if args.self_observe else None
        _print(core.cycle(args.stimulus, observation, cognition=args.cognition))
    elif args.command == "status":
        _print(store.load())
    elif args.command == "propose":
        proposal = propose_growth_experiment(store.load())
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(proposal, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        _print(proposal)
    elif args.command == "propose-change":
        state = store.load()
        proposal, created = propose_self_change(state)
        if created:
            store.save(state)
            store.append_journal(
                {
                    "event": "change_proposal",
                    "time": utc_now(),
                    "cycle": state.get("cycles", 0),
                    "proposal_id": proposal["id"] if proposal else None,
                    "target_dimension": proposal["target_dimension"] if proposal else None,
                }
            )
        result = {
            "created": created,
            "proposal": proposal,
        }
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        _print(result)
    elif args.command == "review-change":
        state = store.load()
        review, created = review_change_proposal(state)
        if created:
            store.save(state)
            store.append_journal(
                {
                    "event": "change_proposal_review",
                    "time": utc_now(),
                    "cycle": state.get("cycles", 0),
                    "review_id": review["id"] if review else None,
                    "proposal_id": review["proposal_id"] if review else None,
                    "verdict": review["verdict"] if review else None,
                    "patch_authority": review["patch_authority"] if review else None,
                }
            )
        result = {
            "created": created,
            "review": review,
        }
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        _print(result)
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
