"""Executable fixture only. It has no simulator, policy, source or network imports."""
import hashlib
import json
import os
import sys
import time

mode = sys.argv[1]
if sys.stdin.buffer.readline() != b"go\n":
    raise SystemExit(90)
if mode == "fail_before_start":
    raise SystemExit(10)
if mode == "bad_json":
    print("{invalid", flush=True)
    raise SystemExit(11)
if mode == "stderr_flood":
    sys.stderr.write("x" * 32768)
    sys.stderr.flush()
    raise SystemExit(12)
if mode == "hang":
    time.sleep(60)
    raise SystemExit(13)
def emit(event, **rest):
    print(json.dumps(dict(event=event, **rest)), flush=True)
emit("started")
if mode == "fail_after_start":
    raise SystemExit(20)
# This is a hand-authored integer fixture, not any world transition.
result_hash = hashlib.sha256(b'{"authored_fixture_sum":5}').hexdigest()
authority_hash = hashlib.sha256(b"stub durable authority, not a capsule").hexdigest()
emit("computed", result_hash=result_hash)
if mode == "fail_after_compute":
    raise SystemExit(30)
emit("durable", result_hash=result_hash, authority_hash=authority_hash)
if mode == "lost_response":
    raise SystemExit(40)
emit("done")
