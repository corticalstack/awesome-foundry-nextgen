"""Tests for Lab 11 display_helpers module.

Verifies that all display functions accept valid inputs without raising exceptions.
Uses IPython.display mocking to avoid actual notebook output during testing.
"""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# sys.path is configured by conftest.py in this directory


# ─────────────────────────────────────────────────────────────────────────────
# Import test
# ─────────────────────────────────────────────────────────────────────────────

def test_display_helpers_importable():
    from display_helpers import (  # noqa: F401
        show_success,
        show_error,
        show_kb_result_detail,
        show_routing_decision,
        show_agent_response,
        show_multi_domain_summary,
    )


# ─────────────────────────────────────────────────────────────────────────────
# show_routing_decision tests
# ─────────────────────────────────────────────────────────────────────────────

def test_show_routing_decision_no_error():
    """show_routing_decision() completes without raising."""
    from display_helpers import show_routing_decision
    with patch('display_helpers.display'):
        show_routing_decision('What is the remote work policy?', 'contoso-hr-agent')


def test_show_routing_decision_html_contains_query_and_agent():
    """show_routing_decision() HTML output includes both the query text and agent name."""
    from display_helpers import show_routing_decision
    from IPython.display import HTML

    captured = []

    def mock_display(obj):
        captured.append(obj)

    with patch('display_helpers.display', side_effect=mock_display):
        show_routing_decision('What is the remote work policy?', 'contoso-hr-agent')

    assert captured, 'display() was never called'
    html_obj = captured[0]
    assert isinstance(html_obj, HTML)
    assert 'What is the remote work policy?' in html_obj.data
    assert 'contoso-hr-agent' in html_obj.data


def test_show_routing_decision_hr_domain_colour():
    """HR agent produces teal colour in routing card."""
    from display_helpers import show_routing_decision
    from IPython.display import HTML

    captured = []
    with patch('display_helpers.display', side_effect=lambda o: captured.append(o)):
        show_routing_decision('PTO question', 'contoso-hr-agent')

    html = captured[0].data
    assert '#00b4d8' in html or '#0e4a4a' in html, 'HR teal colours not found in output'


def test_show_routing_decision_marketing_domain_colour():
    """Marketing agent produces orange colour."""
    from display_helpers import show_routing_decision
    from IPython.display import HTML

    captured = []
    with patch('display_helpers.display', side_effect=lambda o: captured.append(o)):
        show_routing_decision('Campaign question', 'contoso-marketing-agent')

    html = captured[0].data
    assert '#ff6b35' in html or '#4a2800' in html, 'Marketing orange colours not found in output'


# ─────────────────────────────────────────────────────────────────────────────
# show_agent_response tests
# ─────────────────────────────────────────────────────────────────────────────

def test_show_agent_response_no_error():
    """show_agent_response() completes without raising for a normal response."""
    from display_helpers import show_agent_response
    with patch('display_helpers.display'):
        show_agent_response(
            'What is the remote work policy?',
            'Contoso allows remote work up to 3 days per week (Remote Work Policy).',
            'contoso-hr-agent',
        )


def test_show_agent_response_empty_text_no_error():
    """show_agent_response() handles an empty response text without raising."""
    from display_helpers import show_agent_response
    with patch('display_helpers.display'):
        show_agent_response('Any question', '', 'contoso-hr-agent')


def test_show_agent_response_none_text_no_error():
    """show_agent_response() handles None response text without raising."""
    from display_helpers import show_agent_response
    with patch('display_helpers.display'):
        show_agent_response('Any question', None, 'contoso-hr-agent')


def test_show_agent_response_renders_citation_cards():
    """show_agent_response() calls display multiple times when text has citations."""
    from display_helpers import show_agent_response

    calls = []
    with patch('display_helpers.display', side_effect=lambda o: calls.append(o)):
        show_agent_response(
            'What is the remote work policy?',
            'Contoso allows remote work (Remote Work Policy).',
            'contoso-hr-agent',
        )

    # Should have: header HTML + Markdown body + citations HTML = at least 3 calls
    assert len(calls) >= 3, f'Expected >=3 display calls, got {len(calls)}'


# ─────────────────────────────────────────────────────────────────────────────
# show_multi_domain_summary tests
# ─────────────────────────────────────────────────────────────────────────────

def test_show_multi_domain_summary_no_error():
    """show_multi_domain_summary() renders without error for a standard input."""
    from display_helpers import show_multi_domain_summary
    with patch('display_helpers.display'):
        show_multi_domain_summary([
            ('hr',        'HR policies answer here.'),
            ('marketing', 'Marketing campaign answer here.'),
            ('products',  'Product specs answer here.'),
        ])


def test_show_multi_domain_summary_empty_list():
    """show_multi_domain_summary() handles an empty list gracefully."""
    from display_helpers import show_multi_domain_summary
    with patch('display_helpers.display'):
        show_multi_domain_summary([])


def test_show_multi_domain_summary_long_text_truncated():
    """show_multi_domain_summary() truncates long texts without error."""
    from display_helpers import show_multi_domain_summary
    from IPython.display import HTML

    captured = []
    with patch('display_helpers.display', side_effect=lambda o: captured.append(o)):
        show_multi_domain_summary([('hr', 'x' * 1000)])

    html = captured[0].data
    assert 'x' * 100 in html         # some content present
    assert 'x' * 1000 not in html    # but full text is truncated
    assert '...' in html


def test_show_multi_domain_summary_unknown_domain():
    """show_multi_domain_summary() uses default colour for unknown domains."""
    from display_helpers import show_multi_domain_summary
    with patch('display_helpers.display'):
        show_multi_domain_summary([('unknown_domain', 'Some text here.')])
