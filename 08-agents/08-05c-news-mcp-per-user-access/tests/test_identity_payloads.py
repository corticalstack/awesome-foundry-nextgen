"""Unit tests for news_mcp_identity.py: the request bodies 08-05c-01 sends to Microsoft
Graph, Foundry and ARM, and the teardown inventory. No network calls.
"""

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    'news_mcp_identity', Path(__file__).parents[1] / 'news_mcp_identity.py')
ident = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ident)
authz = ident.authz

SUFFIX = 'abc123'
RESOURCE_APP_ID = '11111111-1111-1111-1111-111111111111'
CLIENT_APP_ID = '22222222-2222-2222-2222-222222222222'
BLUEPRINT_CLIENT_ID = '33333333-3333-3333-3333-333333333333'
ACCESS_AGENT_SCOPE_ID = '44444444-4444-4444-4444-444444444444'
TARGET = 'https://apim-foundry-abc123.azure-api.net/news-mcp/mcp'

GRAPH_APP_ID = '00000003-0000-0000-c000-000000000000'
POLICY_RW_AUTH_METHOD = '7e823077-d88e-468f-a337-e18f1f0e6c7c'
USER_AUTH_METHOD_RW_ALL = 'b7887744-6746-4312-813d-72daeaee7e2d'


def _access(manifest, resource_app_id):
    """Return {id: type} for one resource in requiredResourceAccess."""
    entries = [r for r in manifest['requiredResourceAccess'] if r['resourceAppId'] == resource_app_id]
    assert len(entries) == 1
    return {a['id']: a['type'] for a in entries[0]['resourceAccess']}


# ── Resource app ─────────────────────────────────────────────────────────────


def test_resource_app_names_and_uri():
    m = ident.resource_app_manifest(SUFFIX)
    assert m['displayName'] == 'news-mcp-abc123'
    assert m['identifierUris'] == ['api://news-mcp-abc123']
    assert m['signInAudience'] == 'AzureADMyOrg'


def test_resource_app_issues_v2_tokens():
    assert ident.resource_app_manifest(SUFFIX)['api']['requestedAccessTokenVersion'] == 2


def test_resource_app_has_one_delegated_scope():
    scopes = ident.resource_app_manifest(SUFFIX)['api']['oauth2PermissionScopes']
    assert len(scopes) == 1
    scope = scopes[0]
    assert scope['value'] == 'News.Read'
    assert scope['id'] == ident.scope_id(SUFFIX) == authz.permission_id(SUFFIX, 'News.Read')
    assert scope['isEnabled'] is True
    for key in ('adminConsentDisplayName', 'adminConsentDescription', 'userConsentDisplayName', 'userConsentDescription'):
        assert scope[key]


def test_resource_app_roles():
    roles = ident.resource_app_manifest(SUFFIX)['appRoles']
    assert [r['value'] for r in roles] == list(authz.ROLES)
    for r in roles:
        assert r['id'] == authz.permission_id(SUFFIX, r['value'])
        assert r['allowedMemberTypes'] == ['User', 'Application']
        assert r['isEnabled'] is True
        assert r['displayName'] and r['description']


def test_resource_app_manifest_is_the_same_on_every_run():
    assert ident.resource_app_manifest(SUFFIX) == ident.resource_app_manifest(SUFFIX)


# ── Client app ───────────────────────────────────────────────────────────────


def test_client_app_is_a_public_client_on_localhost():
    m = ident.client_app_manifest(SUFFIX, RESOURCE_APP_ID)
    assert m['displayName'] == 'news-desk-client-abc123'
    assert m['signInAudience'] == 'AzureADMyOrg'
    assert m['isFallbackPublicClient'] is True
    assert m['publicClient'] == {'redirectUris': ['http://localhost']}


def test_client_app_requests_news_read_and_the_graph_permissions():
    m = ident.client_app_manifest(SUFFIX, RESOURCE_APP_ID)
    assert _access(m, RESOURCE_APP_ID) == {ident.scope_id(SUFFIX): 'Scope'}
    graph = _access(m, GRAPH_APP_ID)
    assert graph[POLICY_RW_AUTH_METHOD] == 'Scope'
    assert graph[USER_AUTH_METHOD_RW_ALL] == 'Scope'
    assert set(graph.values()) == {'Scope'}  # delegated only, no application permissions
    assert BLUEPRINT_CLIENT_ID not in {r['resourceAppId'] for r in m['requiredResourceAccess']}


def test_client_app_adds_access_agent_once_the_blueprint_exists():
    m = ident.client_app_manifest(SUFFIX, RESOURCE_APP_ID, BLUEPRINT_CLIENT_ID, ACCESS_AGENT_SCOPE_ID)
    assert _access(m, BLUEPRINT_CLIENT_ID) == {ACCESS_AGENT_SCOPE_ID: 'Scope'}
    assert _access(m, RESOURCE_APP_ID) == {ident.scope_id(SUFFIX): 'Scope'}
    assert POLICY_RW_AUTH_METHOD in _access(m, GRAPH_APP_ID)


def test_graph_constants_match_the_well_known_ids():
    assert ident.GRAPH_APP_ID == GRAPH_APP_ID
    assert ident.GRAPH_SCOPE_IDS['Policy.ReadWrite.AuthenticationMethod'] == POLICY_RW_AUTH_METHOD
    assert ident.GRAPH_SCOPE_IDS['UserAuthenticationMethod.ReadWrite.All'] == USER_AUTH_METHOD_RW_ALL


# ── Preauthorization of the blueprint ────────────────────────────────────────


def test_preauthorization_names_the_blueprint_and_the_scope():
    api = ident.preauthorization_patch(SUFFIX, BLUEPRINT_CLIENT_ID)['api']
    assert api['preAuthorizedApplications'] == [
        {'appId': BLUEPRINT_CLIENT_ID, 'delegatedPermissionIds': [ident.scope_id(SUFFIX)]}]


def test_preauthorization_keeps_the_scope_and_token_version():
    api = ident.preauthorization_patch(SUFFIX, BLUEPRINT_CLIENT_ID)['api']
    resource_api = ident.resource_app_manifest(SUFFIX)['api']
    assert api['oauth2PermissionScopes'] == resource_api['oauth2PermissionScopes']
    assert api['requestedAccessTokenVersion'] == 2


# ── Consent ──────────────────────────────────────────────────────────────────


def test_permission_grant_body():
    assert ident.permission_grant_body('client-sp-id', 'resource-sp-id', ['News.Read']) == {
        'clientId': 'client-sp-id', 'consentType': 'AllPrincipals', 'resourceId': 'resource-sp-id', 'scope': 'News.Read'}


def test_permission_grant_joins_scopes_with_spaces():
    body = ident.permission_grant_body('c', 'r', list(ident.GRAPH_SCOPE_IDS))
    assert body['scope'] == 'User.Read Policy.ReadWrite.AuthenticationMethod UserAuthenticationMethod.ReadWrite.All'


def test_blueprint_permissions_body():
    assert ident.blueprint_permissions_body(SUFFIX, RESOURCE_APP_ID) == {
        'requiredResourceAccess': [
            {'resourceAppId': RESOURCE_APP_ID, 'resourceAccess': [{'id': ident.scope_id(SUFFIX), 'type': 'Scope'}]}],
        'inheritablePermissions': [
            {'resourceAppId': RESOURCE_APP_ID,
             'inheritableScopes': {'@odata.type': '#microsoft.graph.allAllowedScopes', 'kind': 'allAllowed'}}],
    }
    assert ident.BLUEPRINT_API_VERSION == '2025-05-01'


# ── Agent endpoint authorization schemes ─────────────────────────────────────


def test_endpoint_schemes_body():
    schemes = ident.endpoint_schemes_body(CLIENT_APP_ID)['agent_endpoint']['authorization_schemes']
    by_type = {s['type']: s for s in schemes}
    assert set(by_type) == {'AzureRbac', 'AgentBlueprint'}
    assert by_type['AzureRbac']['isolation_key_source'] == {'kind': 'Entra'}
    assert by_type['AgentBlueprint']['isolation_key_source'] == {'kind': 'Entra'}
    assert by_type['AgentBlueprint']['token_validation_rules'] == {'allowed_clients': [CLIENT_APP_ID]}


def test_endpoint_patch_content_type():
    assert ident.ENDPOINT_PATCH_CONTENT_TYPE == 'application/merge-patch+json'
    assert ident.AGENT_API_VERSION == 'v1'


# ── Agent ────────────────────────────────────────────────────────────────────


def test_agent_instructions_forbid_retrying_another_category():
    assert ident.AGENT_NAME == 'news-desk-agent'
    assert 'exactly what the tool returned' in ident.AGENT_INSTRUCTIONS
    assert 'do not try another category' in ident.AGENT_INSTRUCTIONS
    assert 'lang en' in ident.AGENT_INSTRUCTIONS  # GNews returns every language unless asked
    assert 'do not fetch another category instead' in ident.AGENT_INSTRUCTIONS  # Track A hides tools


def test_agent_reference():
    """extra_body that runs one version through the agent endpoint, which otherwise runs the latest."""
    assert ident.agent_reference('news-desk-agent', 4) == {
        'agent_reference': {'type': 'agent_reference', 'name': 'news-desk-agent', 'version': '4'}}


def _version(number, *labels):
    return {'version': str(number), 'definition': {'tools': [{'type': 'mcp', 'server_label': label} for label in labels]}}


def test_latest_version_with_tool():
    versions = [_version(5, 'news_mcp_apim'), _version(4, 'news_mcp_wrapper'), _version(3, 'news_mcp_wrapper'), _version(1)]
    assert ident.latest_version_with_tool(versions, 'news_mcp_wrapper') == '4'
    assert ident.latest_version_with_tool(versions, 'news_mcp_apim') == '5'
    assert ident.latest_version_with_tool([_version(1)], 'news_mcp_wrapper') is None


def test_mcp_tool():
    assert ident.mcp_tool('news_mcp_wrapper', 'https://ca.example/mcp', '/subscriptions/x/connections/news-mcp-wrapper') == {
        'type': 'mcp', 'server_label': 'news_mcp_wrapper', 'server_url': 'https://ca.example/mcp',
        'project_connection_id': '/subscriptions/x/connections/news-mcp-wrapper', 'require_approval': 'never'}


# ── Connections ──────────────────────────────────────────────────────────────


def test_delegated_connection_body_matches_learn():
    assert ident.delegated_connection_body(TARGET, SUFFIX) == {'properties': {
        'category': 'RemoteTool',
        'target': TARGET,
        'authType': 'AgentOnBehalfOfUser',
        'scopes': ['api://news-mcp-abc123/News.Read'],
        'metadata': {'type': 'generic_mcp'},
    }}


def test_user_impersonation_variant_differs_only_in_auth_type():
    obo = ident.delegated_connection_body(TARGET, SUFFIX)
    alt = ident.delegated_connection_body(TARGET, SUFFIX, 'AgentUserImpersonation')
    assert alt['properties'].pop('authType') == 'AgentUserImpersonation'
    obo['properties'].pop('authType')
    assert alt == obo


def test_agentic_identity_connection_body():
    props = ident.agentic_connection_body(TARGET, SUFFIX)['properties']
    assert props['category'] == 'RemoteTool'
    assert props['target'] == TARGET
    assert props['authType'] == 'AgenticIdentityToken'
    assert props['audience'] == 'api://news-mcp-abc123'
    assert 'scopes' not in props


def test_connection_attempts_in_fixed_order():
    assert ident.connection_attempts() == [
        ('AgentOnBehalfOfUser', '2025-04-01-preview'),
        ('AgentOnBehalfOfUser', '2025-10-01-preview'),
        ('AgentOnBehalfOfUser', '2026-09-15-preview'),
        ('AgentUserImpersonation', '2025-04-01-preview'),
        ('AgentUserImpersonation', '2025-10-01-preview'),
        ('AgentUserImpersonation', '2026-09-15-preview'),
    ]


def test_connection_url():
    url = ident.connection_url('sub-id', SUFFIX, 'news-mcp-apim', '2025-04-01-preview')
    assert url == (
        'https://management.azure.com/subscriptions/sub-id/resourceGroups/rg-foundry-core-abc123'
        '/providers/Microsoft.CognitiveServices/accounts/aif-core-abc123/projects/project-admin-abc123'
        '/connections/news-mcp-apim?api-version=2025-04-01-preview')


# ── App role assignment ──────────────────────────────────────────────────────


def test_role_assignment_body():
    assert ident.role_assignment_body(SUFFIX, 'user-oid', 'resource-sp-id', 'News.Read.Sports') == {
        'principalId': 'user-oid',
        'resourceId': 'resource-sp-id',
        'appRoleId': authz.permission_id(SUFFIX, 'News.Read.Sports'),
    }


# ── Temporary Access Pass ────────────────────────────────────────────────────


def test_tap_policy_patch():
    body = ident.tap_policy_patch()
    assert body['@odata.type'] == '#microsoft.graph.temporaryAccessPassAuthenticationMethodConfiguration'
    assert body['state'] == 'enabled'
    assert body['isUsableOnce'] is False
    assert body['includeTargets'] == [{'targetType': 'group', 'id': 'all_users', 'isRegistrationRequired': False}]
    lifetimes = [body[k] for k in ('minimumLifetimeInMinutes', 'defaultLifetimeInMinutes', 'maximumLifetimeInMinutes')]
    assert lifetimes == sorted(lifetimes)
    assert 10 <= lifetimes[0] and lifetimes[-1] <= 480


def test_tap_method_body():
    assert ident.tap_method_body() == {'isUsableOnce': False, 'lifetimeInMinutes': 480}
    assert ident.tap_method_body()['lifetimeInMinutes'] <= ident.tap_policy_patch()['maximumLifetimeInMinutes']


# ── Teardown inventory ───────────────────────────────────────────────────────

ENV = {
    'NEWS_TEST_USER_ID': 'user-oid',
    'NEWS_MCP_RESOURCE_APP_ID': RESOURCE_APP_ID,
    'NEWS_DESK_CLIENT_APP_ID': CLIENT_APP_ID,
    'NEWS_MCP_RESOURCE_SP_ID': 'resource-sp-id',
    'NEWS_AGENT_BLUEPRINT_CLIENT_ID': BLUEPRINT_CLIENT_ID,
    'NEWS_TEST_USER_TAP': 'not-a-target',
}
NAMED = {
    ('agent', 'news-desk-agent'), ('agent', 'news-all-agent'), ('agent', 'news-sports-agent'),
    ('connection', 'news-mcp-wrapper'), ('connection', 'news-mcp-apim'),
    ('connection', 'news-mcp-wrapper-all'), ('connection', 'news-mcp-wrapper-sports'),
    ('apim-api', 'news-mcp'), ('apim-backend', 'gnews-mcp'), ('apim-named-value', 'gnews-api-key'),
    ('resource-group', 'rg-foundry-news-mcp-abc123'),
}


def test_teardown_names_each_object_once_and_nothing_else():
    inventory = ident.teardown_inventory(ENV, SUFFIX)
    pairs = [(kind, target) for _, kind, target in inventory]
    assert len(pairs) == len(set(pairs))
    assert set(pairs) == NAMED | {('user', 'user-oid'), ('app', RESOURCE_APP_ID), ('app', CLIENT_APP_ID)}


def test_teardown_order():
    pairs = [(kind, target) for _, kind, target in ident.teardown_inventory(ENV, SUFFIX)]
    kinds = [kind for kind, _ in pairs]
    # Agents reference the connections; the API policy references the named value.
    assert max(i for i, k in enumerate(kinds) if k == 'agent') < min(i for i, k in enumerate(kinds) if k == 'connection')
    assert pairs.index(('apim-api', 'news-mcp')) < pairs.index(('apim-named-value', 'gnews-api-key'))
    assert pairs.index(('apim-api', 'news-mcp')) < pairs.index(('apim-backend', 'gnews-mcp'))  # the API refers to it


def test_teardown_says_role_assignments_go_with_the_resource_app():
    descriptions = {target: d for d, _, target in ident.teardown_inventory(ENV, SUFFIX)}
    assert 'role assignments' in descriptions[RESOURCE_APP_ID]


def test_teardown_uses_the_resource_group_from_env():
    inventory = ident.teardown_inventory({**ENV, 'NEWS_MCP_RESOURCE_GROUP': 'rg-custom'}, SUFFIX)
    assert [t for _, k, t in inventory if k == 'resource-group'] == ['rg-custom']


def test_teardown_skips_objects_never_created():
    pairs = {(kind, target) for _, kind, target in ident.teardown_inventory({}, SUFFIX)}
    assert pairs == NAMED
