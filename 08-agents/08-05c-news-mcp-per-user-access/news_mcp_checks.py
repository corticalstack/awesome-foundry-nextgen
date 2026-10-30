"""The checks 08-05c-02 and 08-05c-03 run on both tracks: the same prompts as user A and
user B, a classifier for the agent's response, and a direct tools/list call to an MCP server.
"""

import json
import sys
from pathlib import Path
from typing import NamedTuple

import requests
from azure.identity import DeviceCodeCredential, InteractiveBrowserCredential, get_bearer_token_provider
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).parent / 'news-mcp-wrapper'))
import authz  # noqa: E402


# ── The matrix ───────────────────────────────────────────────────────────────


class Case(NamedTuple):
    user: str            # 'A' (News.Read.All) or 'B' (sports, science, health)
    category: str
    expected: str        # 'articles' or 'denied'
    required: bool = True


BASE_CASES = (
    Case('A', 'business', 'articles'),
    Case('B', 'business', 'denied'),
    Case('B', 'sports', 'articles'),
)


def science_case(expected, required=True):
    """User B asks for science. The expected outcome depends on whether, and how long ago,
    08-05c-02 revoked News.Read.Science, so the notebook supplies it."""
    return Case('B', 'science', expected, required)


def prompt(category):
    return f'Give me three {category} headlines'


FALLBACK_CALLS = 2  # one call each through news-all-agent and news-sports-agent


def gnews_budget():
    """Upper bound on GNews requests for one run of 08-05c-02 and 08-05c-03. The free plan
    allows 100 a day. A denied call never reaches GNews."""
    per_track = sum(c.expected == 'articles' for c in BASE_CASES)
    return 2 * per_track + 1 + FALLBACK_CALLS + 1  # + science on Track A, + the Track A re-check


# ── Calling the agent as a user ──────────────────────────────────────────────


def openai_base_url(project_endpoint, agent):
    return f'{project_endpoint}/agents/{agent}/endpoint/protocols/openai'


def user_credential(tenant_id, client_id, upn=None, device_code=False):
    """Sign-in through news-desk-client. Device code lets user B sign in from a separate
    (InPrivate) browser window, away from the admin's session."""
    if device_code:
        return DeviceCodeCredential(client_id=client_id, tenant_id=tenant_id)
    return InteractiveBrowserCredential(
        client_id=client_id, tenant_id=tenant_id, login_hint=upn, redirect_uri='http://localhost')


def agent_client(credential, project_endpoint, agent, blueprint_client_id):
    """OpenAI client for the agent endpoint, authorized by the AgentBlueprint scheme."""
    provider = get_bearer_token_provider(credential, f'api://{blueprint_client_id}/access_agent')
    return OpenAI(base_url=openai_base_url(project_endpoint, agent), api_key=provider)


# ── Reading a response (response.model_dump()) ───────────────────────────────


def _items(response, kind):
    return [item for item in response['output'] if item['type'] == kind]


def _output_text(response):
    return ''.join(part['text'] for msg in _items(response, 'message')
                   for part in msg['content'] if part['type'] == 'output_text')


def listed_tools(response):
    return [tool['name'] for item in _items(response, 'mcp_list_tools') for tool in item['tools']]


def called_tools(response):
    return [(call['name'], json.loads(call['arguments'] or '{}')) for call in _items(response, 'mcp_call')]


def classify(response, roles):
    """'denied' if a tool call returned the denial text for these roles, 'articles' if a
    tool call returned content, 'unknown' otherwise. The model's own text is checked for
    the denial only when the response carries no tool call items."""
    denial = authz.denial_message(roles)
    calls = _items(response, 'mcp_call')
    if any(denial in (c.get('output') or '') or denial in (c.get('error') or '') for c in calls):
        return 'denied'
    if any(c.get('output') and not c.get('error') for c in calls):
        return 'articles'
    if not calls and denial in _output_text(response):
        return 'denied'
    return 'unknown'


gnews_calls = 0  # tool calls that returned articles in this kernel, against the daily quota


def run_matrix(clients, cases, roles, extra_body=None):
    """Send each case's prompt as its user and print one line per case.

    clients and roles are keyed by user ('A', 'B'); roles are the user's current
    assignments, which set the denial text to look for. Raises AssertionError after the
    last case if a required case did not get its expected outcome.
    """
    global gnews_calls
    records = []
    for case in cases:
        text = prompt(case.category)
        response = clients[case.user].responses.create(input=text, extra_body=extra_body).model_dump()
        outcome = classify(response, roles[case.user])
        called = called_tools(response)
        if outcome == 'articles':
            gnews_calls += len(called)
        record = {
            'user': case.user, 'category': case.category, 'listed': listed_tools(response), 'called': called,
            'outcome': outcome, 'expected': case.expected, 'required': case.required,
            'passed': outcome == case.expected,
        }
        records.append(record)
        print(f'{case.user} | {text:<35} | listed {len(record["listed"]):>2} | '
              f'called {", ".join(name for name, _ in called) or "-":<24} | {outcome:<8} | '
              f'expected {case.expected:<8} | {"PASS" if record["passed"] else "FAIL"}'
              f'{"" if case.required else " (not required)"}')
    print(f'GNews calls so far: {gnews_calls} (budget for a full run: {gnews_budget()})')
    failed = [r for r in records if r['required'] and not r['passed']]
    if failed:
        raise AssertionError('Unexpected outcome for: ' + ', '.join(f'{r["user"]} {r["category"]}' for r in failed))
    return records


# ── tools/list straight to an MCP server ─────────────────────────────────────


def parse_jsonrpc(body):
    """The result of a JSON-RPC response sent as one JSON object or as server-sent events."""
    if body.lstrip().startswith('{'):
        message = json.loads(body)
    else:
        data = [line[len('data:'):].strip() for line in body.splitlines() if line.startswith('data:')]
        message = next(m for m in map(json.loads, data) if 'result' in m or 'error' in m)
    if 'error' in message:
        raise RuntimeError(f'JSON-RPC error {message["error"]["code"]}: {message["error"]["message"]}')
    return message['result']


def tool_names(result):
    return [tool['name'] for tool in result['tools']]


def list_tools_direct(url, token):
    """tools/list with the caller's own token. The wrapper runs stateless, so it answers
    without an initialize round trip."""
    r = requests.post(
        url,
        json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'},
        headers={'Authorization': f'Bearer {token}', 'Accept': 'application/json, text/event-stream'},
        timeout=30,
    )
    r.raise_for_status()
    return tool_names(parse_jsonrpc(r.text))
