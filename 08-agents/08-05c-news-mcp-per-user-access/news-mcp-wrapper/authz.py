"""News categories, Entra app roles and wrapper tools, and the rules that connect them.

The wrapper (server.py) enforces these rules; the notebooks use them to build the resource
app and to recognise a denial; the APIM policy in ../infra carries the same category order
and denial text, which tests/test_policy.py compares against this file. Standard library only.
"""

import uuid
from typing import NamedTuple

# GNews top_headlines categories, in the order GNews documents them. Every list of
# categories this lab prints or returns follows this order.
CATEGORIES = ('general', 'world', 'nation', 'business', 'technology', 'entertainment', 'sports', 'science', 'health')

ALL_ROLE = 'News.Read.All'
SCOPE = 'News.Read'
SEARCH_TOOL = 'search_news'
MAX_ARTICLES = 10  # GNews free plan returns at most 10 articles per request


def role_for(category):
    return f'News.Read.{category.capitalize()}'


def tool_for(category):
    return f'get_{category}_headlines'


ROLES = (ALL_ROLE, *(role_for(c) for c in CATEGORIES))
TOOLS = (*(tool_for(c) for c in CATEGORIES), SEARCH_TOOL)


def allowed_categories(roles):
    """Categories the roles grant, in GNews order. Role values that match no category are ignored."""
    roles = set(roles or ())
    if ALL_ROLE in roles:
        return list(CATEGORIES)
    return [c for c in CATEGORIES if role_for(c) in roles]


def allowed_tools(roles):
    """Tool names the roles grant. search_news spans every category, so it needs News.Read.All."""
    tools = {tool_for(c) for c in allowed_categories(roles)}
    if ALL_ROLE in set(roles or ()):
        tools.add(SEARCH_TOOL)
    return tools


def denial_message(roles):
    """The text a denied tool call returns, on both tracks. It names what the caller may
    read and tells the model not to try other categories."""
    categories = allowed_categories(roles)
    if not categories:
        return 'Your access covers no news categories. Do not retry.'
    return f'Your access covers: {", ".join(categories)}. Do not retry other categories.'


class Identity(NamedTuple):
    kind: str     # 'user' (delegated token) or 'app' (app-only token)
    oid: str      # object id of the user, or of the agent's service principal
    app_id: str   # the calling app: azp in v2 tokens, appid in v1 tokens
    roles: list
    tenant: str


def identity_from_claims(claims, oid_roles=None):
    """Normalise v1 and v2 Entra access-token claims.

    Entra omits `roles` when the caller holds none. If the delegated token turns out to
    carry no `roles` at all, `oid_roles` (object id to role list, read from Graph) stands in.
    """
    kind = claims.get('idtyp') or ('user' if 'scp' in claims else 'app')
    oid = claims.get('oid')
    if 'roles' in claims:
        roles = list(claims['roles'])
    else:
        roles = list((oid_roles or {}).get(oid, []))
    return Identity(kind, oid, claims.get('azp') or claims.get('appid'), roles, claims.get('tid'))


def clamp_max(value):
    """Article count sent upstream: 1 to MAX_ARTICLES, MAX_ARTICLES when not given."""
    if value is None:
        return MAX_ARTICLES
    return min(max(value, 1), MAX_ARTICLES)


def app_id_uri(suffix):
    return f'api://news-mcp-{suffix}'


def permission_id(suffix, value):
    """Fixed GUID for an app role or scope on news-mcp-{suffix}. Re-running the manifest
    PATCH sends the same ids; new ids would remove enabled roles, which Entra refuses."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f'{app_id_uri(suffix)}/{value}'))
