"""Remote heartbeat claim companion to interaction_request_claim.py (#210)."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from agenttest.heartbeat_claim import abandon_heartbeat, claim_heartbeat, verify_completed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("claim", "verify", "abandon"))
    parser.add_argument("--state", default="state/organism.json")
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--reason", default="")
    args = parser.parse_args()
    path = Path(args.state)
    if args.operation == "claim":
        result = claim_heartbeat(path, args.request_id)
    elif args.operation == "verify":
        result = verify_completed(path, args.request_id, require_current=True)
    else:
        result = abandon_heartbeat(path, args.request_id, args.reason)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
