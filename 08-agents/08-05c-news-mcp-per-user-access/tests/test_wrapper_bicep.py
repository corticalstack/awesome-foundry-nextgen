"""Structure of infra/wrapper.bicep, checked on the ARM template `az bicep build` compiles.
Skipped where the Azure CLI is not installed.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

BICEP = Path(__file__).parents[1] / 'infra' / 'wrapper.bicep'

pytestmark = pytest.mark.skipif(shutil.which('az') is None, reason='needs the Azure CLI for az bicep build')


@pytest.fixture(scope='module')
def resources():
    result = subprocess.run(['az', 'bicep', 'build', '--file', str(BICEP), '--stdout'],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    found = json.loads(result.stdout)['resources']
    # Templates that use symbolic names hold a dict of resources instead of a list.
    return list(found.values()) if isinstance(found, dict) else found


def _one(resources, resource_type):
    matches = [r for r in resources if r['type'] == resource_type]
    assert len(matches) == 1, f'{resource_type}: {len(matches)} found'
    return matches[0]


def test_log_analytics_workspace(resources):
    workspace = _one(resources, 'Microsoft.OperationalInsights/workspaces')
    assert workspace['properties']['sku']['name'] == 'PerGB2018'


def test_basic_registry_without_admin_user(resources):
    registry = _one(resources, 'Microsoft.ContainerRegistry/registries')
    assert registry['sku']['name'] == 'Basic'
    assert registry['properties']['adminUserEnabled'] is False


def test_identity_can_pull_from_the_registry(resources):
    _one(resources, 'Microsoft.ManagedIdentity/userAssignedIdentities')
    assignment = _one(resources, 'Microsoft.Authorization/roleAssignments')
    assert '7f951dda-4ed3-4680-a7ca-43fe172d538d' in assignment['properties']['roleDefinitionId']  # AcrPull


def test_environment_sends_logs_to_the_workspace(resources):
    environment = _one(resources, 'Microsoft.App/managedEnvironments')
    assert environment['properties']['appLogsConfiguration']['destination'] == 'log-analytics'


def test_container_app(resources):
    app = _one(resources, 'Microsoft.App/containerApps')
    assert 'condition' in app  # deployed in the second pass, once the image exists
    config, template = app['properties']['configuration'], app['properties']['template']
    assert config['ingress']['external'] is True
    assert config['ingress']['targetPort'] == 8080
    assert [s['name'] for s in config['secrets']] == ['gnews-api-key']
    assert template['scale']['minReplicas'] == 1
    container = template['containers'][0]
    assert {'name': 'GNEWS_API_KEY', 'secretRef': 'gnews-api-key'} in container['env']
    probes = {p['type']: p['httpGet'] for p in container['probes']}
    assert set(probes) == {'Liveness', 'Readiness'}
    assert all(p['path'] == '/health' and p['port'] == 8080 for p in probes.values())
