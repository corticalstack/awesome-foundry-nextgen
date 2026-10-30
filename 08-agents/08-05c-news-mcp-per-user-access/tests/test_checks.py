"""Unit tests for news_mcp_checks.py: the agent base URL, the response classifier, the
JSON-RPC parsing behind the direct tools/list and tools/call checks, and the test matrix.
No network calls.
"""

import importlib.util
import json
from pathlib import Path

import httpx
import openai
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


def test_jwt_claims():
    import base64
    payload = base64.urlsafe_b64encode(json.dumps({'oid': 'oid-b', 'scp': 'access_agent'}).encode()).decode().rstrip('=')
    assert checks.jwt_claims(f'header.{payload}.signature') == {'oid': 'oid-b', 'scp': 'access_agent'}


# ── Classifier ───────────────────────────────────────────────────────────────


def test_denial_in_call_output_is_denied():
    r = _response(_list_tools('get_sports_headlines'), _call('get_business_headlines', {'max': 3}, output=DENIAL_B),
                  _message(DENIAL_B))
    assert checks.classify(r, USER_B_ROLES, 'business') == 'denied'


def test_denial_in_call_error_is_denied():
    r = _response(_call('get_business_headlines', {'max': 3}, error=f'Tool call failed: {DENIAL_B}'), _message('Sorry.'))
    assert checks.classify(r, USER_B_ROLES, 'business') == 'denied'


def test_call_with_articles():
    r = _response(_call('get_sports_headlines', {'max': 3}, output=ARTICLES), _message('1. Final tonight'))
    assert checks.classify(r, USER_B_ROLES, 'sports') == 'articles'


def test_no_tool_call_and_plain_text_is_unknown():
    assert checks.classify(_response(_message('I can fetch news headlines.')), USER_B_ROLES, 'sports') == 'unknown'


def test_denial_in_text_without_a_tool_item_is_denied():
    assert checks.classify(_response(_message(f'The news server said: {DENIAL_B}')), USER_B_ROLES, 'business') == 'denied'


def test_failed_call_without_the_denial_is_unknown():
    r = _response(_call('get_sports_headlines', {'max': 3}, error='upstream timeout'), _message('Sorry.'))
    assert checks.classify(r, USER_B_ROLES, 'sports') == 'unknown'


def test_tool_left_out_of_the_list_and_no_call_is_hidden():
    """Track A: the wrapper lists only user B's tools, so the agent has nothing to call for business."""
    r = _response(_list_tools('get_sports_headlines', 'get_science_headlines', 'get_health_headlines'),
                  _message('I cannot fetch business headlines with the available news tools.'))
    assert checks.classify(r, USER_B_ROLES, 'business') == 'hidden'


def test_no_tools_listed_at_all_is_hidden():
    r = _response(_list_tools(), _message('I have no news tools.'))
    assert checks.classify(r, [], 'business') == 'hidden'


def test_articles_from_another_category_only_is_substituted():
    """Seen live: asked for business, the agent fetched science headlines instead."""
    r = _response(_list_tools('get_sports_headlines', 'get_science_headlines', 'get_health_headlines'),
                  _call('get_science_headlines', {'max': 3}, output=ARTICLES), _message('Here are science headlines.'))
    assert checks.classify(r, USER_B_ROLES, 'business') == 'substituted'


def test_top_headlines_for_the_category_is_articles():
    """Track B: GNews's own tool takes the category as an argument."""
    r = _response(_list_tools('top_headlines', 'search'), _call('top_headlines', {'category': 'business'}, output=ARTICLES))
    assert checks.classify(r, USER_A_ROLES, 'business') == 'articles'


def test_top_headlines_for_another_category_is_substituted():
    r = _response(_list_tools('top_headlines', 'search'), _call('top_headlines', {'category': 'sports'}, output=ARTICLES))
    assert checks.classify(r, USER_B_ROLES, 'business') == 'substituted'


@pytest.mark.parametrize('tool', ['search_news', 'search'])
def test_search_answers_any_category(tool):
    r = _response(_call(tool, {'q': 'business'}, output=ARTICLES))
    assert checks.classify(r, USER_A_ROLES, 'business') == 'articles'


def test_rejected_call_to_the_category_tool_is_hidden():
    """Foundry refused a call to a tool the server did not list (see checks.ask)."""
    assert checks.classify({'output': [], 'rejected_tool': 'get_business_headlines'}, USER_B_ROLES, 'business') == 'hidden'


def test_failed_call_with_the_denial_is_denied():
    """Foundry failed the request because the tool returned isError (see checks.ask)."""
    response = {'output': [], 'failed_call': {'name': 'top_headlines', 'error': DENIAL_B}}
    assert checks.classify(response, USER_B_ROLES, 'business') == 'denied'
    assert checks.called_tools(response) == [('top_headlines', {})]


def test_reply_is_the_agent_text():
    assert checks.reply(_response(_message('1. Final tonight'))) == '1. Final tonight'


def test_reply_shows_the_error_for_a_failed_call():
    response = {'output': [], 'failed_call': {'name': 'top_headlines', 'error': DENIAL_B}}
    assert checks.reply(response) == f"HTTP 400 from the agent endpoint: an error occurred invoking 'top_headlines': {DENIAL_B}"


def test_reply_shows_the_error_for_a_rejected_tool():
    response = {'output': [], 'rejected_tool': 'get_business_headlines'}
    assert checks.reply(response) == 'HTTP 400 from the agent endpoint: tool get_business_headlines is not on the MCP server'


def test_rejected_call_to_another_tool_is_unknown():
    assert checks.classify({'output': [], 'rejected_tool': 'get_world_headlines'}, USER_B_ROLES, 'business') == 'unknown'


def test_unfiltered_list_without_a_call_is_unknown():
    """Track B lists top_headlines to everyone, so a reply without a call is not 'hidden'."""
    r = _response(_list_tools('top_headlines', 'search'), _message('I cannot help with that.'))
    assert checks.classify(r, USER_B_ROLES, 'business') == 'unknown'


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


def test_call_tool_direct(monkeypatch):
    result = {'content': [{'type': 'text', 'text': DENIAL_B}], 'isError': True}
    sent = {}

    class _Reply:
        text = f"event: message\ndata: {json.dumps({'jsonrpc': '2.0', 'id': 1, 'result': result})}\n\n"

        def raise_for_status(self):
            pass

    def fake_post(url, json, headers, timeout):
        sent.update(url=url, body=json, headers=headers)
        return _Reply()

    monkeypatch.setattr(checks.requests, 'post', fake_post)
    assert checks.call_tool_direct('https://ca.example/mcp', 'tok', 'get_business_headlines', {'max': 3}) == result
    assert sent['body'] == {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                            'params': {'name': 'get_business_headlines', 'arguments': {'max': 3}}}
    assert sent['headers']['Authorization'] == 'Bearer tok'
    assert sent['headers']['Accept'] == 'application/json, text/event-stream'


# ── Wrapper logs from Container Apps ─────────────────────────────────────────

DENIED = {'event': 'tools/call', 'idtyp': 'user', 'oid': 'oid-b', 'azp': 'agent-app', 'roles': USER_B_ROLES,
          'scp': 'News.Read', 'aud': 'resource-app', 'tool': 'get_business_headlines', 'decision': 'denied',
          'mcp_protocol_version': '2025-06-18'}
APP_CALL = {'event': 'tools/call', 'idtyp': 'app', 'oid': 'oid-agent', 'appid': 'agent-app',
            'roles': ['News.Read.Sports'], 'tool': 'get_sports_headlines', 'decision': 'allowed'}
SESSION = {'event': 'initialize', 'requested': '2025-06-18', 'negotiated': '2025-06-18', 'client': 'foundry'}


def test_wrapper_events_from_console_lines():
    lines = [
        json.dumps(SESSION),                                                     # the event itself
        json.dumps({'TimeStamp': '2026-10-30T17:00:00Z', 'Log': json.dumps(DENIED)}),  # az containerapp logs show
        json.dumps({'TimeGenerated': '2026-10-30T17:00:01Z', 'Log_s': f'F {json.dumps(APP_CALL)}'}),  # Log Analytics
        'INFO:     100.100.0.1:5000 - "POST /mcp HTTP/1.1" 200 OK',              # uvicorn access log
        json.dumps({'TimeStamp': '2026-10-30T17:00:02Z', 'Log': 'Connecting to stream...'}),
    ]
    assert checks.wrapper_events(lines) == [SESSION, DENIED, APP_CALL]


def test_wrapper_events_filter_by_kind():
    lines = [json.dumps(SESSION), json.dumps(DENIED), json.dumps(APP_CALL)]
    assert checks.wrapper_events(lines, 'tools/call') == [DENIED, APP_CALL]


# ── Matrix ───────────────────────────────────────────────────────────────────


@pytest.mark.parametrize('track, b_business', [('wrapper', 'hidden'), ('apim', 'denied')])
def test_base_cases(track, b_business):
    assert [(c.user, c.category, c.expected, c.required) for c in checks.base_cases(track)] == [
        ('A', 'business', 'articles', True),
        ('B', 'business', b_business, True),
        ('B', 'sports', 'articles', True),
    ]


def test_science_case_takes_the_expectation_from_the_caller():
    assert checks.science_case('articles') == checks.Case('B', 'science', 'articles', True)
    assert checks.science_case('denied', required=False) == checks.Case('B', 'science', 'denied', False)


@pytest.mark.parametrize('category', ['business', 'sports', 'science'])
def test_prompt_names_the_category(category):
    assert checks.prompt(category) == f'Give me three {category} headlines'


def test_gnews_budget_per_full_run_stays_below_20():
    article_cases = sum(c.expected == 'articles' for track in ('wrapper', 'apim') for c in checks.base_cases(track))
    assert article_cases <= checks.gnews_budget() < 20


class _FakeResponse:
    def __init__(self, data):
        self._data = data

    def model_dump(self, warnings=True):
        assert warnings is False  # Foundry's MCP items make the SDK warn on every dump
        return self._data


class _FakeClient:
    """Answers each prompt from a {category: response dict or exception} map."""

    def __init__(self, answers):
        self.answers = answers
        self.responses = self

    def create(self, input, extra_body=None):
        answer = self.answers[input.split()[3]]
        if isinstance(answer, Exception):
            raise answer
        return _FakeResponse(answer)


def _bad_request(message):
    return openai.BadRequestError(f'Error code: 400 - {message}', body={'message': message},
                                  response=httpx.Response(400, request=httpx.Request('POST', 'https://agent.example')))


NOT_LISTED = _bad_request("Tool get_business_headlines not found on remote server: https://ca.example:443/mcp.")


def test_ask_returns_the_response():
    response = _response(_call('get_sports_headlines', {}, output=ARTICLES))
    assert checks.ask(_FakeClient({'sports': response}), checks.prompt('sports')) == response


def test_ask_turns_a_call_to_an_unlisted_tool_into_a_response():
    """Seen live: the model guessed get_business_headlines from get_sports_headlines, and Foundry
    answered HTTP 400 before anything reached the wrapper."""
    assert checks.ask(_FakeClient({'business': NOT_LISTED}), checks.prompt('business')) == {
        'output': [], 'rejected_tool': 'get_business_headlines'}


def test_ask_turns_a_failed_tool_call_into_a_response():
    """Seen live on Track B: a tool result with isError true fails the whole request with HTTP 400,
    and the message carries the tool's text."""
    error = _bad_request(f"An error occurred invoking 'top_headlines': {DENIAL_B} Troubleshooting guide: "
                         "https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/model-context-protocol")
    assert checks.ask(_FakeClient({'business': error}), checks.prompt('business')) == {
        'output': [], 'failed_call': {'name': 'top_headlines', 'error': DENIAL_B}}


def test_ask_raises_other_bad_requests():
    with pytest.raises(openai.BadRequestError):
        checks.ask(_FakeClient({'business': _bad_request('Invalid model')}), checks.prompt('business'))


A_CLIENT = _FakeClient({'business': _response(_call('get_business_headlines', {}, output=ARTICLES))})
B_CLIENT = _FakeClient({
    'business': _response(_call('get_business_headlines', {}, output=DENIAL_B)),
    'sports': _response(_call('get_sports_headlines', {}, output=ARTICLES)),
    'science': _response(_call('get_science_headlines', {}, output=ARTICLES)),
})
B_WRAPPER_CLIENT = _FakeClient({
    'business': _response(_list_tools('get_sports_headlines', 'get_science_headlines', 'get_health_headlines'),
                          _message('I cannot fetch business headlines.')),
    'sports': _response(_call('get_sports_headlines', {}, output=ARTICLES)),
})
ROLES = {'A': USER_A_ROLES, 'B': USER_B_ROLES}


def test_run_matrix_records_each_case():
    records = checks.run_matrix({'A': A_CLIENT, 'B': B_CLIENT}, checks.base_cases('apim'), ROLES)
    assert [(r['user'], r['category'], r['outcome'], r['passed']) for r in records] == [
        ('A', 'business', 'articles', True), ('B', 'business', 'denied', True), ('B', 'sports', 'articles', True)]


def test_run_matrix_on_the_wrapper_expects_the_business_tool_hidden():
    records = checks.run_matrix({'A': A_CLIENT, 'B': B_WRAPPER_CLIENT}, checks.base_cases('wrapper'), ROLES)
    assert [(r['user'], r['category'], r['outcome'], r['passed']) for r in records] == [
        ('A', 'business', 'articles', True), ('B', 'business', 'hidden', True), ('B', 'sports', 'articles', True)]


def test_run_matrix_records_a_rejected_unlisted_tool_as_hidden():
    client = _FakeClient({'business': NOT_LISTED})
    records = checks.run_matrix({'B': client}, [checks.Case('B', 'business', 'hidden')], ROLES)
    assert (records[0]['outcome'], records[0]['listed'], records[0]['called'], records[0]['passed']) == ('hidden', [], [], True)


def test_run_matrix_records_a_failed_denied_call_as_denied():
    error = _bad_request(f"An error occurred invoking 'top_headlines': {DENIAL_B} Troubleshooting guide: https://learn.example")
    records = checks.run_matrix({'B': _FakeClient({'business': error})}, [checks.Case('B', 'business', 'denied')], ROLES)
    assert (records[0]['outcome'], records[0]['called'], records[0]['passed']) == ('denied', [('top_headlines', {})], True)


def test_run_matrix_raises_on_a_required_failure():
    with pytest.raises(AssertionError, match='science'):
        checks.run_matrix({'B': B_CLIENT}, [checks.science_case('denied')], ROLES)


def test_run_matrix_reports_but_does_not_raise_when_not_required():
    records = checks.run_matrix({'B': B_CLIENT}, [checks.science_case('denied', required=False)], ROLES)
    assert records[0]['outcome'] == 'articles'
    assert records[0]['passed'] is False
