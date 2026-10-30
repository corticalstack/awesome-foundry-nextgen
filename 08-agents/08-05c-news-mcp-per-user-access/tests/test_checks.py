"""Unit tests for news_mcp_checks.py: the agent base URL, the response classifier, the
JSON-RPC parsing behind the direct tools/list check, and the test matrix. No network calls.
"""

import importlib.util
import json
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    'news_mcp_checks_mod', Path(__file__).parents[1] / 'news_mcp_checks.py')
checks = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(checks)

USER_A_ROLES = ['News.Read.All']
USER_B_ROLES = ['News.Read.Sports', 'News.Read.Science', 'News.Read.Health']
DENIAL_B = 'Your access covers: sports, science, health. Do not retry other categories.'
ARTICLES = json.dumps({'totalArticles': 2, 'articles': [{'title': 'Final tonight'}, {'title': 'Transfer news'}]})


# ── Fixtures shaped like a Responses API response (response.model_dump()) ────


def _response(*items):
    return {'id': 'resp_1', 'object': 'response', 'output': list(items)}


def _list_tools(*names):
    return {'type': 'mcp_list_tools', 'server_label': 'news_mcp_wrapper',
            'tools': [{'name': n, 'input_schema': {}} for n in names]}


def _call(name, args, output=None, error=None):
    return {'type': 'mcp_call', 'server_label': 'news_mcp_wrapper', 'name': name,
            'arguments': json.dumps(args), 'output': output, 'error': error}


def _message(text):
    return {'type': 'message', 'role': 'assistant', 'content': [{'type': 'output_text', 'text': text}]}


# ── Base URL ─────────────────────────────────────────────────────────────────


def test_openai_base_url():
    endpoint = 'https://aif-core-abc123.services.ai.azure.com/api/projects/project-admin-abc123'
    assert checks.openai_base_url(endpoint, 'news-desk-agent') == (
        f'{endpoint}/agents/news-desk-agent/endpoint/protocols/openai')


def test_agent_client_sends_the_api_version():
    """Without api-version the agent endpoint answers 400 'Missing required query parameter'."""
    endpoint = 'https://aif-core-abc123.services.ai.azure.com/api/projects/project-admin-abc123'
    client = checks.agent_client(object(), endpoint, 'news-desk-agent', 'blueprint-client-id')
    assert str(client.base_url) == f'{endpoint}/agents/news-desk-agent/endpoint/protocols/openai/'
    assert client.default_query == {'api-version': 'v1'}


# ── Classifier ───────────────────────────────────────────────────────────────


def test_denial_in_call_output_is_denied():
    r = _response(_list_tools('get_sports_headlines'), _call('get_business_headlines', {'max': 3}, output=DENIAL_B),
                  _message(DENIAL_B))
    assert checks.classify(r, USER_B_ROLES) == 'denied'


def test_denial_in_call_error_is_denied():
    r = _response(_call('get_business_headlines', {'max': 3}, error=f'Tool call failed: {DENIAL_B}'), _message('Sorry.'))
    assert checks.classify(r, USER_B_ROLES) == 'denied'


def test_call_with_articles():
    r = _response(_call('get_sports_headlines', {'max': 3}, output=ARTICLES), _message('1. Final tonight'))
    assert checks.classify(r, USER_B_ROLES) == 'articles'


def test_no_tool_call_and_plain_text_is_unknown():
    assert checks.classify(_response(_message('I can fetch news headlines.')), USER_B_ROLES) == 'unknown'


def test_denial_in_text_without_a_tool_item_is_denied():
    assert checks.classify(_response(_message(f'The news server said: {DENIAL_B}')), USER_B_ROLES) == 'denied'


def test_failed_call_without_the_denial_is_unknown():
    r = _response(_call('get_sports_headlines', {'max': 3}, error='upstream timeout'), _message('Sorry.'))
    assert checks.classify(r, USER_B_ROLES) == 'unknown'


def test_listed_tools_in_order():
    r = _response(_list_tools('get_sports_headlines', 'get_science_headlines', 'get_health_headlines'))
    assert checks.listed_tools(r) == ['get_sports_headlines', 'get_science_headlines', 'get_health_headlines']


def test_called_tools_with_arguments():
    r = _response(_call('get_sports_headlines', {'max': 3}, output=ARTICLES),
                  _call('top_headlines', {'category': 'sports', 'max': 3}, output=ARTICLES))
    assert checks.called_tools(r) == [
        ('get_sports_headlines', {'max': 3}), ('top_headlines', {'category': 'sports', 'max': 3})]


# ── JSON-RPC bodies from an MCP server ───────────────────────────────────────

RESULT = {'tools': [{'name': 'get_sports_headlines'}, {'name': 'get_science_headlines'}]}
MESSAGE = json.dumps({'jsonrpc': '2.0', 'id': 1, 'result': RESULT})


def test_parse_plain_json_body():
    assert checks.parse_jsonrpc(MESSAGE) == RESULT


def test_parse_sse_body():
    assert checks.parse_jsonrpc(f'event: message\ndata: {MESSAGE}\n\n') == RESULT


def test_parse_jsonrpc_error_raises():
    body = json.dumps({'jsonrpc': '2.0', 'id': 1, 'error': {'code': -32601, 'message': 'Method not found'}})
    with pytest.raises(RuntimeError, match='Method not found'):
        checks.parse_jsonrpc(body)


def test_tool_names():
    assert checks.tool_names(RESULT) == ['get_sports_headlines', 'get_science_headlines']


# ── Matrix ───────────────────────────────────────────────────────────────────


def test_base_cases():
    assert [(c.user, c.category, c.expected, c.required) for c in checks.BASE_CASES] == [
        ('A', 'business', 'articles', True),
        ('B', 'business', 'denied', True),
        ('B', 'sports', 'articles', True),
    ]


def test_science_case_takes_the_expectation_from_the_caller():
    assert checks.science_case('articles') == checks.Case('B', 'science', 'articles', True)
    assert checks.science_case('denied', required=False) == checks.Case('B', 'science', 'denied', False)


@pytest.mark.parametrize('category', ['business', 'sports', 'science'])
def test_prompt_names_the_category(category):
    assert checks.prompt(category) == f'Give me three {category} headlines'


def test_gnews_budget_per_full_run_stays_below_20():
    article_cases = sum(c.expected == 'articles' for c in checks.BASE_CASES)
    assert 2 * article_cases <= checks.gnews_budget() < 20


class _FakeResponse:
    def __init__(self, data):
        self._data = data

    def model_dump(self):
        return self._data


class _FakeClient:
    """Answers each prompt from a {category: response dict} map."""

    def __init__(self, answers):
        self.answers = answers
        self.responses = self

    def create(self, input, extra_body=None):
        return _FakeResponse(self.answers[input.split()[3]])


A_CLIENT = _FakeClient({'business': _response(_call('get_business_headlines', {}, output=ARTICLES))})
B_CLIENT = _FakeClient({
    'business': _response(_call('get_business_headlines', {}, output=DENIAL_B)),
    'sports': _response(_call('get_sports_headlines', {}, output=ARTICLES)),
    'science': _response(_call('get_science_headlines', {}, output=ARTICLES)),
})
ROLES = {'A': USER_A_ROLES, 'B': USER_B_ROLES}


def test_run_matrix_records_each_case():
    records = checks.run_matrix({'A': A_CLIENT, 'B': B_CLIENT}, checks.BASE_CASES, ROLES)
    assert [(r['user'], r['category'], r['outcome'], r['passed']) for r in records] == [
        ('A', 'business', 'articles', True), ('B', 'business', 'denied', True), ('B', 'sports', 'articles', True)]


def test_run_matrix_raises_on_a_required_failure():
    with pytest.raises(AssertionError, match='science'):
        checks.run_matrix({'B': B_CLIENT}, [checks.science_case('denied')], ROLES)


def test_run_matrix_reports_but_does_not_raise_when_not_required():
    records = checks.run_matrix({'B': B_CLIENT}, [checks.science_case('denied', required=False)], ROLES)
    assert records[0]['outcome'] == 'articles'
    assert records[0]['passed'] is False
