from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from heartbeat_transport import state_writer_check

from agenttest.intervention import record_verified_intervention
from agenttest.state import StateStore, utc_now


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", default="state/organism.json")
    parser.add_argument("--proposal-id")
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--changed-file", action="append", dest="changed_files", required=True)
    parser.add_argument("--verify-run-id", type=int, required=True)
    parser.add_argument("--pr-number", type=int, required=True)
    parser.add_argument("--workflow-name", default="verify")
    parser.add_argument("--verification-event", default="push")
    parser.add_argument("--verification-conclusion", default="success")
    parser.add_argument("--authority", default="trusted_verification_workflow")
    parser.add_argument("--attribution-text", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()

    transport = state_writer_check(Path(args.state))
    if transport["status"] == "deferred":
        print(json.dumps(transport, sort_keys=True), file=sys.stderr)
        raise SystemExit(75)

    store = StateStore(args.state)
    state = store.load()
    if (state.get("current_world_heartbeat") or {}).get("pending"):
        from agenttest.heartbeat_claim import reject_unfinished_claim
        reject_unfinished_claim(state)
    receipt, created = record_verified_intervention(
        state,
        proposal_id=args.proposal_id,
        commit_sha=args.commit_sha,
        changed_files=args.changed_files,
        verify_run_id=args.verify_run_id,
        pr_number=args.pr_number,
        workflow_name=args.workflow_name,
        verification_event=args.verification_event,
        verification_conclusion=args.verification_conclusion,
        authority=args.authority,
        attribution_text=args.attribution_text,
    )

    result = {"created": created, "receipt": receipt}
    if created and receipt is not None:
        store.save(state)
        store.append_journal(
            {
                "event": "verified_intervention_reconciled",
                "time": utc_now(),
                "cycle": state.get("cycles", 0),
                "accepted_change_id": receipt["id"],
                "proposal_id": receipt["proposal_id"],
                "commit_sha": receipt["commit_sha"],
                "verify_run_id": receipt["verification"]["run_id"],
                "verification_scope": receipt["verification_scope"],
                "improvement_claim": receipt["improvement_claim"],
            }
        )

    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
