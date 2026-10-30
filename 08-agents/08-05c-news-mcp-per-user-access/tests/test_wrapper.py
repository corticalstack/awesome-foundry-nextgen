"""Integration tests for news-mcp-wrapper/server.py, run against a stub GNews MCP server.

The wrapper runs as `python server.py` in a subprocess, as in the image, with static test
tokens in place of Entra. FastMCP is not in the repo environment, so the repo run skips
this file. Run it locally with
    uv run --with "fastmcp>=3.4,<4" pytest 08-agents/08-05c-news-mcp-per-user-access/tests/test_wrapper.py
CI runs it inside the wrapper image. FastMCP is reached through importorskip and
import_module rather than import statements, because scripts/check_imports.py executes
every import statement it finds in tests/.
"""

import asyncio
import importlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

fastmcp = pytest.importorskip('fastmcp')
transports = importlib.import_module('fastmcp.client.transports')
fastmcp_tests = importlib.import_module('fastmcp.utilities.tests')
fastmcp_http = importlib.import_module('fastmcp.utilities.http')

_WRAPPER_DIR = Path(os.environ.get('NEWS_MCP_WRAPPER_DIR', Path(__file__).parents[1] / 'news-mcp-wrapper'))
sys.path.insert(0, str(_WRAPPER_DIR))
authz = importlib.import_module('authz')

USER_B_ROLES = ['News.Read.Sports', 'News.Read.Science', 'News.Read.Health']
USER_B_TOOLS = {'get_sports_headlines', 'get_science_headlines', 'get_health_headlines'}

# Bearer string -> claims. StaticTokenVerifier needs client_id; the rest mirrors Entra tokens.
TOKENS = {
    'user-a': {'client_id': 'agent-app', 'idtyp': 'user', 'oid': 'oid-a', 'azp': 'agent-app',
               'scp': 'News.Read', 'roles': ['News.Read.All']},
    'user-b': {'client_id': 'agent-app', 'idtyp': 'user', 'oid': 'oid-b', 'azp': 'agent-app',
               'scp': 'News.Read', 'roles': USER_B_ROLES},
    'agent-sports': {'client_id': 'sports-agent-app', 'idtyp': 'app', 'oid': 'oid-sports-agent',
                     'appid': 'sports-agent-app', 'roles': ['News.Read.Sports']},
    'no-roles': {'client_id': 'agent-app', 'idtyp': 'user', 'oid': 'oid-none', 'azp': 'agent-app', 'scp': 'News.Read'},
    'fallback-oid': {'client_id': 'agent-app', 'idtyp': 'user', 'oid': 'oid-fallback', 'azp': 'agent-app',
                     'scp': 'News.Read'},
}
OID_ROLES = {'oid-fallback': ['News.Read.Health']}


# ── Stub GNews server (same tool names and arguments as the real one) ────────


def _run_stub(record_path, host, port):
    """Runs in a child process. Appends each call, with the headers it arrived with, to record_path."""
    deps = importlib.import_module('fastmcp.server.dependencies')
    stub = fastmcp.FastMCP('gnews-stub')

    def record(tool, args):
        headers = deps.get_http_headers(include_all=True)
        with open(record_path, 'a') as f:
            f.write(json.dumps({'tool': tool, 'args': args, 'x-api-key': headers.get('x-api-key'),
                                'authorization': headers.get('authorization')}) + '\n')

    @stub.tool
    def top_headlines(category: str = 'general', lang: str | None = None, country: str | None = None,
                      max: int = 10) -> str:
        record('top_headlines', {'category': category, 'lang': lang, 'country': country, 'max': max})
        return f'{max} {category} articles'

    @stub.tool
    def search(q: str, lang: str | None = None, country: str | None = None, max: int = 10,
               sortby: str | None = None) -> str:
        record('search', {'q': q, 'lang': lang, 'country': country, 'max': max, 'sortby': sortby})
        return f'{max} articles about {q}'

    stub.run(transport='http', host=host, port=port)


@pytest.fixture(scope='module')
def stub(tmp_path_factory):
    record = tmp_path_factory.mktemp('stub') / 'calls.jsonl'
    record.touch()
    with fastmcp_tests.run_server_in_process(_run_stub, str(record)) as url:
        yield url, record


@pytest.fixture(scope='module')
def wrapper(stub, tmp_path_factory):
    """Base URL of the wrapper and the file its stdout goes to."""
    stub_url, _ = stub
    log = tmp_path_factory.mktemp('wrapper') / 'stdout.jsonl'
    port = fastmcp_http.find_available_port()
    env = {
        **os.environ,
        'NEWS_MCP_AUTH_MODE': 'static',
        'NEWS_MCP_STATIC_TOKENS': json.dumps(TOKENS),
        'NEWS_MCP_OID_ROLES': json.dumps(OID_ROLES),
        'GNEWS_MCP_URL': f'{stub_url}/mcp',
        'GNEWS_API_KEY': 'test-key',
        'PORT': str(port),
    }
    base = f'http://127.0.0.1:{port}'
    with open(log, 'w') as out:
        proc = subprocess.Popen([sys.executable, str(_WRAPPER_DIR / 'server.py')], env=env, stdout=out)
        deadline = time.time() + 30
        while True:
            try:
                urllib.request.urlopen(f'{base}/health', timeout=1)
                break
            except OSError:
                if proc.poll() is not None or time.time() > deadline:
                    proc.kill()
                    raise RuntimeError('wrapper did not start')
                time.sleep(0.2)
        yield base, log
        proc.terminate()
        proc.wait(timeout=10)


def _client(base, token):
    return fastmcp.Client(transports.StreamableHttpTransport(f'{base}/mcp', headers={'Authorization': f'Bearer {token}'}))


def _list(base, token):
    async def go():
        async with _client(base, token) as client:
            return [tool.name for tool in await client.list_tools()]
    return asyncio.run(go())


def _call(base, token, name, arguments):
    """The raw MCP CallToolResult (isError and content), without the client raising on errors."""
    async def go():
        async with _client(base, token) as client:
            return await client.call_tool_mcp(name, arguments)
    return asyncio.run(go())


def _text(result):
    assert len(result.content) == 1
    return result.content[0].text


def _records(stub):
    return [json.loads(line) for line in stub[1].read_text().splitlines()]


def _post_mcp(base, body, token=None, auth_header=None):
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    if auth_header:
        headers['Authorization'] = auth_header
    request = urllib.request.Request(f'{base}/mcp', data=json.dumps(body).encode(), headers=headers, method='POST')
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


# ── tools/list per caller ────────────────────────────────────────────────────


def test_user_a_lists_all_ten_tools(wrapper):
    assert set(_list(wrapper[0], 'user-a')) == set(authz.TOOLS)


def test_user_b_lists_three_tools(wrapper):
    assert set(_list(wrapper[0], 'user-b')) == USER_B_TOOLS


def test_sports_agent_lists_one_tool(wrapper):
    assert _list(wrapper[0], 'agent-sports') == ['get_sports_headlines']


def test_no_roles_lists_nothing(wrapper):
    assert _list(wrapper[0], 'no-roles') == []


def test_missing_roles_claim_uses_the_oid_map(wrapper):
    assert _list(wrapper[0], 'fallback-oid') == ['get_health_headlines']


# ── tools/call: denial and forwarding ────────────────────────────────────────


def test_user_b_business_is_denied_before_gnews(wrapper, stub):
    before = len(_records(stub))
    result = _call(wrapper[0], 'user-b', 'get_business_headlines', {'max': 3})
    assert result.isError is True
    assert _text(result) == authz.denial_message(USER_B_ROLES)
    assert len(_records(stub)) == before


def test_user_b_search_is_denied(wrapper, stub):
    before = len(_records(stub))
    result = _call(wrapper[0], 'user-b', 'search_news', {'q': 'football'})
    assert result.isError is True
    assert _text(result) == authz.denial_message(USER_B_ROLES)
    assert len(_records(stub)) == before


def test_user_a_search_reaches_gnews(wrapper, stub):
    result = _call(wrapper[0], 'user-a', 'search_news', {'q': 'quantum computing', 'max': 2})
    assert result.isError is False
    assert _text(result) == '2 articles about quantum computing'
    assert _records(stub)[-1]['tool'] == 'search'
    assert _records(stub)[-1]['args']['q'] == 'quantum computing'


def test_user_b_sports_is_forwarded_with_max_capped(wrapper, stub):
    result = _call(wrapper[0], 'user-b', 'get_sports_headlines', {'max': 50})
    assert result.isError is False
    assert _text(result) == '10 sports articles'
    assert _records(stub)[-1] == {
        'tool': 'top_headlines', 'args': {'category': 'sports', 'lang': None, 'country': None, 'max': 10},
        'x-api-key': 'test-key', 'authorization': None}


def test_gnews_sees_the_key_and_never_the_caller_token(wrapper, stub):
    _call(wrapper[0], 'user-b', 'get_health_headlines', {})
    records = _records(stub)
    assert records
    assert all(r['x-api-key'] == 'test-key' for r in records)
    assert all(r['authorization'] is None for r in records)


def test_denial_on_the_wire_is_a_tool_result(wrapper):
    """A tools/call result with isError and one text item, not a JSON-RPC error object."""
    body = {'jsonrpc': '2.0', 'id': 7, 'method': 'tools/call',
            'params': {'name': 'get_business_headlines', 'arguments': {}}}
    status, text = _post_mcp(wrapper[0], body, token='user-b')
    assert status == 200
    data = [line[len('data:'):].strip() for line in text.splitlines() if line.startswith('data:')]
    message = json.loads(data[0] if data else text)
    assert 'error' not in message
    assert message['id'] == 7
    assert message['result']['isError'] is True
    assert message['result']['content'] == [{'type': 'text', 'text': authz.denial_message(USER_B_ROLES)}]


# ── Authentication and health ────────────────────────────────────────────────

TOOLS_LIST = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'}


def test_no_token_is_401(wrapper):
    assert _post_mcp(wrapper[0], TOOLS_LIST)[0] == 401


def test_malformed_token_is_401(wrapper):
    assert _post_mcp(wrapper[0], TOOLS_LIST, auth_header='Basic dXNlcjpwYXNz')[0] == 401


def test_unknown_token_is_401(wrapper):
    assert _post_mcp(wrapper[0], TOOLS_LIST, token='not-a-known-token')[0] == 401


def test_health_needs_no_token(wrapper):
    with urllib.request.urlopen(f'{wrapper[0]}/health', timeout=5) as response:
        assert response.status == 200


# ── Logs ─────────────────────────────────────────────────────────────────────


def _log_lines(wrapper):
    return [json.loads(line) for line in wrapper[1].read_text().splitlines() if line.startswith('{')]


def test_each_call_logs_the_caller_and_the_decision(wrapper):
    _call(wrapper[0], 'user-b', 'get_business_headlines', {})
    _call(wrapper[0], 'agent-sports', 'get_sports_headlines', {'max': 1})
    calls = [line for line in _log_lines(wrapper) if line['event'] == 'tools/call']
    denied, allowed = calls[-2], calls[-1]
    assert denied == {**denied, 'idtyp': 'user', 'oid': 'oid-b', 'azp': 'agent-app', 'roles': USER_B_ROLES,
                      'tool': 'get_business_headlines', 'decision': 'denied'}
    assert allowed == {**allowed, 'idtyp': 'app', 'oid': 'oid-sports-agent', 'appid': 'sports-agent-app',
                       'roles': ['News.Read.Sports'], 'tool': 'get_sports_headlines', 'decision': 'allowed'}
    assert 'azp' not in allowed


def test_each_session_logs_the_protocol_version(wrapper):
    _list(wrapper[0], 'user-a')
    lines = _log_lines(wrapper)
    sessions = [line for line in lines if line['event'] == 'initialize']
    assert sessions
    assert sessions[-1]['requested'] and sessions[-1]['negotiated']
    # After initialize the client sends the negotiated version as the MCP-Protocol-Version header.
    listing = [line for line in lines if line['event'] == 'tools/list'][-1]
    assert listing['mcp_protocol_version'] == sessions[-1]['negotiated']
