"""Contoso Private Banking — intent-level MCP tool surface.

Six tools (cpb_*) cover the RM morning-briefing workflow. Compare with
../08-05-contoso-pmo-mcp/contoso-pmo-mcp/function_app.py which has 37 endpoint-style
tools — the contrast is the lesson.

Each tool wrapper just unpacks the call context and delegates to kb.py. All
business logic, joins, drift math, citation stitching, and response shaping
live in kb.py — that is the point. The agent gets one verb; the server does
the work.
"""

import json

import azure.functions as func

import kb

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


# ── Tool property descriptors ─────────────────────────────────────────────────

_RESPONSE_FORMAT_DESC = (
    "Response format. 'concise' (default) returns names/dates/amounts only — "
    "best for synthesis prompts. 'detailed' adds position_id, isin, client_id, "
    "and other identifiers — use when you need to chain a follow-up call."
)

_prepare_briefing_props = json.dumps([
    {'propertyName': 'client_id', 'propertyType': 'string',
     'description': "Client ID (e.g. 'cli-001'). List clients with cpb_run_query(collection='clients')."},
    {'propertyName': 'meeting_purpose', 'propertyType': 'string',
     'description': "Free-text label for the meeting type (default 'quarterly_review'). Examples: 'ad_hoc', 'ips_review', 'esg_discussion'. Currently echoed in the response; reserved for future routing."},
    {'propertyName': 'response_format', 'propertyType': 'string',
     'description': _RESPONSE_FORMAT_DESC},
])

_get_client_context_props = json.dumps([
    {'propertyName': 'client_id', 'propertyType': 'string',
     'description': "Client ID (e.g. 'cli-001')."},
    {'propertyName': 'response_format', 'propertyType': 'string',
     'description': _RESPONSE_FORMAT_DESC},
])

_analyze_drift_props = json.dumps([
    {'propertyName': 'client_id', 'propertyType': 'string',
     'description': "Client ID."},
    {'propertyName': 'threshold_pp', 'propertyType': 'number',
     'description': 'Minimum |drift_pp| to include in the response. Default 3.0.'},
    {'propertyName': 'response_format', 'propertyType': 'string',
     'description': _RESPONSE_FORMAT_DESC},
])

_find_research_props = json.dumps([
    {'propertyName': 'client_id', 'propertyType': 'string',
     'description': "Optional client ID. When supplied, expands to that client's holdings (matches research with isin in their portfolio, plus tag-overlap commentary)."},
    {'propertyName': 'query', 'propertyType': 'string',
     'description': 'Optional free-text query matched against title, tags, and content.'},
    {'propertyName': 'isin', 'propertyType': 'string',
     'description': "Optional instrument ISIN to filter on (e.g. 'XX0000000005')."},
    {'propertyName': 'max_results', 'propertyType': 'number',
     'description': 'Cap on returned results. Default 5; response sets truncated=true if more matched.'},
    {'propertyName': 'response_format', 'propertyType': 'string',
     'description': _RESPONSE_FORMAT_DESC},
])

_summarize_activity_props = json.dumps([
    {'propertyName': 'client_id', 'propertyType': 'string',
     'description': "Client ID."},
    {'propertyName': 'days', 'propertyType': 'number',
     'description': 'Lookback window in days. Default 30. Common: 30, 90, 365.'},
    {'propertyName': 'response_format', 'propertyType': 'string',
     'description': _RESPONSE_FORMAT_DESC},
])

_run_query_props = json.dumps([
    {'propertyName': 'collection', 'propertyType': 'string',
     'description': "One of: 'clients', 'ips', 'portfolios', 'transactions', 'crm_events', 'instruments', 'market_data', 'research', 'market_commentary', 'regulatory'."},
    {'propertyName': 'filter_field', 'propertyType': 'string',
     'description': 'Optional field name to exact-match filter on (e.g. client_id).'},
    {'propertyName': 'filter_value', 'propertyType': 'string',
     'description': 'Value to match against filter_field.'},
    {'propertyName': 'doc_id', 'propertyType': 'string',
     'description': "When collection is 'research'/'market_commentary'/'regulatory': fetch full document content for this ID."},
    {'propertyName': 'page', 'propertyType': 'number',
     'description': '1-indexed page number for pagination. Default 1.'},
    {'propertyName': 'page_size', 'propertyType': 'number',
     'description': 'Records per page. Default 20.'},
])


def _args(context) -> dict:
    return json.loads(context).get('arguments', {}) or {}


# ── Intent tool 1: prepare_client_briefing (the headline) ─────────────────────
@app.generic_trigger(
    arg_name='context',
    type='mcpToolTrigger',
    toolName='cpb_prepare_client_briefing',
    description=(
        "Prepare a fully-stitched briefing for a private-banking RM ahead of a "
        "client meeting. Returns one structured response covering: portfolio "
        "summary (allocation, top holdings, ESG composite), drift vs IPS "
        "(asset class, regional, concentration, ESG floor), recent transactions "
        "(30d), CRM flags (90d), relevant research and commentary touching the "
        "client's holdings, and heuristic next-best-actions. This is the primary "
        "intent — prefer it over composing cpb_get_client_context + "
        "cpb_analyze_portfolio_drift + cpb_find_relevant_research yourself."
    ),
    toolProperties=_prepare_briefing_props,
)
def prepare_client_briefing(context) -> str:
    a = _args(context)
    return kb.cpb_prepare_client_briefing(
        client_id=a.get('client_id', ''),
        meeting_purpose=a.get('meeting_purpose', 'quarterly_review'),
        response_format=a.get('response_format', 'concise'),
    )


# ── Intent tool 2: get_client_context (lighter weight) ────────────────────────
@app.generic_trigger(
    arg_name='context',
    type='mcpToolTrigger',
    toolName='cpb_get_client_context',
    description=(
        "Get identity, segment, RM, base currency, IPS targets, and exclusions for "
        "one client — without the briefing's portfolio synthesis. Use when you only "
        "need the basics (e.g. to look up the client's RM email or base currency)."
    ),
    toolProperties=_get_client_context_props,
)
def get_client_context(context) -> str:
    a = _args(context)
    return kb.cpb_get_client_context(
        client_id=a.get('client_id', ''),
        response_format=a.get('response_format', 'concise'),
    )


# ── Intent tool 3: analyze_portfolio_drift ────────────────────────────────────
@app.generic_trigger(
    arg_name='context',
    type='mcpToolTrigger',
    toolName='cpb_analyze_portfolio_drift',
    description=(
        "Drift-only deep dive for one client. Returns asset-class drift, regional "
        "drift, concentration flags, and ESG floor breach. Filters drift rows to "
        "|drift_pp| >= threshold_pp. Use this when the user explicitly asks about "
        "drift or rebalancing; otherwise prefer cpb_prepare_client_briefing for "
        "context around the drift."
    ),
    toolProperties=_analyze_drift_props,
)
def analyze_portfolio_drift(context) -> str:
    a = _args(context)
    threshold = a.get('threshold_pp')
    return kb.cpb_analyze_portfolio_drift(
        client_id=a.get('client_id', ''),
        threshold_pp=float(threshold) if threshold is not None else 3.0,
        response_format=a.get('response_format', 'concise'),
    )


# ── Intent tool 4: find_relevant_research ─────────────────────────────────────
@app.generic_trigger(
    arg_name='context',
    type='mcpToolTrigger',
    toolName='cpb_find_relevant_research',
    description=(
        "Search Contoso research notes, market commentary, and regulatory memos. "
        "Filters combine (intersection): client_id expands to the client's holdings, "
        "isin pins to one instrument, query is free-text against title/tags/content. "
        "Returns excerpts; use cpb_run_query(collection='research', doc_id=...) for "
        "full document content. At least one filter is required."
    ),
    toolProperties=_find_research_props,
)
def find_relevant_research(context) -> str:
    a = _args(context)
    max_results = a.get('max_results')
    return kb.cpb_find_relevant_research(
        client_id=a.get('client_id') or None,
        query=a.get('query') or None,
        isin=a.get('isin') or None,
        max_results=int(max_results) if max_results is not None else 5,
        response_format=a.get('response_format', 'concise'),
    )


# ── Intent tool 5: summarize_recent_activity ──────────────────────────────────
@app.generic_trigger(
    arg_name='context',
    type='mcpToolTrigger',
    toolName='cpb_summarize_recent_activity',
    description=(
        "Group transactions for one client over a lookback window by intent "
        "(thematic_top_up, ldi_duration_extension, income_distribution, etc.) and "
        "return per-intent gross + net flows in CHF, plus the underlying transaction "
        "list. Use this when the user asks 'what's been happening' or wants to "
        "explain recent moves before the briefing."
    ),
    toolProperties=_summarize_activity_props,
)
def summarize_recent_activity(context) -> str:
    a = _args(context)
    days = a.get('days')
    return kb.cpb_summarize_recent_activity(
        client_id=a.get('client_id', ''),
        days=int(days) if days is not None else 30,
        response_format=a.get('response_format', 'concise'),
    )


# ── Intent tool 6: run_query (escape hatch — read-only) ───────────────────────
@app.generic_trigger(
    arg_name='context',
    type='mcpToolTrigger',
    toolName='cpb_run_query',
    description=(
        "Read-only escape hatch for unusual workflows the intent tools don't cover. "
        "Prefer the intent tools when they fit. Modes: list a registry collection "
        "(clients/ips/portfolios/transactions/crm_events/instruments/market_data); "
        "list a document index (research/market_commentary/regulatory); fetch a "
        "specific document via doc_id. Optional exact-match filter via filter_field+"
        "filter_value. Pagination via page+page_size."
    ),
    toolProperties=_run_query_props,
)
def run_query(context) -> str:
    a = _args(context)
    page = a.get('page')
    page_size = a.get('page_size')
    return kb.cpb_run_query(
        collection=a.get('collection') or None,
        filter_field=a.get('filter_field') or None,
        filter_value=a.get('filter_value'),
        doc_id=a.get('doc_id') or None,
        page=int(page) if page is not None else 1,
        page_size=int(page_size) if page_size is not None else 20,
    )
