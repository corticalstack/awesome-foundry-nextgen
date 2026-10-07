"""Check keyword arguments passed to Azure SDK model classes against the installed SDKs.

    uv run python scripts/check_sdk_kwargs.py

Import checks catch removed classes; this catches removed or renamed fields. Generated
models in azure-ai-projects, azure-search-documents and friends are constructed with
keyword arguments, and a field the installed version no longer has raises a TypeError
only when the cell runs (azure-ai-projects 2.7 removed HostedAgentDefinition's `image`
and `container_protocol_versions` this way). For every call to a model class imported
from those packages, the keyword arguments are compared with the fields the class
defines. Clients and other non-model classes are skipped. Exit code 1 on any mismatch.
"""

import ast
import importlib
import sys

from check_imports import REPO, code_blocks, repo_files

SDK_PACKAGES = ("azure.ai.projects", "azure.search.documents", "azure.ai.agents", "azure.ai.evaluation")


def model_fields(cls):
    """Field names of a generated SDK model, or None for anything that is not one."""
    try:
        cls.__new__(cls)  # generated models build their field map on first __new__
    except Exception:
        return None
    fields = getattr(cls, "_attr_to_rest_field", None)
    return set(fields) if fields else None


def main():
    files, _ = repo_files()
    checked, problems = 0, []
    for path in files:
        trees = []
        for label, src in code_blocks(path):
            try:
                trees.append((label, compile(src, "<cell>", "exec",
                                             flags=ast.PyCF_ONLY_AST | ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)))
            except SyntaxError:
                continue
        # A notebook shares one namespace, so an import in one cell covers calls in later cells.
        imported = {}
        for _, tree in trees:
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith(SDK_PACKAGES):
                    for alias in node.names:
                        imported[alias.asname or alias.name] = (node.module, alias.name)
        for label, tree in trees:
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                        and node.func.id in imported and node.keywords):
                    continue
                module, name = imported[node.func.id]
                try:
                    cls = getattr(importlib.import_module(module), name)
                except (ImportError, AttributeError):
                    continue  # check_imports.py reports these
                if not isinstance(cls, type) or (fields := model_fields(cls)) is None:
                    continue
                checked += 1
                unknown = sorted({k.arg for k in node.keywords if k.arg} - fields)
                if unknown:
                    where = label.replace(str(REPO) + "/", "")
                    problems.append(f"FAIL  {name}({', '.join(f'{u}=' for u in unknown)}) in {where}")
    for p in problems:
        print(p)
    print(f"{checked} SDK model constructor calls checked, {len(problems)} with unknown keyword arguments")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
