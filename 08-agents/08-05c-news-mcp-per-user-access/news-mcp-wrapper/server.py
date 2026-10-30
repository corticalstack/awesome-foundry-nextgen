"""News MCP wrapper: Track A of lab 08-05c.

Validates the caller's Entra token, lists only the news tools the caller's app roles grant,
answers any other call with authz.denial_message, and forwards allowed calls to the GNews
MCP server with the GNews key. The key never leaves this process and the caller's token
never reaches GNews.

One log line per event goes to stdout as JSON, so Container Apps console logs show who
called, with which roles, and what was decided.
"""

import json
import os

import uvicorn
from fastmcp import Client, FastMCP
from fastmcp.client.transports import StreamableHttpTransport
from fastmcp.exceptions import ToolError
from fastmcp.server.auth.providers.jwt import JWTVerifier, StaticTokenVerifier
from fastmcp.server.dependencies import get_access_token, get_http_headers
from fastmcp.server.middleware import Middleware
from fastmcp.tools import ToolResult
from starlette.requests import Request
from starlette.responses import PlainTextResponse

import authz

AUTH_MODE = os.environ.get('NEWS_MCP_AUTH_MODE', 'entra')
GNEWS_MCP_URL = os.environ.get('GNEWS_MCP_URL', 'https://mcp.gnews.io/')
# Object id -> roles, read from Graph. Used only if delegated tokens arrive without `roles`.
OID_ROLES = json.loads(os.environ.get('NEWS_MCP_OID_ROLES') or '{}')


def log(**fields):
    print(json.dumps(fields), flush=True)


if AUTH_MODE == 'static':
    # Test mode: bearer strings map to fixed claims. Never set this in Azure.
    log(event='startup', warning='NEWS_MCP_AUTH_MODE=static: accepting test tokens, not Entra tokens')
    verifier = StaticTokenVerifier(tokens=json.loads(os.environ['NEWS_MCP_STATIC_TOKENS']))
else:
    tenant = os.environ['ENTRA_TENANT_ID']
    # v1 and v2 issuers and both audience forms (client id and App ID URI). No required
    # scopes: the per-agent fallback sends app-only tokens, which carry no scp.
    verifier = JWTVerifier(
        jwks_uri=f'https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys',
        issuer=[f'https://sts.windows.net/{tenant}/', f'https://login.microsoftonline.com/{tenant}/v2.0'],
        audience=os.environ['NEWS_MCP_AUDIENCES'].split(','),
    )

# A plain Client, not a proxy: it sends only the headers set here, so the caller's
# Authorization header is never forwarded. Entering it per call is reentrant.
upstream = Client(StreamableHttpTransport(GNEWS_MCP_URL, headers={'X-Api-Key': os.environ['GNEWS_API_KEY']}))


def _caller(token):
    """The caller's identity and the identity fields for a log line, under the claim names the token used."""
    claims = token.claims if token else {}
    who = authz.identity_from_claims(claims, OID_ROLES)
    fields = {'idtyp': who.kind, 'oid': who.oid, 'azp' if 'azp' in claims else 'appid': who.app_id,
              'roles': who.roles, 'scp': claims.get('scp'), 'aud': claims.get('aud')}
    return who, fields


def allowed(ctx):
    """auth= check on every tool: the second layer behind NewsAccess, with the same rule."""
    who, _ = _caller(ctx.token)
    return ctx.component.name in authz.allowed_tools(who.roles)


class NewsAccess(Middleware):
    """Filters tools/list and denies tools/call by the caller's roles. It runs before the
    server looks the tool up, so a denied caller gets the denial text rather than the
    `Unknown tool` error that auth= alone would produce."""

    async def on_initialize(self, context, call_next):
        result = await call_next(context)
        log(event='initialize', requested=context.message.params.protocolVersion,
            negotiated=result.protocolVersion if result else None,
            client=context.message.params.clientInfo.name)
        return result

    async def on_list_tools(self, context, call_next):
        tools = await call_next(context)
        who, fields = _caller(get_access_token())
        visible = [t for t in tools if t.name in authz.allowed_tools(who.roles)]
        log(event='tools/list', **fields, tools=[t.name for t in visible],
            mcp_protocol_version=get_http_headers().get('mcp-protocol-version'))
        return visible

    async def on_call_tool(self, context, call_next):
        who, fields = _caller(get_access_token())
        tool = context.message.name
        decision = 'allowed' if tool in authz.allowed_tools(who.roles) else 'denied'
        log(event='tools/call', **fields, tool=tool, decision=decision,
            mcp_protocol_version=get_http_headers().get('mcp-protocol-version'))
        if decision == 'denied':
            raise ToolError(authz.denial_message(who.roles))
        return await call_next(context)


mcp = FastMCP('news-mcp-wrapper', auth=verifier, middleware=[NewsAccess()])


async def _gnews(tool, arguments):
    """Call a GNews tool and pass its result through unchanged."""
    arguments = {k: v for k, v in arguments.items() if v is not None}
    async with upstream:
        result = await upstream.call_tool_mcp(tool, arguments)
    log(event='upstream', tool=tool, arguments=arguments, is_error=result.isError)
    if result.isError:
        raise ToolError(' '.join(c.text for c in result.content if c.type == 'text'))
    return ToolResult(content=result.content, structured_content=result.structuredContent)


def _headlines_tool(category):
    async def headlines(max: int | None = None, lang: str | None = None, country: str | None = None) -> ToolResult:
        return await _gnews('top_headlines', {'category': category, 'max': authz.clamp_max(max),
                                              'lang': lang, 'country': country})
    return headlines


for _category in authz.CATEGORIES:
    mcp.tool(
        _headlines_tool(_category),
        name=authz.tool_for(_category),
        description=f'Latest {_category} news headlines from GNews. max: 1 to {authz.MAX_ARTICLES} articles; '
                    'lang and country: optional two-letter codes.',
        auth=allowed,
    )


@mcp.tool(auth=allowed)
async def search_news(q: str, max: int | None = None, lang: str | None = None, country: str | None = None,
                      sortby: str | None = None) -> ToolResult:
    """Search news articles in every category by keywords. max: 1 to 10 articles; sortby: publishedAt or relevance."""
    return await _gnews('search', {'q': q, 'max': authz.clamp_max(max), 'lang': lang, 'country': country,
                                   'sortby': sortby})


@mcp.custom_route('/health', methods=['GET'])
async def health(request: Request) -> PlainTextResponse:
    """Container Apps probes. Outside /mcp, so no token is needed."""
    return PlainTextResponse('ok')


# Stateless: every request stands alone, so any replica can serve it.
app = mcp.http_app(path='/mcp', stateless_http=True)

if __name__ == '__main__':
    log(event='startup', auth_mode=AUTH_MODE, upstream=GNEWS_MCP_URL)
    uvicorn.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', '8080')),
                log_level=os.environ.get('LOG_LEVEL', 'info'))
