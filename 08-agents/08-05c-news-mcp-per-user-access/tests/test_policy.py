"""String-level checks of infra/news-mcp-policy.xml, the Track B inbound policy. APIM evaluates
its C# expressions; these tests pin what must stay in step with authz.py: the category order,
the role names and the denial text, plus the token swap and the body handling.
"""

import importlib.util
import os
import re
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    'news_mcp_authz_policy', Path(__file__).parents[1] / 'news-mcp-wrapper' / 'authz.py')
authz = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(authz)

POLICY_FILE = Path(__file__).parents[1] / 'infra' / 'news-mcp-policy.xml'


@pytest.fixture(scope='module')
def policy():
    return POLICY_FILE.read_text()


def test_validates_the_entra_token_into_a_variable(policy):
    assert '<validate-azure-ad-token tenant-id="__TENANT_ID__"' in policy
    assert 'output-token-variable-name="jwt"' in policy
    assert '<audiences>__AUDIENCES__</audiences>' in policy  # filled in by apim-news-mcp.bicep


def test_categories_in_authz_order(policy):
    assert ', '.join(f'"{c}"' for c in authz.CATEGORIES) in policy


def test_role_names_follow_authz(policy):
    """The policy builds each role name as News.Read. plus the capitalised category."""
    assert all(authz.role_for(c) == 'News.Read.' + c[0].upper() + c[1:] for c in authz.CATEGORIES)
    assert '"News.Read." + char.ToUpper(c[0]) + c.Substring(1)' in policy
    assert f'"{authz.ALL_ROLE}"' in policy


def test_denial_text_matches_authz(policy):
    before, after = authz.denial_message([authz.role_for('sports')]).split('sports')
    assert f'"{before}" + string.Join(", ", allowed) + "{after}"' in policy
    assert f'"{authz.denial_message([])}"' in policy


def test_checks_top_headlines_by_category_and_search_by_all(policy):
    assert '"tools/call"' in policy
    assert '"top_headlines"' in policy and '"search"' in policy
    assert '?? "general"' in policy  # top_headlines without a category asks for general news


def test_reads_the_body_without_consuming_it(policy):
    assert 'context.Request.Body.As<JObject>(preserveContent: true)' in policy


def test_denial_is_a_jsonrpc_tool_error(policy):
    response = policy[policy.index('<return-response>'):policy.index('</return-response>')]
    assert '<set-status code="200" reason="OK" />' in response
    assert '<value>application/json</value>' in response
    for key in ('"jsonrpc"', '"id"', '"result"', '"content"', '"isError"'):
        assert key in response


def test_swaps_the_user_token_for_the_gnews_key(policy):
    assert '<set-header name="Authorization" exists-action="delete" />' in policy
    assert '<set-header name="X-Api-Key" exists-action="override">' in policy
    assert '<value>{{gnews-api-key}}</value>' in policy


def test_forwards_to_the_gnews_root(policy):
    """APIM appends the client's /mcp to the backend URL; GNews serves MCP only at /."""
    assert '<rewrite-uri template="/" />' in policy


def test_never_reads_the_response_body(policy):
    """Learn: an MCP API policy must not read context.Response.Body; it breaks streaming."""
    assert 'context.Response.Body' not in policy


def test_holds_no_literal_key(policy):
    key = os.environ.get('GNEWS_API_KEY')
    if key:
        assert key not in policy
    assert not re.search(r'\b[0-9a-f]{32}\b', policy)
