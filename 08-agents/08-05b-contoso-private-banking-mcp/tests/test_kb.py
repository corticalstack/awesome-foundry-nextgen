"""Unit tests for kb.py — Contoso Private Banking intent-level knowledge base.

All tests run against the real fixture data under
assets/contoso-private-banking-dataset/. No Azure credentials required.

The TODAY env var is fixed to 2026-05-10 so the dataset's relative-date math
(recent transactions, 90d CRM events) is reproducible.
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


# ── Helpers ───────────────────────────────────────────────────────────────────


def _unwrap(s: str) -> dict:
    obj = json.loads(s)
    assert 'error' not in obj, f"unexpected error: {obj}"
    return obj


def _err(s: str) -> dict:
    obj = json.loads(s)
    assert 'error' in obj, f"expected error, got: {obj}"
    return obj['error']


# ── cpb_prepare_client_briefing ───────────────────────────────────────────────


def test_briefing_happy_path_returns_envelope():
    out = _unwrap(kb.cpb_prepare_client_briefing('cli-001'))
    assert set(out) == {'data', 'summary', 'citations', 'truncated', 'more_with', 'next_steps'}
    assert isinstance(out['data'], dict)
    assert isinstance(out['summary'], str) and out['summary']
    assert isinstance(out['citations'], list) and len(out['citations']) > 0


def test_briefing_data_sections():
    out = _unwrap(kb.cpb_prepare_client_briefing('cli-001'))
    d = out['data']
    for key in (
        'client', 'meeting_purpose', 'as_of', 'portfolio_summary', 'vs_ips',
        'recent_transactions_30d', 'crm_flags_90d',
        'relevant_research', 'relevant_commentary', 'next_best_actions',
    ):
        assert key in d, f"missing section {key}"
    assert d['client']['name'] == 'Berger Family Trust'
    assert d['client']['rm'] == 'Anna Müller'
    assert d['portfolio_summary']['top_5_positions']
    assert isinstance(d['vs_ips']['asset_class_drift'], list)
    assert isinstance(d['next_best_actions'], list)


def test_briefing_concise_default_strips_ids():
    """In concise mode, position_id, isin, client_id should not appear in data."""
    out = _unwrap(kb.cpb_prepare_client_briefing('cli-001'))
    blob = json.dumps(out['data'])
    assert 'position_id' not in blob
    assert 'isin' not in blob


def test_briefing_detailed_keeps_ids():
    out = _unwrap(kb.cpb_prepare_client_briefing('cli-001', response_format='detailed'))
    blob = json.dumps(out['data'])
    assert 'isin' in blob


def test_briefing_unknown_client_returns_actionable_error():
    err = _err(kb.cpb_prepare_client_briefing('cli-999'))
    assert err['code'] == 'client_not_found'
    assert 'cli-001' in err['message']
    assert err['next_steps'] and any('cli-001' in s for s in err['next_steps'])


def test_briefing_meeting_purpose_echoed():
    out = _unwrap(kb.cpb_prepare_client_briefing('cli-002', meeting_purpose='ips_review'))
    assert out['data']['meeting_purpose'] == 'ips_review'


def test_briefing_picks_up_drift_for_lindemann_pe():
    """cli-003 has a deliberately drifted PE sleeve; alts should be over band."""
    out = _unwrap(kb.cpb_prepare_client_briefing('cli-003'))
    flags = [r for r in out['data']['vs_ips']['asset_class_drift'] if r['severity'] != 'within_band']
    assert flags, "expected at least one drift flag for cli-003"


def test_briefing_concentration_flag_for_muller_legacy_stake():
    """cli-004 has Müller Holding AG > 10% IPS cap; concentration flag should fire."""
    out = _unwrap(kb.cpb_prepare_client_briefing('cli-004', response_format='detailed'))
    flags = out['data']['vs_ips']['concentration_flags']
    assert any(f['isin'] == 'XX0000000015' for f in flags), \
        f"expected legacy stake to be flagged; got: {flags}"


def test_briefing_recent_transactions_within_30d():
    """All transactions in the briefing's 30d window must be on/after 2026-04-10."""
    out = _unwrap(kb.cpb_prepare_client_briefing('cli-001'))
    for t in out['data']['recent_transactions_30d']:
        assert t['trade_date'] >= '2026-04-10'


def test_briefing_crm_flags_within_90d():
    out = _unwrap(kb.cpb_prepare_client_briefing('cli-001'))
    for e in out['data']['crm_flags_90d']:
        assert e['event_date'] >= '2026-02-09'


def test_briefing_summary_is_human_readable():
    out = _unwrap(kb.cpb_prepare_client_briefing('cli-002'))
    s = out['summary']
    assert 'Eichmann Foundation' in s
    assert 'AUM' in s


def test_briefing_next_steps_present():
    out = _unwrap(kb.cpb_prepare_client_briefing('cli-001'))
    assert out['next_steps'], "next_steps should be present even on success"


# ── cpb_get_client_context ────────────────────────────────────────────────────


def test_get_client_context_happy():
    out = _unwrap(kb.cpb_get_client_context('cli-002'))
    assert out['data']['client']['name'] == 'Eichmann Foundation'
    assert out['data']['ips']['target_allocation_pct']['fixed_income'] == 60.0


def test_get_client_context_unknown_errors():
    err = _err(kb.cpb_get_client_context('cli-zzz'))
    assert err['code'] == 'client_not_found'


# ── cpb_analyze_portfolio_drift ───────────────────────────────────────────────


def test_drift_default_threshold_filters():
    out = _unwrap(kb.cpb_analyze_portfolio_drift('cli-001', threshold_pp=3.0))
    for r in out['data']['asset_class_drift']:
        assert abs(r['drift_pp']) >= 3.0


def test_drift_low_threshold_returns_more_rows():
    high = _unwrap(kb.cpb_analyze_portfolio_drift('cli-001', threshold_pp=10.0))
    low = _unwrap(kb.cpb_analyze_portfolio_drift('cli-001', threshold_pp=0.0))
    assert len(low['data']['asset_class_drift']) >= len(high['data']['asset_class_drift'])


def test_drift_severity_labels_present():
    out = _unwrap(kb.cpb_analyze_portfolio_drift('cli-003', threshold_pp=0.0))
    for r in out['data']['asset_class_drift']:
        assert r['severity'] in {'within_band', 'over_band', 'material_breach'}


def test_drift_unknown_client_errors():
    err = _err(kb.cpb_analyze_portfolio_drift('cli-zzz'))
    assert err['code'] == 'client_not_found'


def test_drift_riedi_pension_ldi_mostly_within_band():
    """Pension cli-005 has tight 2pp band; should be largely conservative drift."""
    out = _unwrap(kb.cpb_analyze_portfolio_drift('cli-005', threshold_pp=0.0))
    rows = out['data']['asset_class_drift']
    breaches = [r for r in rows if r['severity'] == 'material_breach']
    assert len(breaches) <= 1, f"expected pension to be largely in-line, got breaches: {breaches}"


# ── cpb_find_relevant_research ────────────────────────────────────────────────


def test_find_research_requires_a_filter():
    err = _err(kb.cpb_find_relevant_research())
    assert err['code'] == 'no_filter_supplied'


def test_find_research_by_isin():
    out = _unwrap(kb.cpb_find_relevant_research(isin='XX0000000005'))
    assert out['data']
    for r in out['data']:
        if r.get('isin') is not None:
            assert r['isin'] == 'XX0000000005' or 'XX0000000005' in (r.get('excerpt') or '')


def test_find_research_by_query():
    out = _unwrap(kb.cpb_find_relevant_research(query='AI capex'))
    assert any('AI' in r['title'] or any('ai' in t for t in r.get('tags', [])) for r in out['data'])


def test_find_research_by_client_expands_to_holdings():
    """cli-001 (Berger) holds the Climate Solutions and AI Infra funds; find should
    return notes for those instruments without me passing the ISINs."""
    # Use detailed mode so ISINs survive the response shaping.
    out = _unwrap(kb.cpb_find_relevant_research(
        client_id='cli-001', max_results=20, response_format='detailed'))
    isins = {r.get('isin') for r in out['data'] if r.get('isin')}
    assert 'XX0000000013' in isins or 'XX0000000005' in isins


def test_find_research_pagination_truncation():
    out = _unwrap(kb.cpb_find_relevant_research(query='market', max_results=2))
    assert out['truncated'] in (True, False)
    if out['truncated']:
        assert out['more_with'] is not None


def test_find_research_unknown_client_errors():
    err = _err(kb.cpb_find_relevant_research(client_id='cli-zzz'))
    assert err['code'] == 'client_not_found'


# ── cpb_summarize_recent_activity ─────────────────────────────────────────────


def test_summarize_activity_intent_breakdown():
    out = _unwrap(kb.cpb_summarize_recent_activity('cli-001', days=90))
    assert out['data']['transaction_count'] >= 1
    assert isinstance(out['data']['intent_breakdown'], dict)
    for v in out['data']['intent_breakdown'].values():
        assert 'count' in v
        assert 'gross_chf' in v
        assert 'net_chf' in v


def test_summarize_activity_zero_results_actionable_hint():
    out = _unwrap(kb.cpb_summarize_recent_activity('cli-001', days=1))
    assert out['data']['transaction_count'] == 0
    assert out['next_steps'] and any('90' in s for s in out['next_steps'])


def test_summarize_activity_unknown_client_errors():
    err = _err(kb.cpb_summarize_recent_activity('cli-zzz'))
    assert err['code'] == 'client_not_found'


# ── cpb_run_query (escape hatch) ──────────────────────────────────────────────


def test_run_query_no_collection_errors_actionably():
    err = _err(kb.cpb_run_query())
    assert err['code'] == 'collection_required'
    assert any('clients' in s for s in err['next_steps'])


def test_run_query_lists_clients():
    out = _unwrap(kb.cpb_run_query(collection='clients'))
    assert len(out['data']) == 5
    assert all('name' in c for c in out['data'])


def test_run_query_pagination():
    out = _unwrap(kb.cpb_run_query(collection='instruments', page=1, page_size=5))
    assert len(out['data']) == 5
    assert out['truncated']
    assert out['more_with'] == {'page': 2, 'page_size': 5}
    out2 = _unwrap(kb.cpb_run_query(collection='instruments', page=2, page_size=5))
    assert len(out2['data']) == 5
    assert out2['data'][0]['isin'] != out['data'][0]['isin']


def test_run_query_filter():
    out = _unwrap(kb.cpb_run_query(collection='transactions',
                                   filter_field='client_id', filter_value='cli-001'))
    assert all(t['client_id'] == 'cli-001' for t in out['data'])


def test_run_query_fetch_research_doc():
    out = _unwrap(kb.cpb_run_query(collection='research', doc_id='res-003'))
    assert 'AI infrastructure' in out['data']['title']
    assert 'content' in out['data']


def test_run_query_unknown_doc_errors():
    err = _err(kb.cpb_run_query(collection='research', doc_id='res-999'))
    assert err['code'] == 'document_not_found'


def test_run_query_market_data_special_collection():
    out = _unwrap(kb.cpb_run_query(collection='market_data'))
    assert 'fx_to_chf' in out['data']
    assert 'instrument_marks' in out['data']


def test_run_query_unknown_collection_errors():
    err = _err(kb.cpb_run_query(collection='nope'))
    assert err['code'] == 'unknown_collection'


# ── Cross-cutting contract tests ──────────────────────────────────────────────


@pytest.mark.parametrize('call', [
    lambda: kb.cpb_prepare_client_briefing('cli-001'),
    lambda: kb.cpb_get_client_context('cli-001'),
    lambda: kb.cpb_analyze_portfolio_drift('cli-001'),
    lambda: kb.cpb_find_relevant_research(client_id='cli-001'),
    lambda: kb.cpb_summarize_recent_activity('cli-001'),
    lambda: kb.cpb_run_query(collection='clients'),
])
def test_every_success_response_has_envelope(call):
    out = json.loads(call())
    assert 'error' not in out
    for k in ('data', 'summary', 'citations', 'truncated', 'more_with', 'next_steps'):
        assert k in out, f"envelope missing {k} in {call.__name__}"


@pytest.mark.parametrize('call', [
    lambda: kb.cpb_prepare_client_briefing('cli-zzz'),
    lambda: kb.cpb_get_client_context('cli-zzz'),
    lambda: kb.cpb_analyze_portfolio_drift('cli-zzz'),
    lambda: kb.cpb_find_relevant_research(client_id='cli-zzz'),
    lambda: kb.cpb_summarize_recent_activity('cli-zzz'),
    lambda: kb.cpb_run_query(),
])
def test_every_error_response_has_actionable_next_steps(call):
    out = json.loads(call())
    assert 'error' in out
    err = out['error']
    assert err['code']
    assert err['message']
    assert err['next_steps'], f"every error must offer next_steps; got: {err}"
