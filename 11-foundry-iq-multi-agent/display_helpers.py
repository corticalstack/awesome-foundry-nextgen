"""
Display helpers for Foundry IQ Multi-Agent

Provides:
  - show_success / show_error       - status feedback (shared pattern)
  - show_kb_result_detail           - KB retrieval response display (Phase 3)
  - show_routing_decision           - routing visualization (Phase 5/6)
  - show_agent_response             - agent response with citations (Phase 5/6)
  - show_multi_domain_summary       - side-by-side domain comparison (Phase 6)
"""
from IPython.display import display, Markdown, HTML

# ── Domain colour palette ─────────────────────────────────────────────────────
_DOMAIN_COLOURS = {
    'hr':        {'bg': '#0e4a4a', 'accent': '#00b4d8', 'label': 'HR'},
    'marketing': {'bg': '#4a2800', 'accent': '#ff6b35', 'label': 'Marketing'},
    'products':  {'bg': '#2d004a', 'accent': '#9c5de8', 'label': 'Products'},
}
_DEFAULT_COLOUR = {'bg': '#1e3a5f', 'accent': '#0078d4', 'label': 'Agent'}


def _domain_colours(agent_name: str) -> dict:
    """Return colour dict for a given agent name (matches on domain keyword)."""
    name_lower = agent_name.lower()
    for key, colours in _DOMAIN_COLOURS.items():
        if key in name_lower:
            return colours
    return _DEFAULT_COLOUR


# ── Status helpers ────────────────────────────────────────────────────────────

def show_success(message: str):
    """Display a success message."""
    display(Markdown(f'### ✅ {message}'))


def show_error(message: str):
    """Display an error message."""
    display(Markdown(f'### ❌ Error\n```\n{message}\n```'))


# ── KB validation display ─────────────────────────────────────────────────────

def show_kb_result_detail(result: dict, label: str = ''):
    """Display a KB retrieval result (answerSynthesis mode).

    For answerSynthesis KBs the response text is a natural-language answer.
    References are displayed as a compact list of document titles.
    """
    if label:
        display(Markdown(f'**{label}**'))

    if 'error' in result:
        show_error(result['error'])
        return

    responses = result.get('response', [])
    for resp in responses:
        for item in resp.get('content', []):
            text = item.get('text', '')
            if text:
                display(Markdown(text))

    refs = result.get('references', [])
    if refs:
        titles = [r.get('title') or r.get('id', f'ref_{i}') for i, r in enumerate(refs)]
        ref_lines = '\n'.join(f'- {t}' for t in titles)
        display(Markdown(f'**Sources:**\n{ref_lines}'))


# ── Routing visualization ─────────────────────────────────────────────────────

def show_routing_decision(query: str, agent_name: str):
    """Render an HTML card showing the query and which specialist was selected.

    Colour-coded by domain: HR = teal, Marketing = orange, Products = purple.
    """
    colours = _domain_colours(agent_name)
    html = (
        f'<div style="margin:8px 0;padding:12px 16px;border-radius:6px;'
        f'background:{colours["bg"]};border-left:4px solid {colours["accent"]};">'
        f'<div style="color:#c8d8e8;font-size:0.85em;margin-bottom:4px;">Query</div>'
        f'<div style="color:#ffffff;font-size:1em;margin-bottom:8px;">{query}</div>'
        f'<div style="color:{colours["accent"]};font-weight:600;font-size:0.9em;">'
        f'&#8594;&nbsp;&nbsp;{agent_name}&nbsp;&nbsp;'
        f'<span style="background:{colours["accent"]};color:#000;'
        f'border-radius:3px;padding:1px 6px;font-size:0.8em;">'
        f'{colours["label"]}</span>'
        f'</div>'
        f'</div>'
    )
    display(HTML(html))


# ── Agent response display ────────────────────────────────────────────────────

def show_agent_response(query: str, response_text: str, agent_name: str):
    """Render an agent response with a domain-coloured header and inline citations.

    Citations are extracted from the pattern: (Document Title) in the text.
    """
    import re

    colours = _domain_colours(agent_name)

    if not response_text:
        display(HTML(
            f'<div style="padding:10px;color:#888;font-style:italic;">'
            f'No response from {agent_name}.</div>'
        ))
        return

    # Header
    display(HTML(
        f'<div style="margin:4px 0 8px 0;padding:8px 14px;border-radius:4px;'
        f'background:{colours["bg"]};color:{colours["accent"]};font-weight:600;">'
        f'{agent_name}</div>'
    ))

    # Response body
    display(Markdown(response_text))

    # Extract citation titles from (Title) pattern and render as cards
    citations = re.findall(r'\(([^()]{5,80})\)', response_text)
    unique_citations = list(dict.fromkeys(citations))  # preserve order, dedupe
    if unique_citations:
        cards = ''.join(
            f'<div style="margin:4px 0;padding:6px 12px;'
            f'border-left:3px solid {colours["accent"]};'
            f'background:{colours["bg"]};border-radius:0 3px 3px 0;'
            f'color:#c8d8e8;font-size:0.85em;">{c}</div>'
            for c in unique_citations
        )
        display(HTML(f'<div style="margin-top:8px;"><b style="color:#aaa;">Cited:</b>{cards}</div>'))


# ── Multi-domain summary ──────────────────────────────────────────────────────

def show_multi_domain_summary(results_list: list):
    """Render a side-by-side summary of responses across domains.

    Args:
        results_list: list of (domain, response_text) tuples,
                      e.g. [('hr', 'HR answer...'), ('marketing', 'Mkt answer...')]
    """
    if not results_list:
        display(Markdown('*No results to display.*'))
        return

    cols = []
    for domain, text in results_list:
        colours = _DOMAIN_COLOURS.get(domain, _DEFAULT_COLOUR)
        snippet = (text or '*No response*')[:400]
        if len(text or '') > 400:
            snippet += '...'
        cols.append(
            f'<div style="flex:1;min-width:220px;padding:12px;margin:4px;'
            f'background:{colours["bg"]};border-radius:6px;'
            f'border-top:3px solid {colours["accent"]};">'
            f'<div style="color:{colours["accent"]};font-weight:600;'
            f'font-size:0.9em;margin-bottom:8px;">{colours["label"]}</div>'
            f'<div style="color:#d8e8f0;font-size:0.87em;line-height:1.5;">{snippet}</div>'
            f'</div>'
        )

    display(HTML(
        '<div style="display:flex;flex-wrap:wrap;gap:8px;margin:8px 0;">'
        + ''.join(cols)
        + '</div>'
    ))
