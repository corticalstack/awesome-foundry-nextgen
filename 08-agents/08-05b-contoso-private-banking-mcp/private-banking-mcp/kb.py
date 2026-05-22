"""Contoso Private Banking - intent-level knowledge base.

Pedagogical contrast with 08-05-contoso-pmo-mcp/kb.py:

  08-05 wraps 37 CRUD endpoints (create_project, get_project, list_projects, ...).
  This module exposes 6 intent-level operations that match what the user (a Swiss
  private-banking RM) actually does in their day. Joins, filters, drift math,
  and citation-stitching all happen here on the server, not in the agent context.

  See 08-05b-00-contoso-private-banking-mcp.md for the full design rationale and
  the "Writing effective tools for AI agents" reference.

All functions return JSON strings. Reads are direct from DATA_DIR. There are no
write operations: the demo workflow is read-and-synthesise, not state mutation.
HITL trade-execution would live in a separate intent (e.g. cpb_propose_trade with
require_approval) and is intentionally out of scope here.
"""

import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

DATA_DIR: Path = Path(os.environ.get(
    'DATA_DIR',
    str(Path(__file__).parent / '..' / '..' / '..' / 'assets' / 'contoso-private-banking-dataset')
))

CLIENT_ID_PREFIX = 'cli-'

# "Today" for relative-date math. Defaults to the dataset's as-of date so the demo
# is reproducible regardless of when it runs. Override with ENV TODAY=YYYY-MM-DD.
def _today() -> date:
    raw = os.environ.get('TODAY', '2026-05-10')
    return datetime.strptime(raw, '%Y-%m-%d').date()


# ── Internal helpers ──────────────────────────────────────────────────────────

def _load(path: Path) -> Any:
    with open(path) as f:
        return json.load(f)


def _ok(data: Any, summary: str, citations: list[dict] | None = None,
        truncated: bool = False, more_with: dict | None = None,
        next_steps: list[str] | None = None) -> str:
    """Wrap a successful response in the standard envelope."""
    return json.dumps({
        'data': data,
        'summary': summary,
        'citations': citations or [],
        'truncated': truncated,
        'more_with': more_with,
        'next_steps': next_steps or [],
    })


def _err(code: str, message: str, next_steps: list[str]) -> str:
    """Wrap an error in the standard envelope.

    next_steps is mandatory: every error tells the agent what to try instead.
    """
    return json.dumps({
        'error': {
            'code': code,
            'message': message,
            'next_steps': next_steps,
        }
    })


def _client(client_id: str) -> dict | None:
    for c in _load(DATA_DIR / 'registry' / 'clients.json'):
        if c['id'] == client_id:
            return c
    return None


def _client_or_err(client_id: str) -> tuple[dict | None, str | None]:
    """Return (client_dict, None) on hit; (None, error_json_string) on miss."""
    c = _client(client_id)
    if c is not None:
        return c, None
    valid = [x['id'] for x in _load(DATA_DIR / 'registry' / 'clients.json')]
    err = _err(
        code='client_not_found',
        message=f"Client {client_id!r} not found. Known clients: {', '.join(valid)}.",
        next_steps=[
            f"Retry with one of the known client IDs: {', '.join(valid)}",
            "Or call cpb_run_query with collection='clients' to list clients with names",
        ],
    )
    return None, err


def _ips(client_id: str) -> dict | None:
    for i in _load(DATA_DIR / 'registry' / 'ips.json'):
        if i['client_id'] == client_id:
            return i
    return None


def _instruments_index() -> dict[str, dict]:
    return {i['isin']: i for i in _load(DATA_DIR / 'registry' / 'instruments.json')}


def _market() -> dict:
    return _load(DATA_DIR / 'registry' / 'market_data.json')


def _portfolio_positions(client_id: str) -> list[dict]:
    for p in _load(DATA_DIR / 'registry' / 'portfolios.json'):
        if p['client_id'] == client_id:
            return p['positions']
    return []


def _value_position_chf(position: dict, instruments: dict, market: dict) -> tuple[float, dict]:
    """Return (market_value_chf, enriched_position_dict)."""
    isin = position['isin']
    inst = instruments.get(isin, {})
    mark = market['instrument_marks'].get(isin, {})
    fx = market['fx_to_chf'].get(mark.get('currency', 'CHF'), 1.0)
    price = mark.get('price', 0.0)
    qty = position['quantity']
    mv_local = qty * price
    mv_chf = mv_local * fx
    enriched = {
        **position,
        'instrument_name': inst.get('name'),
        'instrument_type': inst.get('instrument_type'),
        'asset_class': inst.get('asset_class'),
        'region': inst.get('region'),
        'currency': mark.get('currency'),
        'price': price,
        'market_value_local': round(mv_local, 2),
        'market_value_chf': round(mv_chf, 2),
        'esg_score': inst.get('esg_score'),
    }
    return mv_chf, enriched


def _aggregate(positions_enriched: list[dict], total_chf: float, key: str) -> dict[str, float]:
    """Return {bucket -> percent}."""
    buckets: dict[str, float] = {}
    for p in positions_enriched:
        bucket = p.get(key) or 'unknown'
        buckets[bucket] = buckets.get(bucket, 0.0) + p['market_value_chf']
    return {k: round(v / total_chf * 100, 2) for k, v in buckets.items()} if total_chf else {}


def _drift_table(actual: dict[str, float], target: dict[str, float]) -> list[dict]:
    """Return [{bucket, target_pct, actual_pct, drift_pp, severity}], sorted by |drift| desc."""
    rows = []
    for bucket in set(target) | set(actual):
        a = actual.get(bucket, 0.0)
        t = target.get(bucket, 0.0)
        d = round(a - t, 2)
        rows.append({
            'bucket': bucket,
            'target_pct': t,
            'actual_pct': a,
            'drift_pp': d,
        })
    rows.sort(key=lambda r: abs(r['drift_pp']), reverse=True)
    return rows


def _severity(drift_pp: float, band_pp: float) -> str:
    a = abs(drift_pp)
    if a < band_pp:
        return 'within_band'
    if a < band_pp * 2:
        return 'over_band'
    return 'material_breach'


def _doc(folder: str, doc_id: str) -> dict | None:
    path = DATA_DIR / folder / f'{doc_id}.json'
    if path.exists():
        return _load(path)
    return None


def _sanitise_for_concise(obj: Any, drop_keys: set[str]) -> Any:
    """Strip ID-flavoured keys recursively for the 'concise' response format."""
    if isinstance(obj, dict):
        return {k: _sanitise_for_concise(v, drop_keys) for k, v in obj.items() if k not in drop_keys}
    if isinstance(obj, list):
        return [_sanitise_for_concise(v, drop_keys) for v in obj]
    return obj


_CONCISE_DROP = {'position_id', 'isin', 'client_id', 'id'}


def _shape(data: Any, response_format: str) -> Any:
    if response_format == 'detailed':
        return data
    return _sanitise_for_concise(data, _CONCISE_DROP)


# ── Core analytics (private; reused across intent tools) ──────────────────────

def _value_portfolio(client_id: str) -> dict:
    """Return {total_chf, positions_enriched, by_asset_class, by_region, esg_weighted}."""
    instruments = _instruments_index()
    market = _market()
    enriched = []
    total = 0.0
    for p in _portfolio_positions(client_id):
        mv, e = _value_position_chf(p, instruments, market)
        total += mv
        enriched.append(e)
    enriched.sort(key=lambda p: p['market_value_chf'], reverse=True)
    by_asset = _aggregate(enriched, total, 'asset_class')
    by_region = _aggregate(enriched, total, 'region')
    esg_weighted = round(
        sum((p['esg_score'] or 0) * p['market_value_chf'] for p in enriched) / total, 2
    ) if total else 0.0
    return {
        'total_chf': round(total, 2),
        'positions': enriched,
        'by_asset_class_pct': by_asset,
        'by_region_pct': by_region,
        'esg_weighted_score': esg_weighted,
    }


def _drift_for_client(client_id: str) -> dict:
    val = _value_portfolio(client_id)
    ips = _ips(client_id) or {}
    band = ips.get('rebalance_band_pp', 3.0)
    asset_drift = _drift_table(val['by_asset_class_pct'], ips.get('target_allocation_pct', {}))
    region_drift = _drift_table(val['by_region_pct'], ips.get('regional_targets_pct', {}))
    for row in asset_drift:
        row['severity'] = _severity(row['drift_pp'], band)
    for row in region_drift:
        row['severity'] = _severity(row['drift_pp'], band)
    # The IPS max_single_position_pct is a single-name concentration rule;
    # it applies to direct holdings, not pooled fund vehicles (which are diversified
    # by construction). Skip fund positions to avoid spurious flags.
    concentration_flags = []
    max_pos = ips.get('max_single_position_pct', 100.0)
    for p in val['positions']:
        if p.get('instrument_type') != 'direct_single_name':
            continue
        pct = p['market_value_chf'] / val['total_chf'] * 100 if val['total_chf'] else 0
        if pct > max_pos:
            concentration_flags.append({
                'instrument_name': p['instrument_name'],
                'isin': p['isin'],
                'position_pct': round(pct, 2),
                'max_allowed_pct': max_pos,
                'over_by_pp': round(pct - max_pos, 2),
            })
    esg_flag = None
    floor = ips.get('esg_floor_score')
    if floor is not None and val['esg_weighted_score'] < floor:
        esg_flag = {
            'esg_weighted_score': val['esg_weighted_score'],
            'floor': floor,
            'short_by': round(floor - val['esg_weighted_score'], 2),
        }
    return {
        'client_id': client_id,
        'total_chf': val['total_chf'],
        'rebalance_band_pp': band,
        'asset_class_drift': asset_drift,
        'regional_drift': region_drift,
        'concentration_flags': concentration_flags,
        'esg_floor_breach': esg_flag,
    }


def _research_touching_holdings(client_id: str) -> list[dict]:
    held_isins = {p['isin'] for p in _portfolio_positions(client_id)}
    out = []
    for r in _load(DATA_DIR / 'research' / 'index.json'):
        if r.get('isin') in held_isins:
            doc = _doc('research', r['id']) or r
            out.append(doc)
    return out


def _commentary_touching_holdings(client_id: str) -> list[dict]:
    """Pick commentary whose tags overlap holdings' regions/asset classes."""
    instruments = _instruments_index()
    held_regions = set()
    held_asset_classes = set()
    for p in _portfolio_positions(client_id):
        inst = instruments.get(p['isin'], {})
        if inst.get('region'):
            held_regions.add(inst['region'])
        if inst.get('asset_class'):
            held_asset_classes.add(inst['asset_class'])
    interest_tags = held_regions | held_asset_classes | {'macro', 'rates', 'fx'}
    out = []
    for c in _load(DATA_DIR / 'market_commentary' / 'index.json'):
        if any(t in interest_tags for t in c.get('tags', [])):
            doc = _doc('market_commentary', c['id']) or c
            out.append(doc)
    return out


def _recent_transactions(client_id: str, days: int) -> list[dict]:
    cutoff = _today() - timedelta(days=days)
    out = []
    for t in _load(DATA_DIR / 'registry' / 'transactions.json'):
        if t['client_id'] != client_id:
            continue
        td = datetime.strptime(t['trade_date'], '%Y-%m-%d').date()
        if td >= cutoff:
            out.append(t)
    out.sort(key=lambda t: t['trade_date'], reverse=True)
    return out


def _crm_recent(client_id: str, days: int) -> list[dict]:
    cutoff = _today() - timedelta(days=days)
    out = []
    for e in _load(DATA_DIR / 'registry' / 'crm_events.json'):
        if e['client_id'] != client_id:
            continue
        ed = datetime.strptime(e['event_date'], '%Y-%m-%d').date()
        if ed >= cutoff:
            out.append(e)
    out.sort(key=lambda e: e['event_date'], reverse=True)
    return out


def _next_best_actions(client_id: str, drift: dict, crm: list[dict]) -> list[str]:
    """Heuristic-derived RM-facing talking points. Not a recommendation engine."""
    actions = []
    for row in drift['asset_class_drift']:
        if row['severity'] in ('over_band', 'material_breach'):
            direction = 'trim' if row['drift_pp'] > 0 else 'add'
            actions.append(
                f"{row['bucket']} is {row['drift_pp']:+.1f}pp vs target - discuss {direction} at next review."
            )
    for f in drift['concentration_flags']:
        actions.append(
            f"{f['instrument_name']} is {f['position_pct']:.1f}% of AUM (cap {f['max_allowed_pct']}%) - review concentration policy."
        )
    if drift['esg_floor_breach']:
        b = drift['esg_floor_breach']
        actions.append(
            f"ESG composite {b['esg_weighted_score']} is below the {b['floor']} floor - discuss ESG-tilted reweighting."
        )
    for e in crm:
        if e.get('follow_up_required'):
            due = f" (due {e['due_by']})" if e.get('due_by') else ''
            actions.append(f"CRM follow-up: {e['summary']}{due}")
    return actions


# ── Intent-level tools (the public surface) ───────────────────────────────────


def cpb_prepare_client_briefing(
    client_id: str,
    meeting_purpose: str = 'quarterly_review',
    response_format: str = 'concise',
) -> str:
    """The headline intent. Returns a fully-stitched RM briefing for one client.

    The naive endpoint-style decomposition would be 10+ separate calls
    (list_clients, get_client, get_ips, list_holdings, list_transactions,
    list_crm_events, get_market_data, search_research, search_commentary,
    compute_drift). All joined and synthesised here.
    """
    client, err = _client_or_err(client_id)
    if err:
        return err

    val = _value_portfolio(client_id)
    drift = _drift_for_client(client_id)
    txns = _recent_transactions(client_id, days=30)
    crm = _crm_recent(client_id, days=90)
    research = _research_touching_holdings(client_id)
    commentary = _commentary_touching_holdings(client_id)
    nba = _next_best_actions(client_id, drift, crm)

    brief = {
        'client': {
            'name': client['name'],
            'segment': client['segment'],
            'rm': client['rm'],
            'base_currency': client['base_currency'],
            'aum_chf_book': client['aum_chf'],
            'aum_chf_calc': val['total_chf'],
            'next_review_date': client['next_review_date'],
            'languages': client['languages'],
        },
        'meeting_purpose': meeting_purpose,
        'as_of': _today().isoformat(),
        'portfolio_summary': {
            'by_asset_class_pct': val['by_asset_class_pct'],
            'by_region_pct': val['by_region_pct'],
            'esg_weighted_score': val['esg_weighted_score'],
            'top_5_positions': [
                {
                    'instrument_name': p['instrument_name'],
                    'asset_class': p['asset_class'],
                    'market_value_chf': p['market_value_chf'],
                    'pct_of_aum': round(p['market_value_chf'] / val['total_chf'] * 100, 2),
                }
                for p in val['positions'][:5]
            ],
        },
        'vs_ips': {
            'rebalance_band_pp': drift['rebalance_band_pp'],
            'asset_class_drift': drift['asset_class_drift'],
            'concentration_flags': drift['concentration_flags'],
            'esg_floor_breach': drift['esg_floor_breach'],
        },
        'recent_transactions_30d': txns,
        'crm_flags_90d': crm,
        'relevant_research': [
            {'title': r['title'], 'isin': r.get('isin'), 'published': r['published']}
            for r in research
        ],
        'relevant_commentary': [
            {'title': c['title'], 'tags': c['tags'], 'published': c['published']}
            for c in commentary
        ],
        'next_best_actions': nba,
    }

    citations = (
        [{'source': f"ips/{client_id}", 'as_of': (_ips(client_id) or {}).get('as_of')}]
        + [{'source': f"research/{r['id']}", 'title': r['title']} for r in research]
        + [{'source': f"market_commentary/{c['id']}", 'title': c['title']} for c in commentary]
        + [{'source': f"crm/{e['id']}", 'summary': e['summary'][:80]} for e in crm]
    )

    summary = (
        f"Briefing for {client['name']} ({client['segment']}, RM {client['rm']}): "
        f"AUM CHF {val['total_chf']:,.0f}; {len([r for r in drift['asset_class_drift'] if r['severity'] != 'within_band'])} "
        f"asset-class drift flag(s); {len(drift['concentration_flags'])} concentration flag(s); "
        f"{len(crm)} CRM event(s) in last 90d; {len(nba)} next-best-action(s)."
    )

    shaped = _shape(brief, response_format)
    return _ok(shaped, summary, citations=citations,
               next_steps=[
                   "Call cpb_analyze_portfolio_drift for a deeper drift breakdown",
                   "Call cpb_find_relevant_research with a specific ISIN or query for source documents",
                   "Set response_format='detailed' to get position_ids and ISINs for chained calls",
               ])


def cpb_get_client_context(client_id: str, response_format: str = 'concise') -> str:
    """Lightweight intent - identity + IPS + RM + segment, without portfolio synthesis.

    Use when the agent needs the basics without paying for the briefing's compute.
    """
    client, err = _client_or_err(client_id)
    if err:
        return err
    ips = _ips(client_id)
    data = {
        'client': {
            'name': client['name'],
            'segment': client['segment'],
            'rm': client['rm'],
            'rm_email': client['rm_email'],
            'base_currency': client['base_currency'],
            'aum_chf_book': client['aum_chf'],
            'next_review_date': client['next_review_date'],
            'languages': client['languages'],
            'tags': client['tags'],
        },
        'ips': ips,
    }
    summary = f"{client['name']} - {client['segment']}, base {client['base_currency']}, RM {client['rm']}, IPS as of {ips['as_of'] if ips else 'n/a'}."
    return _ok(_shape(data, response_format), summary,
               citations=[{'source': f'ips/{client_id}', 'as_of': ips['as_of'] if ips else None}],
               next_steps=[
                   "Call cpb_prepare_client_briefing for the full meeting brief",
                   "Call cpb_analyze_portfolio_drift to inspect drift only",
               ])


def cpb_analyze_portfolio_drift(
    client_id: str,
    threshold_pp: float = 3.0,
    response_format: str = 'concise',
) -> str:
    """Drift-only deep dive. Returns asset-class, regional, concentration, and ESG drift.

    Filters drift table to rows where |drift_pp| >= threshold_pp.
    """
    client, err = _client_or_err(client_id)
    if err:
        return err
    drift = _drift_for_client(client_id)
    asset_filtered = [r for r in drift['asset_class_drift'] if abs(r['drift_pp']) >= threshold_pp]
    region_filtered = [r for r in drift['regional_drift'] if abs(r['drift_pp']) >= threshold_pp]
    data = {
        'client_name': client['name'],
        'rebalance_band_pp': drift['rebalance_band_pp'],
        'threshold_pp': threshold_pp,
        'asset_class_drift': asset_filtered,
        'regional_drift': region_filtered,
        'concentration_flags': drift['concentration_flags'],
        'esg_floor_breach': drift['esg_floor_breach'],
    }
    breaches = sum(1 for r in asset_filtered + region_filtered
                   if r['severity'] in ('over_band', 'material_breach'))
    summary = (
        f"{client['name']}: {len(asset_filtered)} asset-class drift row(s), "
        f"{len(region_filtered)} regional drift row(s) at ≥ {threshold_pp}pp; "
        f"{len(drift['concentration_flags'])} concentration flag(s); {breaches} severity-flagged."
    )
    return _ok(_shape(data, response_format), summary,
               citations=[{'source': f'ips/{client_id}'}, {'source': f'portfolio/{client_id}'}],
               next_steps=[
                   "Call cpb_prepare_client_briefing for context around the drift",
                   "Call cpb_find_relevant_research with isin=<top-driver ISIN> for what's driving the move",
               ])


def cpb_find_relevant_research(
    client_id: str | None = None,
    query: str | None = None,
    isin: str | None = None,
    max_results: int = 5,
    response_format: str = 'concise',
) -> str:
    """Search research + commentary + regulatory by client (expands to holdings),
    by ISIN, or by free-text tag/title match. Multiple filters combine (intersection).
    """
    if not (client_id or query or isin):
        return _err(
            code='no_filter_supplied',
            message='Supply at least one of client_id, query, isin to scope the search.',
            next_steps=[
                "Pass client_id='cli-001' to find research touching that client's holdings",
                "Pass isin='XX0000000005' to find research on a specific instrument",
                "Pass query='AI capex' for free-text match against titles and tags",
            ],
        )

    if client_id:
        client, err = _client_or_err(client_id)
        if err:
            return err

    held_isins: set[str] = set()
    if client_id:
        held_isins = {p['isin'] for p in _portfolio_positions(client_id)}

    query_lc = query.lower() if query else None

    def matches(meta: dict, content_text: str) -> bool:
        if isin is not None and meta.get('isin') != isin:
            return False
        if client_id and meta.get('isin') and meta['isin'] not in held_isins:
            # Allow tag-only matches for client when no ISIN is on the doc (commentary/regulatory).
            if not (query_lc and (query_lc in meta.get('title', '').lower()
                                  or any(query_lc in t.lower() for t in meta.get('tags', [])))):
                return False
        if query_lc:
            haystack = (meta.get('title', '') + ' ' + ' '.join(meta.get('tags', [])) + ' ' + content_text).lower()
            if query_lc not in haystack:
                # Allow per-token match
                tokens = [t for t in query_lc.split() if len(t) >= 3]
                if not tokens or not any(t in haystack for t in tokens):
                    return False
        return True

    results = []
    for folder in ('research', 'market_commentary', 'regulatory'):
        index = _load(DATA_DIR / folder / 'index.json')
        for meta in index:
            doc = _doc(folder, meta['id']) or meta
            content_text = doc.get('content', '')
            if matches({**meta, **doc}, content_text):
                results.append({
                    'source': folder,
                    'id': meta['id'],
                    'title': meta['title'],
                    'isin': meta.get('isin'),
                    'tags': meta.get('tags', []),
                    'published': meta.get('published'),
                    'excerpt': content_text[:300],
                })

    results.sort(key=lambda r: r.get('published', ''), reverse=True)
    truncated = len(results) > max_results
    page = results[:max_results]

    summary = (
        f"{len(page)} result(s) across research/commentary/regulatory"
        + (f" for client {client_id}" if client_id else '')
        + (f", isin={isin}" if isin else '')
        + (f", query={query!r}" if query else '')
        + (f"; truncated from {len(results)}" if truncated else '')
    )

    citations = [{'source': f"{r['source']}/{r['id']}", 'title': r['title']} for r in page]
    return _ok(_shape(page, response_format), summary, citations=citations,
               truncated=truncated,
               more_with={'max_results': len(results)} if truncated else None,
               next_steps=[
                   "Call cpb_run_query with collection='research' and a doc_id to get full content",
               ] if truncated else [])


def cpb_summarize_recent_activity(
    client_id: str,
    days: int = 30,
    response_format: str = 'concise',
) -> str:
    """Group transactions by intent and return a one-paragraph human summary
    plus a per-intent breakdown.
    """
    client, err = _client_or_err(client_id)
    if err:
        return err
    txns = _recent_transactions(client_id, days)
    if not txns:
        return _ok(
            data={
                'client_name': client['name'],
                'days': days,
                'transaction_count': 0,
                'intent_breakdown': {},
                'transactions': [],
            },
            summary=f"{client['name']}: no transactions in the last {days} days.",
            next_steps=[f"Try a longer window: cpb_summarize_recent_activity(client_id={client_id!r}, days=90)"],
        )
    by_intent: dict[str, dict] = {}
    for t in txns:
        intent = t['intent']
        b = by_intent.setdefault(intent, {'count': 0, 'gross_chf': 0.0, 'net_chf': 0.0})
        b['count'] += 1
        amt = t['amount_chf'] or 0
        b['gross_chf'] += abs(amt)
        if t['type'] in ('buy', 'subscription', 'capital_call'):
            b['net_chf'] += amt
        elif t['type'] in ('sell', 'redemption', 'distribution'):
            b['net_chf'] -= amt
    for v in by_intent.values():
        v['gross_chf'] = round(v['gross_chf'], 2)
        v['net_chf'] = round(v['net_chf'], 2)
    data = {
        'client_name': client['name'],
        'days': days,
        'transaction_count': len(txns),
        'intent_breakdown': by_intent,
        'transactions': txns,
    }
    summary = (
        f"{client['name']}: {len(txns)} transactions over {days}d, "
        f"intents: {', '.join(sorted(by_intent.keys()))}."
    )
    return _ok(_shape(data, response_format), summary,
               citations=[{'source': f'transactions/{client_id}', 'window_days': days}],
               next_steps=[
                   "Call cpb_prepare_client_briefing for the next-best-actions tied to this activity",
               ])


def cpb_run_query(
    collection: str | None = None,
    filter_field: str | None = None,
    filter_value: str | None = None,
    doc_id: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> str:
    """Read-only escape hatch for unusual workflows the intent tools don't cover.

    Prefer the intent tools (cpb_prepare_client_briefing, cpb_analyze_portfolio_drift,
    cpb_find_relevant_research, cpb_summarize_recent_activity, cpb_get_client_context)
    when they fit. This tool exists for the long tail.

    Modes:
      - List a registry collection: collection='clients' (or 'ips', 'portfolios',
        'transactions', 'crm_events', 'instruments').
      - List a document index: collection='research' (or 'market_commentary',
        'regulatory') - returns the index without content.
      - Fetch document content: collection='research', doc_id='res-001' (also
        'market_commentary' and 'regulatory').
      - Filter: pass filter_field + filter_value to keep only records where that
        field exact-matches the value.
    """
    REGISTRY = {'clients', 'ips', 'portfolios', 'transactions', 'crm_events', 'instruments'}
    DOC_FOLDERS = {'research', 'market_commentary', 'regulatory'}
    if collection is None:
        return _err(
            code='collection_required',
            message="Pass collection: one of " + ', '.join(sorted(REGISTRY | DOC_FOLDERS)) + '.',
            next_steps=[
                "cpb_run_query(collection='clients') to list all clients",
                "cpb_run_query(collection='research', doc_id='res-001') to fetch a research doc",
            ],
        )
    if collection == 'market_data':
        return _ok(_market(), summary='Market data snapshot (FX + instrument marks).')
    if collection in REGISTRY:
        path = DATA_DIR / 'registry' / f'{collection}.json'
        if not path.exists():
            return _err(code='unknown_collection',
                        message=f'No such registry collection: {collection!r}',
                        next_steps=[f"Try one of: {', '.join(sorted(REGISTRY))}"])
        records = _load(path)
        if not isinstance(records, list):
            records = [records]
    elif collection in DOC_FOLDERS:
        if doc_id:
            doc = _doc(collection, doc_id)
            if doc is None:
                return _err(
                    code='document_not_found',
                    message=f"No document {doc_id!r} in {collection}.",
                    next_steps=[f"cpb_run_query(collection={collection!r}) to list available IDs"],
                )
            return _ok(doc, summary=f"{collection}/{doc_id}: {doc.get('title', '')}",
                       citations=[{'source': f'{collection}/{doc_id}'}])
        records = _load(DATA_DIR / collection / 'index.json')
    else:
        return _err(code='unknown_collection',
                    message=f'Unknown collection: {collection!r}',
                    next_steps=[f"Use one of: {', '.join(sorted(REGISTRY | DOC_FOLDERS))}"])
    if filter_field and filter_value is not None:
        records = [r for r in records if str(r.get(filter_field)) == str(filter_value)]
    total = len(records)
    start = (page - 1) * page_size
    end = start + page_size
    page_records = records[start:end]
    has_more = end < total
    return _ok(
        data=page_records,
        summary=f"{collection}: {len(page_records)} of {total} record(s), page {page}.",
        truncated=has_more,
        more_with={'page': page + 1, 'page_size': page_size} if has_more else None,
    )
