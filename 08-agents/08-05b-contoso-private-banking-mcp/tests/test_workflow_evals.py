"""Workflow-level evals - Anthropic's "evals on real workflows, not toy prompts" point.

Each row in workflow_evals.jsonl pairs a natural-language RM request with the
intent tool the agent SHOULD call and the response fields the kb SHOULD return.
This file tests the kb-side contract (does the right tool with the right args
return the right fields?). The agent-side selection (does the LLM pick the
right tool from the description?) is exercised in the queries notebook
[08-05b-02] and would be wired into the Foundry evaluation portal in production.

Why this matters per Anthropic's guidance: registry changes (renaming tools,
tweaking descriptions) routinely degrade tool-selection accuracy. Running
workflow evals after every registry change catches the drift toy benchmarks
miss.
"""

import json
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / 'assets' / 'contoso-private-banking-dataset'
KB_DIR = REPO_ROOT / '08-agents' / '08-05b-contoso-private-banking-mcp' / 'private-banking-mcp'

os.environ['DATA_DIR'] = str(DATA_DIR)
os.environ.setdefault('TODAY', '2026-05-10')

sys.path.insert(0, str(KB_DIR))
import kb  # noqa: E402


def _load_evals() -> list[dict]:
    with open(Path(__file__).parent / 'workflow_evals.jsonl') as f:
        return [json.loads(line) for line in f if line.strip()]


def _get_nested(d: dict, dotted_key: str):
    cur = d
    for part in dotted_key.split('.'):
        if isinstance(cur, list) and cur:
            cur = cur[0]
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


_SEVERITY_ORDER = {'within_band': 0, 'over_band': 1, 'material_breach': 2}


@pytest.mark.parametrize('row', _load_evals(), ids=lambda r: r['id'])
def test_workflow(row):
    tool_fn = getattr(kb, row['expected_tool'])
    out = json.loads(tool_fn(**row.get('args', {})))

    assert 'error' not in out, (
        f"workflow {row['id']}: unexpected error from {row['expected_tool']}: {out.get('error')}"
    )

    for key in row.get('expect_data_keys', []):
        assert _get_nested(out['data'], key) is not None, (
            f"workflow {row['id']}: expected key {key!r} in data; got: {list(out['data']) if isinstance(out['data'], dict) else type(out['data']).__name__}"
        )

    for needle in row.get('expect_summary_contains', []):
        assert needle in out['summary'], (
            f"workflow {row['id']}: expected {needle!r} in summary; got: {out['summary']!r}"
        )

    if 'expect_at_least_n_results' in row:
        n = row['expect_at_least_n_results']
        items = out['data']
        assert isinstance(items, list) and len(items) >= n, (
            f"workflow {row['id']}: expected at least {n} results; got {len(items) if isinstance(items, list) else 'non-list'}"
        )

    if 'expect_at_least_one_row_in' in row:
        key = row['expect_at_least_one_row_in']
        rows = out['data'].get(key, [])
        assert rows, f"workflow {row['id']}: expected at least one row in data.{key}"

    if 'expect_drift_severity_at_least' in row:
        threshold = _SEVERITY_ORDER[row['expect_drift_severity_at_least']]
        rows = out['data'].get('vs_ips', {}).get('asset_class_drift', []) \
            or out['data'].get('asset_class_drift', [])
        max_seen = max((_SEVERITY_ORDER.get(r.get('severity'), 0) for r in rows), default=0)
        assert max_seen >= threshold, (
            f"workflow {row['id']}: expected at least {row['expect_drift_severity_at_least']} severity; "
            f"max seen was {next(k for k, v in _SEVERITY_ORDER.items() if v == max_seen)}"
        )
