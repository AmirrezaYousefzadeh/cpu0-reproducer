"""Frequency restoration and process-cleanup primitives (MIT)."""
from contextlib import contextmanager
import datetime as dt
import json, os, signal, subprocess
from pathlib import Path

def now():
    return dt.datetime.now().astimezone().isoformat()

def write_limit(directory, value):
    path = directory / "scaling_max_freq"
    path.write_text(str(value) + "\n")
    if int(path.read_text()) != value:
        raise RuntimeError(f"Frequency limit read-back failed: {path}")

def restore_limits(policies, originals):
    errors = []
    for cpu, directory in policies.items():
        try:
            write_limit(directory, originals[cpu])
        except Exception as error:
            errors.append(f"CPU {cpu}: {error}")
    if errors:
        raise RuntimeError("Restoration failed: " + "; ".join(errors))

@contextmanager
def temporary_limits(policies, originals, cap):
    # The finally also runs if the second cap write fails before yield.
    try:
        for directory in policies.values():
            write_limit(directory, cap)
        yield
    finally:
        restore_limits(policies, originals)

def process_table():
    table = {}
    for path in Path("/proc").glob("[0-9]*/stat"):
        try:
            fields = path.read_text().rsplit(")", 1)[1].split()
            table[int(path.parent.name)] = (int(fields[1]), fields[19])
        except (OSError, ValueError, IndexError):
            pass
    return table

def descendants(pid):
    table = process_table()
    selected = {pid}
    while True:
        expanded = selected | {p for p, (parent, _) in table.items() if parent in selected}
        if expanded == selected:
            return {p: table[p][1] for p in selected if p in table}
        selected = expanded

def stop_supervisor(process, grace_seconds=15):
    # The existing runner handles SIGINT by stopping its workload's separate
    # process group. Retain descendant identities for a forced-cleanup fallback.
    tracked = descendants(process.pid)
    if process.poll() is None:
        process.send_signal(signal.SIGINT)
        try:
            process.wait(timeout=grace_seconds)
        except subprocess.TimeoutExpired:
            tracked.update(descendants(process.pid))
    for pid, start in tracked.items():
        current = process_table().get(pid)
        if current and current[1] == start and pid != os.getpid():
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    process.wait(timeout=10)

def save_status(out, status, uid, gid):
    path = out / "status.json"
    temporary = out / "status.json.tmp"
    temporary.write_text(json.dumps(status, indent=2) + "\n")
    os.chown(temporary, uid, gid)
    temporary.replace(path)
