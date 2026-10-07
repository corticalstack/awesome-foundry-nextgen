"""Markdown reports for the scheduled workflows (standard library only).

    python3 scripts/ci_report.py lock-diff COMMITTED_LOCK NEWEST_LOCK
    python3 scripts/ci_report.py live FIRST_RESULTS.json [COMMITTED_RESULTS.json]

lock-diff lists the packages whose locked version differs, marking major-version jumps.
live turns run_notebooks.py results into a table. With a second results file (failures
rerun on the committed lock) it labels each failure: a package regression if it passes on
the committed lock, Azure or notebook drift if it fails on both.
"""

import json
import sys
import tomllib
from pathlib import Path


def lock_versions(path):
    versions = {}
    for package in tomllib.loads(Path(path).read_text())["package"]:
        versions.setdefault(package["name"], set()).add(package["version"])
    return {name: ", ".join(sorted(v)) for name, v in versions.items()}


def lock_diff(committed, newest):
    old, new = lock_versions(committed), lock_versions(newest)
    changed = sorted(n for n in old.keys() | new.keys() if old.get(n) != new.get(n))
    lines = ["### Newest releases vs the committed lock", ""]
    if not changed:
        return "\n".join(lines + ["No changes: the committed lock is already on the newest allowed releases.", ""])
    lines += [f"{len(changed)} packages differ.", "", "| Package | Committed | Newest | |", "|---|---|---|---|"]
    for name in changed:
        a, b = old.get(name, "-"), new.get(name, "-")
        major = a != "-" and b != "-" and a.split(".")[0] != b.split(".")[0]
        lines.append(f"| {name} | {a} | {b} | {'major' if major else ''} |")
    return "\n".join(lines + [""])


def live(first, committed=None):
    results = json.loads(Path(first).read_text())
    rerun = {r["notebook"]: r for r in json.loads(Path(committed).read_text())} if committed and Path(committed).exists() else {}
    lines = ["### Live notebook run", "", "| Notebook | Result | Failing cell | Verdict |", "|---|---|---|---|"]
    counts = {"pass": 0, "package": 0, "drift": 0, "fail": 0}
    for r in results:
        if r["status"] == "pass":
            counts["pass"] += 1
            lines.append(f"| `{r['notebook']}` | pass | | |")
            continue
        cell = f"{r['failed_cell']}: {r['error_type']}"
        again = rerun.get(r["notebook"])
        if again is None:
            verdict, key = "failed (not rerun)", "fail"
        elif again["status"] == "pass":
            verdict, key = "**package regression**: passes on the committed lock", "package"
        else:
            verdict, key = "Azure or notebook drift: fails on the committed lock too", "drift"
        counts[key] += 1
        lines.append(f"| `{r['notebook']}` | fail | {cell} | {verdict} |")
    summary = (f"{counts['pass']} passed, {counts['package']} package regressions, "
               f"{counts['drift']} drift, {counts['fail']} other failures.")
    return "\n".join(["### Live notebook run", "", summary, ""] + lines[2:] + [""])


if __name__ == "__main__":
    command, *paths = sys.argv[1:]
    print({"lock-diff": lock_diff, "live": live}[command](*paths))
