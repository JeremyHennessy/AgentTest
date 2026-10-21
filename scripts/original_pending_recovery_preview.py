#!/usr/bin/env python3
"""Verify a complete frozen Ora 9905 candidate in a disposable Git checkout.

No push, remote mutation, new-world authority or fake live progress.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from agenttest.snapshot_storage import (CHUNK_BYTES, CHUNK_FORMAT,
    read_snapshot_bytes, write_chunked_snapshot_bytes)

CLAIM="584e861165fb65639f1eea0ac165f3cae85d5e91"
SOURCE="d6452c239c7665166e9dd5196a46451442dc8505"
TICKET="heartbeat:v1:ccb6e57dd7b5d37e7bcbed9eea7d3ba9a65e31556f7dbbf562b19b882cd668e4"
ORIGINAL_BLOB="b99783f1baef5ca679e1dd43740956ec3111cc25"

def command(root:Path,*args:str) -> str:
    return subprocess.check_output(["git","-C",str(root),*args],text=True).strip()

def run(root:Path,destination:Path)->dict:
    if command(root,"rev-parse","HEAD")!=CLAIM:
        raise RuntimeError("original candidate checkout not exact pending claim")
    if command(root,"rev-parse",CLAIM+":state/organism.json")!=ORIGINAL_BLOB:
        raise RuntimeError("original Git blob mismatch")
    path=root/"scripts"/"heartbeat_transport.py"
    spec=importlib.util.spec_from_file_location("_frozen_ora_transport",path)
    if spec is None or spec.loader is None: raise RuntimeError("missing original transport")
    old=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=old
    spec.loader.exec_module(old)
    row=old._read(root)
    if not row or row["status"]!="completed" or row["request_id"]!=TICKET:
        raise RuntimeError("original completion must occur first")
    if row["source_sha"]!=SOURCE or row.get("claim_commit")!=CLAIM:
        raise RuntimeError("original source or claim changed")
    if row["input_cycle"]!=9904 or row["result_cycle"]!=9905:
        raise RuntimeError("not precisely one original cycle")
    if old._commit_record(root,CLAIM)["status"]!="pending":
        raise RuntimeError("source is not an authentic pending ticket")
    raw_previous=subprocess.check_output(["git","-C",str(root),"show",CLAIM+":state/organism.json"])
    old_journal=subprocess.check_output(["git","-C",str(root),"show",CLAIM+":state/journal.jsonl"])
    if hashlib.sha256(raw_previous).hexdigest()!="1fd834e29f83ef2bba73a951ed184bddce37a129676fbd3a23fc47e7e539ef7b":
        raise RuntimeError("previous original bytes changed")
    journal=(root/"state/journal.jsonl").read_bytes()
    if not journal.startswith(old_journal) or len(journal)<=len(old_journal):
        raise RuntimeError("journal prefix changed or no new event")
    new_events=[json.loads(x) for x in journal[len(old_journal):].splitlines() if x.strip()]
    cycles=[x for x in new_events if x.get("event")=="cycle"]
    if len(cycles)!=1 or cycles[0].get("cycle")!=9905:
        raise RuntimeError("one natural Core cycle not proven")
    state_path=root/"state/organism.json"
    computed=state_path.read_bytes()
    if json.loads(computed).get("cycles")!=9905 or row["result_state_hash"]!=old._state_hash(root):
        raise RuntimeError("old exact-source completion receipt invalid")

    receipt=write_chunked_snapshot_bytes(state_path,computed)
    if receipt["format"]!=CHUNK_FORMAT or read_snapshot_bytes(state_path)!=computed:
        raise RuntimeError("conversion changed original computed state")
    if receipt["part_count"]!=4:
        raise RuntimeError("unexpected physical chunk count")
    row["result_state_hash"]=old._state_hash(root)
    row["recovery_execution"]={
       "kind":"copy_only_transaction_preview",
       "original_source_sha":SOURCE,
       "input_cycle":9904, "result_cycle":9905,
       "remotely_published":False,
    }
    old._write(root,row)
    if old._read(root)["content_hash"]!=row["content_hash"]:
        raise RuntimeError("unsealed or altered recovery receipt")
    command(root,"config","user.name","ora-copy-only-audit")
    command(root,"config","user.email","audit@example.invalid")
    command(root,"add","--","state/")
    changed=command(root,"diff","--cached","--name-only").splitlines()
    if not changed or any(not x.startswith("state/") for x in changed):
        raise RuntimeError("preview changed unrelated source")
    command(root,"commit","-qm","Copied exact-original pending 9905 chunk transaction",
            "-m","Heartbeat-Request: "+TICKET)
    candidate=command(root,"rev-parse","HEAD")
    if command(root,"rev-parse",candidate+"^")!=CLAIM or command(root,"status","--porcelain"):
        raise RuntimeError("candidate parent or clean tree mismatch")
    stored=old._commit_record(root,candidate)
    if stored["status"]!="completed" or stored["content_hash"]!=row["content_hash"]:
        raise RuntimeError("committed complete record mismatch")
    if stored["result_state_hash"]!=old._state_hash(root,candidate):
        raise RuntimeError("committed state hash mismatch")
    tree=subprocess.check_output(["git","-C",str(root),"ls-tree","-rz",candidate,"--","state/"])
    for entry in tree.split(b"\0"):
        if not entry:continue
        oid=entry.split(b"\t")[0].decode().split()[-1]
        if int(command(root,"cat-file","-s",oid))>100*1024*1024:
            raise RuntimeError("Git object over single-blob size limit")
    remote=command(root,"ls-remote","origin","refs/heads/autonomous/growth").split()[0]
    if remote!=CLAIM:
        raise RuntimeError("original remote unexpectedly moved")
    report={
      "status":"LOCAL_COPIED_TRANSACTION_ONLY",
      "remote_published":False,"remote_heartbeat_recovered":False,
      "original_claim":CLAIM,"source_sha":SOURCE,"ticket":TICKET,
      "input_cycle":9904,"copied_result_cycle":9905,
      "one_new_cycle_event":True,"preserved_journal_prefix_bytes":len(old_journal),
      "original_raw_sha256":hashlib.sha256(raw_previous).hexdigest(),
      "computed_raw_sha256":hashlib.sha256(computed).hexdigest(),
      "computed_raw_bytes":len(computed),
      "chunk_count":receipt["part_count"],"chunk_bytes":CHUNK_BYTES,
      "local_only_commit":candidate,"result_state_hash":stored["result_state_hash"],
      "remote_writes":0
    }
    destination.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    print(json.dumps(report,sort_keys=True))
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--copy",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    run(args.copy.resolve(),args.output.resolve())
