"""Unit tests for news-mcp-wrapper/authz.py: categories, roles, tools, the denial text,
token claims and the article cap.

Standard library only, so the file runs in the repo environment and inside the wrapper
image, where NEWS_MCP_WRAPPER_DIR points at /app.
"""

import importlib.util
import os
import uuid
from pathlib import Path

import pytest

# Load authz.py by path under its own name, so no other suite's module can shadow it.
_WRAPPER_DIR = Path(os.environ.get('NEWS_MCP_WRAPPER_DIR', Path(__file__).parents[1] / 'news-mcp-wrapper'))
_spec = importlib.util.spec_from_file_location('news_mcp_authz', _WRAPPER_DIR / 'authz.py')
authz = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(authz)

GNEWS_ORDER = ['general', 'world', 'nation', 'business', 'technology', 'entertainment', 'sports', 'science', 'health']
USER_B_ROLES = ['News.Read.Sports', 'News.Read.Science', 'News.Read.Health']
USER_B_TOOLS = {'get_sports_headlines', 'get_science_headlines', 'get_health_headlines'}


# ── Catalogue ────────────────────────────────────────────────────────────────


def test_categories_follow_gnews_order():
    assert list(authz.CATEGORIES) == GNEWS_ORDER


@pytest.mark.parametrize('category', GNEWS_ORDER)
def test_every_category_has_a_role_and_a_tool(category):
    assert authz.role_for(category) == f'News.Read.{category.capitalize()}'
    assert authz.tool_for(category) == f'get_{category}_headlines'


def test_tool_catalogue_has_ten_names():
    assert len(authz.TOOLS) == 10
    assert set(authz.TOOLS) == {f'get_{c}_headlines' for c in GNEWS_ORDER} | {'search_news'}


def test_roles_are_all_plus_one_per_category():
    assert authz.ROLES == ('News.Read.All', *(f'News.Read.{c.capitalize()}' for c in GNEWS_ORDER))


# ── Allowed tools ────────────────────────────────────────────────────────────


def test_all_role_allows_every_tool():
    assert authz.allowed_tools(['News.Read.All']) == set(authz.TOOLS)


def test_user_b_roles_allow_three_headline_tools():
    assert authz.allowed_tools(USER_B_ROLES) == USER_B_TOOLS


def test_search_needs_the_all_role():
    assert 'search_news' not in authz.allowed_tools([r for r in authz.ROLES if r != 'News.Read.All'])


@pytest.mark.parametrize('roles', [
    [], None, ['News.Read.sports'], ['News.Read.Sport'], ['Sports'], ['News.Read.'],
    ['news.read.all'], ['News.Read.All '], ['News.Read.Weather'],
])
def test_no_or_malformed_roles_allow_nothing(roles):
    assert authz.allowed_tools(roles) == set()


def test_unknown_roles_beside_a_valid_one_are_ignored():
    assert authz.allowed_tools(['Admin', 'News.Read.Sports', 'News.Read.Weather']) == {'get_sports_headlines'}


# ── Allowed categories ───────────────────────────────────────────────────────


def test_allowed_categories_keep_gnews_order():
    shuffled = ['News.Read.Health', 'News.Read.Sports', 'News.Read.Science']
    assert authz.allowed_categories(shuffled) == ['sports', 'science', 'health']


def test_all_role_allows_every_category():
    assert authz.allowed_categories(['News.Read.All']) == GNEWS_ORDER


@pytest.mark.parametrize('roles', [['News.Read.All'], USER_B_ROLES, ['News.Read.Business'], []])
def test_allowed_categories_match_the_tool_mapping(roles):
    headline_tools = authz.allowed_tools(roles) - {'search_news'}
    assert headline_tools == {authz.tool_for(c) for c in authz.allowed_categories(roles)}


# ── Denial message ───────────────────────────────────────────────────────────


def test_denial_message_for_user_b_in_any_claim_order():
    expected = 'Your access covers: sports, science, health. Do not retry other categories.'
    assert authz.denial_message(USER_B_ROLES) == expected
    assert authz.denial_message(list(reversed(USER_B_ROLES))) == expected


@pytest.mark.parametrize('roles', [[], None, ['Admin']])
def test_denial_message_without_categories(roles):
    assert authz.denial_message(roles) == 'Your access covers no news categories. Do not retry.'


def test_denial_message_for_all_role_lists_every_category():
    expected = f'Your access covers: {", ".join(GNEWS_ORDER)}. Do not retry other categories.'
    assert authz.denial_message(['News.Read.All']) == expected


# ── Identity from token claims ───────────────────────────────────────────────

V2_USER = {
    'ver': '2.0', 'idtyp': 'user', 'tid': 'tenant-id', 'oid': 'user-b-oid', 'azp': 'agent-app-id',
    'scp': 'News.Read', 'roles': USER_B_ROLES,
}
V1_APP = {
    'ver': '1.0', 'idtyp': 'app', 'tid': 'tenant-id', 'oid': 'agent-sp-oid', 'appid': 'agent-app-id',
    'roles': ['News.Read.Sports'],
}


def test_v2_user_token():
    assert authz.identity_from_claims(V2_USER) == authz.Identity(
        kind='user', oid='user-b-oid', app_id='agent-app-id', roles=USER_B_ROLES, tenant='tenant-id')


def test_v1_app_token():
    assert authz.identity_from_claims(V1_APP) == authz.Identity(
        kind='app', oid='agent-sp-oid', app_id='agent-app-id', roles=['News.Read.Sports'], tenant='tenant-id')


def test_without_idtyp_scp_means_user():
    claims = {k: v for k, v in V2_USER.items() if k != 'idtyp'}
    assert authz.identity_from_claims(claims).kind == 'user'


def test_without_idtyp_or_scp_means_app():
    claims = {k: v for k, v in V1_APP.items() if k != 'idtyp'}
    assert authz.identity_from_claims(claims).kind == 'app'


def test_missing_roles_claim_means_no_roles():
    claims = {k: v for k, v in V2_USER.items() if k != 'roles'}
    assert authz.identity_from_claims(claims).roles == []


def test_missing_roles_claim_falls_back_to_the_oid_map():
    claims = {k: v for k, v in V2_USER.items() if k != 'roles'}
    fallback = {'user-b-oid': ['News.Read.Sports'], 'someone-else': ['News.Read.All']}
    assert authz.identity_from_claims(claims, fallback).roles == ['News.Read.Sports']


def test_oid_map_without_the_caller_means_no_roles():
    claims = {k: v for k, v in V2_USER.items() if k != 'roles'}
    assert authz.identity_from_claims(claims, {'someone-else': ['News.Read.All']}).roles == []


def test_roles_claim_wins_over_the_oid_map():
    assert authz.identity_from_claims(V2_USER, {'user-b-oid': ['News.Read.All']}).roles == USER_B_ROLES


# ── Article cap ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize('requested, sent', [
    (None, 10), (11, 10), (50, 10), (100, 10), (0, 1), (-3, 1), (1, 1), (3, 3), (10, 10),
])
def test_clamp_max(requested, sent):
    assert authz.clamp_max(requested) == sent


# ── Deterministic ids for app roles and the scope ────────────────────────────


def test_app_id_uri():
    assert authz.app_id_uri('abc123') == 'api://news-mcp-abc123'


def test_permission_id_is_stable():
    assert authz.permission_id('abc123', 'News.Read.Sports') == authz.permission_id('abc123', 'News.Read.Sports')


def test_permission_id_is_a_guid():
    assert str(uuid.UUID(authz.permission_id('abc123', 'News.Read.All'))) == authz.permission_id('abc123', 'News.Read.All')


def test_permission_ids_differ_across_values_and_suffixes():
    ids = {authz.permission_id('abc123', r) for r in authz.ROLES} | {authz.permission_id('abc123', 'News.Read')}
    assert len(ids) == len(authz.ROLES) + 1
    assert authz.permission_id('abc123', 'News.Read.All') != authz.permission_id('def456', 'News.Read.All')
