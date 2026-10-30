"""Request bodies for the Microsoft Graph, Foundry and ARM calls in 08-05c-01, and the
teardown inventory. Builders only: the notebook sends the requests.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'news-mcp-wrapper'))
import authz  # noqa: E402

GRAPH_APP_ID = '00000003-0000-0000-c000-000000000000'
# Delegated Graph permissions on news-desk-client. User.Read covers user B's test sign-in;
# the other two cover the Temporary Access Pass calls the Azure CLI token cannot make.
GRAPH_SCOPE_IDS = {
    'User.Read': 'e1fe6dd8-ba31-4d61-89e7-88639da4683d',
    'Policy.ReadWrite.AuthenticationMethod': '7e823077-d88e-468f-a337-e18f1f0e6c7c',
    'UserAuthenticationMethod.ReadWrite.All': 'b7887744-6746-4312-813d-72daeaee7e2d',
}

AGENT_API_VERSION = 'v1'
ENDPOINT_PATCH_CONTENT_TYPE = 'application/merge-patch+json'
BLUEPRINT_API_VERSION = '2025-05-01'

# No published contract covers a delegated RemoteTool connection, so 08-05c-01 tries these
# in order and keeps the first that ARM accepts.
CONNECTION_AUTH_TYPES = ('AgentOnBehalfOfUser', 'AgentUserImpersonation')
CONNECTION_API_VERSIONS = ('2025-04-01-preview', '2025-10-01-preview', '2026-09-15-preview')

AGENT_NAME = 'news-desk-agent'
AGENT_INSTRUCTIONS = (
    'You are a news desk assistant. Answer requests for headlines with the news tools and keep answers short. '
    'Ask the tools for English articles (lang en) unless the user names another language. '
    'If a news tool call is denied, tell the user exactly what the tool returned and do not try another '
    'category or tool for that request. If no news tool covers the category the user asks for, say that '
    'their access does not include it and do not fetch another category instead.'
)
AGENTS = (AGENT_NAME, 'news-all-agent', 'news-sports-agent')
CONNECTIONS = ('news-mcp-wrapper', 'news-mcp-apim', 'news-mcp-wrapper-all', 'news-mcp-wrapper-sports')


def scope_id(suffix):
    return authz.permission_id(suffix, authz.SCOPE)


# ── App registrations ────────────────────────────────────────────────────────


def _resource_api(suffix):
    return {
        'requestedAccessTokenVersion': 2,
        'oauth2PermissionScopes': [{
            'id': scope_id(suffix),
            'value': authz.SCOPE,
            'type': 'User',
            'isEnabled': True,
            'adminConsentDisplayName': 'Read news through the news MCP server',
            'adminConsentDescription': 'Lets the app call the news MCP server as the signed-in user. '
                                       'The categories the user can read come from their app roles.',
            'userConsentDisplayName': 'Read news on your behalf',
            'userConsentDescription': 'Lets the app read news headlines for you, limited to the categories you are assigned.',
        }],
    }


def resource_app_manifest(suffix):
    """news-mcp-{suffix}: the API both enforcement points validate tokens for."""
    return {
        'displayName': f'news-mcp-{suffix}',
        'signInAudience': 'AzureADMyOrg',
        'identifierUris': [authz.app_id_uri(suffix)],
        'api': _resource_api(suffix),
        'appRoles': [{
            'id': authz.permission_id(suffix, role),
            'value': role,
            'displayName': role,
            'description': ('Read headlines in every category and search all news' if role == authz.ALL_ROLE
                            else f'Read {role.rsplit(".", 1)[1].lower()} headlines'),
            'allowedMemberTypes': ['User', 'Application'],
            'isEnabled': True,
        } for role in authz.ROLES],
    }


def client_app_manifest(suffix, resource_app_id, blueprint_client_id=None, access_agent_scope_id=None):
    """news-desk-client-{suffix}: the public client users sign in to. The blueprint's
    access_agent scope is added once the agent, and so the blueprint, exists."""
    access = [
        {'resourceAppId': GRAPH_APP_ID,
         'resourceAccess': [{'id': i, 'type': 'Scope'} for i in GRAPH_SCOPE_IDS.values()]},
        {'resourceAppId': resource_app_id, 'resourceAccess': [{'id': scope_id(suffix), 'type': 'Scope'}]},
    ]
    if blueprint_client_id:
        access.append({'resourceAppId': blueprint_client_id,
                       'resourceAccess': [{'id': access_agent_scope_id, 'type': 'Scope'}]})
    return {
        'displayName': f'news-desk-client-{suffix}',
        'signInAudience': 'AzureADMyOrg',
        'isFallbackPublicClient': True,
        'publicClient': {'redirectUris': ['http://localhost']},
        'requiredResourceAccess': access,
    }


def preauthorization_patch(suffix, blueprint_client_id):
    """Preauthorize the agent blueprint for News.Read, so no user is asked to consent.
    The body repeats the scope and token version so the PATCH cannot drop them."""
    return {'api': {
        **_resource_api(suffix),
        'preAuthorizedApplications': [{'appId': blueprint_client_id, 'delegatedPermissionIds': [scope_id(suffix)]}],
    }}


def permission_grant_body(client_sp_id, resource_sp_id, scopes):
    """POST /oauth2PermissionGrants: admin consent, for every user, to delegated scopes."""
    return {'clientId': client_sp_id, 'consentType': 'AllPrincipals', 'resourceId': resource_sp_id,
            'scope': ' '.join(scopes)}


def blueprint_permissions_body(suffix, resource_app_id):
    """PATCH {project}/managedAgentIdentityBlueprints/{name}: declare News.Read on the blueprint and
    let delegated scopes granted on the blueprint principal flow to its agent identities.
    Declaring is not consent; Step 8 grants it."""
    return {
        'requiredResourceAccess': [
            {'resourceAppId': resource_app_id, 'resourceAccess': [{'id': scope_id(suffix), 'type': 'Scope'}]}],
        'inheritablePermissions': [
            {'resourceAppId': resource_app_id,
             'inheritableScopes': {'@odata.type': '#microsoft.graph.allAllowedScopes', 'kind': 'allAllowed'}}],
    }


def role_assignment_body(suffix, principal_id, resource_sp_id, role):
    """POST /servicePrincipals/{resource_sp_id}/appRoleAssignedTo"""
    return {'principalId': principal_id, 'resourceId': resource_sp_id, 'appRoleId': authz.permission_id(suffix, role)}


# ── Agent endpoint ───────────────────────────────────────────────────────────


def endpoint_schemes_body(client_app_id):
    """PATCH /agents/{name}: keep AzureRbac for Foundry-token callers and add AgentBlueprint
    for user tokens from news-desk-client. The PATCH replaces the whole array."""
    return {'agent_endpoint': {'authorization_schemes': [
        {'type': 'AzureRbac', 'isolation_key_source': {'kind': 'Entra'}},
        {'type': 'AgentBlueprint', 'isolation_key_source': {'kind': 'Entra'},
         'token_validation_rules': {'allowed_clients': [client_app_id]}},
    ]}}


def agent_reference(name, version):
    """extra_body that runs one version of an agent. Without it the agent endpoint runs the latest."""
    return {'agent_reference': {'type': 'agent_reference', 'name': name, 'version': str(version)}}


def latest_version_with_tool(versions, server_label):
    """The newest version number, as a string, among agent versions (as dicts) that carry an MCP
    tool with this server_label; None if none does."""
    numbers = [int(v['version']) for v in versions
               if any(t.get('server_label') == server_label for t in v['definition'].get('tools', []))]
    return str(max(numbers)) if numbers else None


def mcp_tool(server_label, server_url, connection_id):
    """An agent's MCP tool. The connection supplies the authentication; no approval step."""
    return {'type': 'mcp', 'server_label': server_label, 'server_url': server_url,
            'project_connection_id': connection_id, 'require_approval': 'never'}


# ── Project connections (ARM) ────────────────────────────────────────────────


def connection_attempts():
    return [(auth_type, version) for auth_type in CONNECTION_AUTH_TYPES for version in CONNECTION_API_VERSIONS]


def connection_url(subscription_id, suffix, name, api_version):
    return (
        f'https://management.azure.com/subscriptions/{subscription_id}/resourceGroups/rg-foundry-core-{suffix}'
        f'/providers/Microsoft.CognitiveServices/accounts/aif-core-{suffix}/projects/project-admin-{suffix}'
        f'/connections/{name}?api-version={api_version}'
    )


def delegated_connection_body(target, suffix, auth_type='AgentOnBehalfOfUser'):
    """The connection JSON from Learn's "Configure user delegation for tools"."""
    return {'properties': {
        'category': 'RemoteTool',
        'target': target,
        'authType': auth_type,
        'scopes': [f'{authz.app_id_uri(suffix)}/{authz.SCOPE}'],
        'metadata': {'type': 'generic_mcp'},
    }}


def agentic_connection_body(target, suffix):
    """Per-agent fallback: the agent's own identity calls the server, with no user in the token."""
    return {'properties': {
        'category': 'RemoteTool',
        'target': target,
        'authType': 'AgenticIdentityToken',
        'audience': authz.app_id_uri(suffix),
        'metadata': {'type': 'generic_mcp'},
    }}


# ── Temporary Access Pass ────────────────────────────────────────────────────


def tap_policy_patch():
    """PATCH /policies/authenticationMethodsPolicy/authenticationMethodConfigurations/temporaryAccessPass"""
    return {
        '@odata.type': '#microsoft.graph.temporaryAccessPassAuthenticationMethodConfiguration',
        'state': 'enabled',
        'isUsableOnce': False,
        'minimumLifetimeInMinutes': 60,
        'defaultLifetimeInMinutes': 60,
        'maximumLifetimeInMinutes': 480,
        'includeTargets': [{'targetType': 'group', 'id': 'all_users', 'isRegistrationRequired': False}],
    }


def tap_method_body():
    """POST /users/{id}/authentication/temporaryAccessPassMethods: one pass for the whole
    lab session. Tokens from a pass sign-in expire with the pass."""
    return {'isUsableOnce': False, 'lifetimeInMinutes': 480}


# ── Teardown ─────────────────────────────────────────────────────────────────


def teardown_inventory(env, suffix):
    """(description, kind, target) for everything the lab creates, in delete order.
    Entra objects whose ids never reached .env were not created and are left out."""
    items = [(f'agent {name} and its agent identity', 'agent', name) for name in AGENTS]
    items += [(f'project connection {name}', 'connection', name) for name in CONNECTIONS]
    items += [
        ('MCP API news-mcp on apim-foundry (its policy goes with it)', 'apim-api', 'news-mcp'),
        ('backend gnews-mcp on apim-foundry', 'apim-backend', 'gnews-mcp'),
        ('named value gnews-api-key on apim-foundry', 'apim-named-value', 'gnews-api-key'),
    ]
    rg = env.get('NEWS_MCP_RESOURCE_GROUP') or f'rg-foundry-news-mcp-{suffix}'
    items.append((f'resource group {rg} (Track A)', 'resource-group', rg))
    if env.get('NEWS_TEST_USER_ID'):
        items.append(('test user news-sports-desk', 'user', env['NEWS_TEST_USER_ID']))
    if env.get('NEWS_MCP_RESOURCE_APP_ID'):
        items.append((f'app news-mcp-{suffix} (its service principal, role assignments and consent grants go with it)',
                      'app', env['NEWS_MCP_RESOURCE_APP_ID']))
    if env.get('NEWS_DESK_CLIENT_APP_ID'):
        items.append((f'app news-desk-client-{suffix} (its service principal and consent grants go with it)',
                      'app', env['NEWS_DESK_CLIENT_APP_ID']))
    return items
