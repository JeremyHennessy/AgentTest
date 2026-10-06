"""Remote request claim for the human-interaction workflow.

The claim is stored only in an already-tracked last_interaction sidecar. The
ordinary organism state is not modified. Missing sidecar is a documented
first-interaction fallback: no new tracked path is created.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


VERSION = "interaction-request-claim-v1"


class ClaimError(RuntimeError):
    pass


def message_digest(message: str) -> str:
    return hashlib.sha256(message.encode("utf-8")).hexdigest()


def make_claim(request_id: str, message: str, event_name: str) -> dict:
    if not request_id:
        raise ClaimError("missing request identity")
    return {
        "version": VERSION,
        "request_id": request_id,
        "message_sha256": message_digest(message),
        "event_name": event_name,
    }


def claim_sidecar(path: Path, request_id: str, message: str, event_name: str) -> dict:
    claim = make_claim(request_id, message, event_name)
    if not path.exists():
        return {"claimed": False, "reason": "sidecar_missing", "claim": claim}

    before = path.read_bytes()
    try:
        data = json.loads(before)
    except (ValueError, UnicodeError) as exc:
        raise ClaimError("invalid last-interaction sidecar") from exc
    if not isinstance(data, dict):
        raise ClaimError("last-interaction sidecar must be an object")

    completed = data.get("interaction") or {}
    completed_id = completed.get("request_id")
    if completed_id == request_id:
        if completed.get("input") != message:
            raise ClaimError("completed interaction request identity conflicts with message")
        return {"claimed": False, "reason": "already_completed", "claim": claim}

    existing = data.get("pending_request")
    if existing is not None:
        if existing != claim:
            raise ClaimError("different interaction request is already pending")
        return {"claimed": False, "reason": "already_claimed", "claim": claim}

    data["pending_request"] = claim
    rendered = (json.dumps(data, indent=2, sort_keys=True) + "\n").encode("utf-8")
    temp = path.with_suffix(path.suffix + ".claim.tmp")
    temp.write_bytes(rendered)
    temp.replace(path)
    return {"claimed": True, "reason": "created", "claim": claim}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sidecar", required=True)
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--message-file", required=True)
    parser.add_argument("--event-name", required=True)
    args = parser.parse_args()

    message = Path(args.message_file).read_text(encoding="utf-8")
    result = claim_sidecar(
        Path(args.sidecar),
        args.request_id,
        message,
        args.event_name,
    )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
