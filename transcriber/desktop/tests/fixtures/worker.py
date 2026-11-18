#!/usr/bin/env python3
"""
worker.py

Model-free worker fixture used by native and runtime tests. Its modes exercise
real process lifetime, pipe errors and stale/duplicate protocol messages.
"""
import json
import os
from pathlib import Path
import sys
import time

request = json.loads(sys.stdin.readline())
mode = sys.argv[1] if len(sys.argv) > 1 else "normal"


# Keep identity/version identical to production unless deliberately testing corruption.
def emit(event, **values):
    print(json.dumps({"version": 1, "id": request["id"], "event": event, **values}), flush=True)


if os.environ.get("TRANSCRIBER_FIXTURE_RECORD"):
    Path(os.environ["TRANSCRIBER_FIXTURE_RECORD"]).write_text(str(os.getpid()))
if mode == "wrong-id":
    request["id"] += 1
if mode == "malformed":
    print("not JSON", flush=True)
elif mode == "crash":
    print("Synthetic worker crash", file=sys.stderr)
    raise SystemExit(7)
elif mode == "no-result":
    pass
elif mode == "invalid-result":
    emit("result", available="not a boolean")
else:
    if request["action"] == "inspect":
        emit("result", models={"High": True, "Medium": True, "Low": True})
    else:
        emit("progress", phase="transcribing", percent=12)
        if mode == "slow" or "slow" in (request.get("input") or ""):
            time.sleep(60)
        if mode == "log-flood":
            sys.stderr.write("diagnostic " * 100000)
            sys.stderr.flush()
        emit("result", text="Native fixture transcription.", available=True)
        if mode == "duplicate":
            emit("result", text="Duplicate result")
