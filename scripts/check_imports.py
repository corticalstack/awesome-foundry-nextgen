"""Check that every third-party import in the labs resolves in the current environment.

    uv run python scripts/check_imports.py          notebooks and modules that run on the repo .venv
    python scripts/check_imports.py DIR [DIR ...]   every notebook and module under each DIR

Each distinct import statement is executed once, so `from pkg import Name` also catches a
Name that a new release removed. Standard-library modules, relative imports and the repo's
own modules are skipped. Code is parsed with `ast`, so imports inside strings (the main.py
template in 08-03-01) and in %% cell magics (%%writefile, %%bash) are not executed.

Without arguments, folders that carry their own requirements.txt (hosted-agent containers,
Function apps) are left out because they install into a different environment, and so is
15-fine-tune, which needs `uv sync --group finetune`. Exit code 1 if any import fails.
"""

import ast
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SKIP_IN_REPO_MODE = ("15-fine-tune/",)


def repo_files():
    """Return (files to check, every tracked module) for the repo .venv."""
    tracked = subprocess.check_output(
        ["git", "ls-files", "*.py", "*.ipynb", "*/requirements.txt", "*/requirements.in"], cwd=REPO, text=True
    ).split()
    own_env = {str(Path(f).parent) + "/" for f in tracked if f.endswith(("requirements.txt", "requirements.in"))}
    skip = SKIP_IN_REPO_MODE + tuple(own_env)
    code = [REPO / f for f in tracked if f.endswith((".py", ".ipynb"))]
    return [p for p in code if not str(p.relative_to(REPO)).startswith(skip)], code


def dir_files(roots):
    files = [p for r in roots for p in sorted(Path(r).rglob("*")) if p.suffix in (".py", ".ipynb")]
    return files, files


def local_modules(files):
    names = set()
    for f in files:
        if f.suffix == ".py":
            names.add(f.stem)
            names.add(f.parent.name)  # package directories, e.g. 11-foundry-iq-multi-agent/agents
    return names


def code_blocks(path):
    """Yield (label, source) for a module, or for each code cell of a notebook."""
    if path.suffix == ".py":
        yield str(path), path.read_text(encoding="utf-8")
        return
    cells = json.loads(path.read_text(encoding="utf-8"))["cells"]
    for i, cell in enumerate(cells):
        src = "".join(cell["source"])
        if cell["cell_type"] != "code" or src.lstrip().startswith("%%"):
            continue
        # Line magics and shell escapes (with their backslash continuations) are not Python.
        lines, in_magic = [], False
        for line in src.splitlines():
            if in_magic or line.lstrip().startswith(("%", "!")):
                indent = "" if in_magic else line[: len(line) - len(line.lstrip())]
                lines.append(indent + "pass" if not in_magic else "")
                in_magic = line.rstrip().endswith("\\")
            else:
                lines.append(line)
        yield f"{path} cell {i}", "\n".join(lines)


def import_statements(source, local):
    # Notebook cells may use top-level await.
    tree = compile(source, "<cell>", "exec", flags=ast.PyCF_ONLY_AST | ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] not in local:
                    yield f"import {alias.name}"
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            if node.module.split(".")[0] in local or node.module == "__future__":
                continue
            names = ", ".join(a.name for a in node.names)
            yield f"from {node.module} import {names}" if names != "*" else f"import {node.module}"


def main(argv):
    files, all_code = dir_files(argv) if argv else repo_files()
    local = local_modules(all_code) | set(sys.stdlib_module_names)
    statements = defaultdict(set)
    unparsed = []
    for f in files:
        for label, src in code_blocks(f):
            try:
                for stmt in import_statements(src, local):
                    statements[stmt].add(label)
            except SyntaxError as e:
                unparsed.append(f"{label}: {e.msg} (line {e.lineno})")

    failures = []
    for stmt in sorted(statements):
        try:
            exec(stmt, {})
        except Exception as e:  # ImportError, or whatever a broken package raises on import
            failures.append((stmt, f"{type(e).__name__}: {e}", sorted(statements[stmt])))

    for line in unparsed:
        print(f"warning: not parsed, imports not checked: {line}")
    for stmt, err, where in failures:
        print(f"FAIL  {stmt}\n      {err}")
        for w in where:
            print(f"      in {Path(w).relative_to(REPO) if w.startswith(str(REPO)) else w}")
    print(f"{len(statements)} import statements from {len(files)} files, {len(failures)} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
