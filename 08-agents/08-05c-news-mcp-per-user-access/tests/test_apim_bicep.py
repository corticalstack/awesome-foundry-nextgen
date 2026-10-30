"""Structure of infra/apim-news-mcp.bicep, checked on the ARM template `az bicep build` compiles.
Skipped where the Azure CLI is not installed.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

BICEP = Path(__file__).parents[1] / 'infra' / 'apim-news-mcp.bicep'
API_VERSION = '2024-06-01-preview'

pytestmark = pytest.mark.skipif(shutil.which('az') is None, reason='needs the Azure CLI for az bicep build')


@pytest.fixture(scope='module')
def template():
    result = subprocess.run(['az', 'bicep', 'build', '--file', str(BICEP), '--stdout'],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.fixture(scope='module')
def resources(template):
    found = template['resources']
    # Templates that use symbolic names hold a dict of resources instead of a list.
    return list(found.values()) if isinstance(found, dict) else found


def _one(resources, resource_type):
    matches = [r for r in resources if r['type'] == resource_type and not r.get('existing')]
    assert len(matches) == 1, f'{resource_type}: {len(matches)} found'
    assert matches[0]['apiVersion'] == API_VERSION
    return matches[0]


def test_gateway_is_referenced_not_deployed(resources):
    """05-02 owns apim-foundry-{suffix}; this template only adds to it."""
    assert not [r for r in resources if r['type'] == 'Microsoft.ApiManagement/service' and not r.get('existing')]


def test_secret_named_value(resources):
    named_value = _one(resources, 'Microsoft.ApiManagement/service/namedValues')
    assert 'gnews-api-key' in json.dumps(named_value['name'])
    assert named_value['properties']['secret'] is True
    assert named_value['properties']['displayName'] == 'gnews-api-key'


def test_backend_is_the_gnews_mcp_endpoint(resources):
    backend = _one(resources, 'Microsoft.ApiManagement/service/backends')
    assert 'gnews-mcp' in json.dumps(backend['name'])
    assert backend['properties']['url'] == 'https://mcp.gnews.io/'
    assert backend['properties']['protocol'] == 'http'


def test_mcp_api_passes_through_to_the_backend(resources):
    """An MCP API with a backendId proxies an existing MCP server. Without one, APIM answers
    initialize itself and lists the tools of its own operations: none."""
    api = _one(resources, 'Microsoft.ApiManagement/service/apis')
    props = api['properties']
    assert props['type'] == 'mcp'
    assert props['path'] == 'news-mcp'
    assert props['protocols'] == ['https']
    assert props['subscriptionRequired'] is False
    assert props['backendId'] == 'gnews-mcp'
    assert props['mcpProperties'] == {'transportType': 'streamable'}
    assert 'serviceUrl' not in props


def test_api_policy_is_the_policy_file(template, resources):
    policy = _one(resources, 'Microsoft.ApiManagement/service/apis/policies')
    assert policy['properties']['format'] == 'rawxml'
    # loadTextContent compiles to a template variable that the value expression refers to.
    loaded = [name for name, value in template['variables'].items()
              if isinstance(value, str) and value == (BICEP.parent / 'news-mcp-policy.xml').read_text()]
    assert len(loaded) == 1
    assert f"variables('{loaded[0]}')" in policy['properties']['value']


def test_mcp_url_is_the_endpoint_under_the_api_path(template):
    """APIM serves an MCP API's endpoint at /mcp under the API's path; /news-mcp itself is 404."""
    assert template['outputs']['mcpUrl']['value'].startswith("[format('{0}/news-mcp/mcp', ")
    assert template['outputs']['mcpUrl']['value'].endswith('.gatewayUrl)]')
