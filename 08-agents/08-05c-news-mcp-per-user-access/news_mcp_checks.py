"""The checks 08-05c-02 and 08-05c-03 run on both tracks: the same prompts as user A and
user B, a classifier for the agent's response, and direct tools/list and tools/call requests
to an MCP server.
"""

import base64
import json
import re
import sys
from pathlib import Path
from typing import NamedTuple

import requests
from azure.identity import DeviceCodeCredential, InteractiveBrowserCredential, get_bearer_token_provider
from openai import BadRequestError, OpenAI

sys.path.insert(0, str(Path(__file__).parent / 'news-mcp-wrapper'))
import authz  # noqa: E402


# ── The matrix ───────────────────────────────────────────────────────────────


class Case(NamedTuple):
    user: str            # 'A' (News.Read.All) or 'B' (sports, science, health)
    category: str
    expected: str        # an outcome from classify: 'articles', 'denied' or 'hidden'
    required: bool = True


def base_cases(track):
    """A business, B business, B sports. On 'wrapper' (Track A) user B's tools/list leaves the
    business tool out, so the agent has nothing to call ('hidden'). On 'apim' (Track B) everyone
    sees GNews's own tools and the policy denies the call ('denied')."""
    return (
        Case('A', 'business', 'articles'),
        Case('B', 'business', 'hidden' if track == 'wrapper' else 'denied'),
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
    article_cases = sum(c.expected == 'articles' for track in ('wrapper', 'apim') for c in base_cases(track))
    return article_cases + 1 + FALLBACK_CALLS + 1  # + science on Track A, + the Track A re-check


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


def jwt_claims(token):
    """A JWT's payload, for display and for checking who signed in. The signature is not checked:
    the token came straight from Entra to this process."""
    payload = token.split('.')[1]
    return json.loads(base64.urlsafe_b64decode(payload + '=' * (-len(payload) % 4)))


def agent_client(credential, project_endpoint, agent, blueprint_client_id):
    """OpenAI client for the agent endpoint, authorized by the AgentBlueprint scheme. The endpoint
    requires api-version=v1, which AIProjectClient.get_openai_client also sends."""
    provider = get_bearer_token_provider(credential, f'api://{blueprint_client_id}/access_agent')
    return OpenAI(base_url=openai_base_url(project_endpoint, agent), api_key=provider,
                  default_query={'api-version': 'v1'})


def ask(client, text, extra_body=None):
    """The agent's response to `text` as a dict. When the model calls a tool the MCP server did not
    list, Foundry answers HTTP 400 ('Tool ... not found on remote server') before anything reaches
    the server; that comes back as {'output': [], 'rejected_tool': name}."""
    try:
        # warnings=False: the SDK does not model Foundry's extra fields on MCP items and warns on each dump.
        return client.responses.create(input=text, extra_body=extra_body).model_dump(warnings=False)
    except BadRequestError as e:
        rejected = re.search(r'Tool (\S+) not found on remote server', str(e))
        if not rejected:
            raise
        return {'output': [], 'rejected_tool': rejected.group(1)}


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


def _asks_for(call, category):
    """Whether a tool call can answer a request for `category`: the wrapper's tool for it,
    GNews's top_headlines with it (no category means general), or a search on either server."""
    name, arguments = call['name'], json.loads(call['arguments'] or '{}')
    return (name in (authz.tool_for(category), authz.SEARCH_TOOL, 'search')
            or (name == 'top_headlines' and arguments.get('category', 'general') == category))


def classify(response, roles, category):
    """The outcome of asking for `category` headlines with these roles:

    'denied'       a tool call returned the denial text for the roles (with no tool call at
                   all, the model's reply quoting it counts too)
    'articles'     a call for this category returned content
    'substituted'  content came only from calls for other categories
    'hidden'       the server listed no tool for this category and the agent called nothing,
                   or Foundry refused the agent's call to that tool as not listed
    'unknown'      anything else
    """
    denial = authz.denial_message(roles)
    calls = _items(response, 'mcp_call')
    if any(denial in (c.get('output') or '') or denial in (c.get('error') or '') for c in calls):
        return 'denied'
    answered = [c for c in calls if c.get('output') and not c.get('error')]
    if any(_asks_for(c, category) for c in answered):
        return 'articles'
    if answered:
        return 'substituted'
    if not calls and denial in _output_text(response):
        return 'denied'
    if response.get('rejected_tool') == authz.tool_for(category):
        return 'hidden'
    listed = listed_tools(response)
    if not calls and _items(response, 'mcp_list_tools') and not {authz.tool_for(category), 'top_headlines'} & set(listed):
        return 'hidden'
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
        response = ask(clients[case.user], text, extra_body)
        outcome = classify(response, roles[case.user], case.category)
        called = called_tools(response)
        if outcome in ('articles', 'substituted'):
            gnews_calls += len(called)
        record = {
            'user': case.user, 'category': case.category, 'listed': listed_tools(response), 'called': called,
            'outcome': outcome, 'expected': case.expected, 'required': case.required,
            'passed': outcome == case.expected,
        }
        records.append(record)
        print(f'{case.user} | {text:<35} | listed {len(record["listed"]):>2} | '
              f'called {", ".join(name for name, _ in called) or "-":<24} | {outcome:<11} | '
              f'expected {case.expected:<8} | {"PASS" if record["passed"] else "FAIL"}'
              f'{"" if case.required else " (not required)"}')
    print(f'GNews calls so far: {gnews_calls} (budget for a full run: {gnews_budget()})')
    failed = [r for r in records if r['required'] and not r['passed']]
    if failed:
        raise AssertionError('Unexpected outcome for: ' + ', '.join(f'{r["user"]} {r["category"]}' for r in failed))
    return records


# ── The wrapper's log lines ──────────────────────────────────────────────────


def wrapper_events(lines, kind=None):
    """The wrapper's JSON events from Container Apps console log lines, optionally of one kind
    ('initialize', 'tools/list', 'tools/call', 'upstream'). A line is the event itself, or an
    entry from `az containerapp logs show --format json` (Log) or Log Analytics (Log_s) that
    holds it after an optional prefix. Other lines, such as uvicorn's access log, are skipped."""
    events = []
    for line in lines:
        try:
            entry = json.loads(line)
        except ValueError:
            entry = None
        if isinstance(entry, dict) and 'event' not in entry:
            line, entry = entry.get('Log') or entry.get('Log_s') or '', None
        if entry is None and '{' in line:
            try:
                entry = json.loads(line[line.index('{'):])
            except ValueError:
                continue
        if isinstance(entry, dict) and 'event' in entry and kind in (None, entry['event']):
            events.append(entry)
    return events


# ── tools/list and tools/call straight to an MCP server ──────────────────────


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


def call_tool_direct(url, token, name, arguments):
    """tools/call with the caller's own token. Returns the result: its content items and
    isError, which is how an MCP server reports a tool that refused to run."""
    r = requests.post(
        url,
        json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': name, 'arguments': arguments}},
        headers={'Authorization': f'Bearer {token}', 'Accept': 'application/json, text/event-stream'},
        timeout=60,
    )
    r.raise_for_status()
    return parse_jsonrpc(r.text)
