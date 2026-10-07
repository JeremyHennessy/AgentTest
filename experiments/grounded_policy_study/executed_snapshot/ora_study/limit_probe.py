"""Zero-world-call resource mechanism fixture, never a scientific child."""
import resource
# Kernel accounts CPU from process birth, including work before these calls.
resource.setrlimit(resource.RLIMIT_AS, (64*1024*1024, 64*1024*1024))
resource.setrlimit(resource.RLIMIT_CPU, (1, 1))
resource.setrlimit(resource.RLIMIT_FSIZE, (4096, 4096))
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
resource.setrlimit(resource.RLIMIT_NPROC, (1, 1))
import json
import os
import sys
mode = sys.argv[1]
if mode == "as":
    try:
        data = bytearray(128*1024*1024)
    except MemoryError:
        print(json.dumps({"mechanism": "RLIMIT_AS", "blocked": True, "limit": 64*1024*1024}))
    else:
        raise SystemExit(10)
elif mode == "fsize":
    try:
        with open("bounded-file", "wb", buffering=0) as stream:
            stream.write(b"x"*8192)
            stream.write(b"x")
    except OSError as error:
        print(json.dumps({"mechanism": "RLIMIT_FSIZE", "size": os.stat("bounded-file").st_size, "errno": error.errno}))
    else:
        raise SystemExit(11)
elif mode == "cpu":
    value = 0
    while True:
        value += 1
elif mode == "nproc":
    try:
        child = os.fork()
    except OSError as error:
        print(json.dumps({"mechanism": "RLIMIT_NPROC", "blocked": True, "errno": error.errno, "euid": os.geteuid()}))
    else:
        if child == 0:
            os._exit(0)
        os.waitpid(child, 0)
        print(json.dumps({"mechanism": "RLIMIT_NPROC", "blocked": False, "euid": os.geteuid()}))
else:
    raise SystemExit(12)
