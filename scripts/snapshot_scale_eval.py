"""Isolated, real-snapshot Git pack-cost comparator; no writes to original growth."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from agenttest.snapshot_chunk_research import write_isolated_parts, read_parts, CHUNK_BYTES
from agenttest.snapshot_storage import prepare_stable_compressed_copy, read_snapshot_bytes


def git(directory: Path,*args:str) -> str:
    return subprocess.check_output(["git","-C",str(directory),*args],text=True).strip()


def _files(where:Path,raw:bytes,kind:str) -> None:
    if kind=="parts":
        write_isolated_parts(where,raw)
    elif kind=="gzip":
        envelope,name,body=prepare_stable_compressed_copy(raw)
        where.mkdir(exist_ok=True,parents=True)
        (where/name).write_bytes(body)
        (where/"organism.json").write_bytes(envelope)
        if read_snapshot_bytes(where/"organism.json")!=raw:
            raise SystemExit("compressed local roundtrip changed bytes")
    else:
        raise SystemExit("unknown representation")


def pack_cost(where:Path,older:bytes,newer:bytes,kind:str) -> dict:
    where.mkdir()
    git(where,"init","-q")
    git(where,"config","user.name","independent-storage-study")
    git(where,"config","user.email","study@example.invalid")
    for generation,raw in enumerate((older,newer),1):
        _files(where,raw,kind)
        git(where,"add","-A")
        git(where,"commit","-qm",f"copied storage representation {generation}")
        if kind=="parts" and read_parts(where)!=raw:
            raise SystemExit("copy semantics changed")
    git(where,"gc","--prune=now")
    report=dict(line.split(": ",1) for line in git(where,"count-objects","-v").splitlines() if ": " in line)
    return {"kind":kind,"pack_kib":int(report["size-pack"]),"packfiles":int(report["packs"]),
            "tracked_files":len(git(where,"ls-files").splitlines()),
            "original_bytes":len(older),"synthetic_new_bytes":len(newer)}


def run(source:Path, candidate:Path | None = None) -> dict:
    older=source.read_bytes()
    old_hash=hashlib.sha256(older).hexdigest()
    state=json.loads(older)
    if state.get("cycles")!=9904:
        raise SystemExit("unexpected original growth input cycle")
    if candidate is None:
        # This control is not presented as a natural Ora action.
        state["isolated_storage_comparison_marker"]={"experiment":"matched-representation","value":1}
        newer=(json.dumps(state,sort_keys=True,separators=(",",":"))+"\n").encode()
        study_name="real_cycle9904_matched_synthetic_update"
    else:
        newer=candidate.read_bytes()
        if json.loads(newer).get("cycles")!=state["cycles"]+1:
            raise SystemExit("copied next-cycle candidate does not advance exactly once")
        study_name="real_cycle9904_copied_native_full_cycle"
    with tempfile.TemporaryDirectory() as tmp:
        parent=Path(tmp)
        results=[pack_cost(parent/k,older,newer,k) for k in ("gzip","parts")]
    if source.read_bytes()!=older or hashlib.sha256(source.read_bytes()).hexdigest()!=old_hash:
        raise SystemExit("original source modified")
    return {"study":study_name,"read_only":True,"live_actions_published":0,
            "input_sha256":old_hash,"chunk_size":CHUNK_BYTES,"results":results,
            "conclusion_limit":"Two-generation copied-storage comparison only. A copied natural-policy action is not a durably published original-world heartbeat or a long-horizon Git storage guarantee."}


def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--candidate",type=Path)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    result=run(args.source,args.candidate)
    args.output.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print(json.dumps(result,sort_keys=True))

if __name__=="__main__":
    main()
