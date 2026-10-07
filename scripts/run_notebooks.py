"""Execute lab notebooks headless against the live Azure environment.

    uv run --with nbclient --with nbformat python scripts/run_notebooks.py --tags weekly
    uv run --with nbclient --with nbformat python scripts/run_notebooks.py --only 10-foundry-iq/10-03-knowledge-base-setup.ipynb --save
    python scripts/run_notebooks.py --check

Notebooks come from scripts/notebooks.txt, in file order, each in a fresh kernel started in
the notebook's folder. Notebooks that call input() get the scripted `answers=` from the
manifest. Nothing is written back unless --save is given, and then only for notebooks that
passed and already keep outputs. Output printed here is safe for public CI logs: notebook,
status, seconds, failing cell index and exception type, never the exception message or any
cell output (--verbose adds the message for local debugging). --check fails if a tracked
notebook is missing from the manifest. Exit code 1 if any notebook fails.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO / "scripts" / "notebooks.txt"


def read_manifest():
    entries = []
    for line in MANIFEST.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        path, tags, *opts = line.split()
        options = dict(o.split("=", 1) for o in opts)
        entries.append({"path": path, "tags": set(tags.split(",")),
                        "answers": options["answers"].split(",") if "answers" in options else None})
    return entries


def check_manifest(entries):
    tracked = set(subprocess.check_output(["git", "ls-files", "*.ipynb"], cwd=REPO, text=True).split())
    listed = {e["path"] for e in entries}
    missing, stale = sorted(tracked - listed), sorted(listed - tracked)
    for p in missing:
        print(f"not in {MANIFEST.name}: {p}")
    for p in stale:
        print(f"listed but not tracked: {p}")
    print(f"{len(listed)} notebooks listed, {len(tracked)} tracked")
    return 1 if missing or stale else 0


def json_format(raw, nb):
    """Indent, ASCII escaping and trailing newline the file was saved with."""
    for indent in (1, 2):
        for ascii_only in (True, False):
            for tail in ("\n", ""):
                if json.dumps(nb, indent=indent, ensure_ascii=ascii_only) + tail == raw:
                    return indent, ascii_only, tail
    return 1, False, "\n"


def scripted_input_dir(answers):
    """An IPYTHONDIR whose startup file answers input() calls in order."""
    d = Path(tempfile.mkdtemp(prefix="nb-answers-"))
    startup = d / "profile_default" / "startup"
    startup.mkdir(parents=True)
    (startup / "00-scripted-input.py").write_text(
        "import ipykernel.kernelbase as _kb\n"
        f"_answers = iter({answers!r})\n"
        "def _scripted(self, prompt=''):\n"
        "    answer = next(_answers)\n"
        "    print(f'{prompt}{answer}')\n"
        "    return answer\n"
        "_kb.Kernel.raw_input = _scripted\n")
    return str(d)


def run(entry, save, verbose):
    import nbformat
    from nbclient import NotebookClient
    from nbclient.exceptions import CellExecutionError

    path = REPO / entry["path"]
    raw = path.read_text(encoding="utf-8")
    original = json.loads(raw)
    keeps_outputs = any(c.get("outputs") for c in original["cells"] if c["cell_type"] == "code")
    source_is_str = [isinstance(c["source"], str) for c in original["cells"]]
    nb = nbformat.reads(raw, as_version=4)

    previous_ipythondir = os.environ.get("IPYTHONDIR")
    if entry["answers"]:
        os.environ["IPYTHONDIR"] = scripted_input_dir(entry["answers"])
    client = NotebookClient(nb, timeout=3600, kernel_name="python3", record_timing=False,
                            resources={"metadata": {"path": str(path.parent)}})
    start = time.time()
    result = {"notebook": entry["path"], "status": "pass", "failed_cell": None, "error_type": None}
    message = ""
    try:
        client.execute()
    except CellExecutionError as e:
        result.update(status="fail", error_type=getattr(e, "ename", None) or "CellExecutionError")
        message = str(getattr(e, "evalue", ""))
        result["failed_cell"] = next((i for i, c in enumerate(nb.cells) if c.cell_type == "code"
                                      and any(o.get("output_type") == "error" for o in c.get("outputs", []))), None)
    except Exception as e:  # kernel died, timeout, ...
        result.update(status="fail", error_type=type(e).__name__)
        message = str(e)
    finally:
        if entry["answers"]:
            if previous_ipythondir is None:
                os.environ.pop("IPYTHONDIR", None)
            else:
                os.environ["IPYTHONDIR"] = previous_ipythondir
    result["seconds"] = round(time.time() - start)

    if save and result["status"] == "pass" and keeps_outputs:
        executed = json.loads(nbformat.writes(nb))
        for cell, as_str in zip(executed["cells"], source_is_str):
            if as_str and isinstance(cell["source"], list):
                cell["source"] = "".join(cell["source"])
        indent, ascii_only, tail = json_format(raw, original)
        path.write_text(json.dumps(executed, indent=indent, ensure_ascii=ascii_only) + tail, encoding="utf-8")

    line = f"{result['status'].upper():4s} {result['seconds']:5d}s  {entry['path']}"
    if result["status"] == "fail":
        line += f"  (cell {result['failed_cell']}: {result['error_type']})"
        if verbose and message:
            line += f"\n      {message[:500]}"
    print(line, flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--tags", help="comma-separated; run notebooks carrying any of these tags")
    parser.add_argument("--only", nargs="+", metavar="PATH", help="run just these manifest paths")
    parser.add_argument("--results", type=Path, help="write a JSON list of results here")
    parser.add_argument("--save", action="store_true", help="write outputs back for notebooks that pass")
    parser.add_argument("--verbose", action="store_true", help="also print exception messages (not for CI)")
    parser.add_argument("--list", action="store_true", help="print the selection without running it")
    parser.add_argument("--check", action="store_true", help="verify the manifest lists every notebook")
    args = parser.parse_args()

    entries = read_manifest()
    if args.check:
        return check_manifest(entries)
    if args.only:
        wanted = set(args.only)
        unknown = wanted - {e["path"] for e in entries}
        if unknown:
            sys.exit(f"not in {MANIFEST.name}: {', '.join(sorted(unknown))}")
        selected = [e for e in entries if e["path"] in wanted]
    elif args.tags:
        tags = set(args.tags.split(","))
        selected = [e for e in entries if e["tags"] & tags]
    else:
        sys.exit("give --tags, --only, --list with --tags, or --check")
    if args.list:
        for e in selected:
            print(e["path"])
        return 0

    results = [run(e, args.save, args.verbose) for e in selected]
    failed = [r for r in results if r["status"] == "fail"]
    print(f"{len(results) - len(failed)} passed, {len(failed)} failed")
    if args.results:
        args.results.write_text(json.dumps(results, indent=2) + "\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
