"""Tests for the multi-agent module.

Fast tests (no live Azure calls) verify construction and graph topology.
Live tests are guarded by CONTOSO_LIVE_TESTS=true and require .env populated
from 11-01-deploy-setup.ipynb.
"""
import os
import sys
import pytest
from pathlib import Path

# sys.path is configured by conftest.py in this directory
LAB_DIR = Path(__file__).resolve().parents[1]

LIVE = os.getenv('CONTOSO_LIVE_TESTS', '').lower() == 'true'

FAKE_ENDPOINT   = 'https://fake-project.services.ai.azure.com/api/projects/contoso-project'
FAKE_SEARCH_EP  = 'https://fake-search.search.windows.net'
FAKE_MODEL      = 'gpt-4.1-mini'
FAKE_CONN       = 'contoso-apim-connection'


# ─────────────────────────────────────────────────────────────────────────────
# Import tests
# ─────────────────────────────────────────────────────────────────────────────

def test_agents_package_importable():
    from agents import (  # noqa: F401
        create_hr_agent,
        create_marketing_agent,
        create_products_agent,
        create_orchestrator_agent,
        build_contoso_workflow,
    )


def test_hr_agent_module_importable():
    from agents.hr_agent import create_hr_agent  # noqa: F401


def test_marketing_agent_module_importable():
    from agents.marketing_agent import create_marketing_agent  # noqa: F401


def test_products_agent_module_importable():
    from agents.products_agent import create_products_agent  # noqa: F401


def test_orchestrator_module_importable():
    from agents.orchestrator import create_orchestrator_agent, build_contoso_workflow  # noqa: F401


# ─────────────────────────────────────────────────────────────────────────────
# Construction tests - no live calls, uses fake endpoints
# ─────────────────────────────────────────────────────────────────────────────

def test_hr_agent_constructs():
    from agents.hr_agent import create_hr_agent
    from azure.identity import DefaultAzureCredential
    agent = create_hr_agent(FAKE_ENDPOINT, FAKE_SEARCH_EP, FAKE_MODEL, FAKE_CONN, DefaultAzureCredential())
    assert agent is not None
    assert agent.name == 'contoso-hr-agent'


def test_marketing_agent_constructs():
    from agents.marketing_agent import create_marketing_agent
    from azure.identity import DefaultAzureCredential
    agent = create_marketing_agent(FAKE_ENDPOINT, FAKE_SEARCH_EP, FAKE_MODEL, FAKE_CONN, DefaultAzureCredential())
    assert agent is not None
    assert agent.name == 'contoso-marketing-agent'


def test_products_agent_constructs():
    from agents.products_agent import create_products_agent
    from azure.identity import DefaultAzureCredential
    agent = create_products_agent(FAKE_ENDPOINT, FAKE_SEARCH_EP, FAKE_MODEL, FAKE_CONN, DefaultAzureCredential())
    assert agent is not None
    assert agent.name == 'contoso-products-agent'


def test_orchestrator_constructs():
    from agents.orchestrator import create_orchestrator_agent
    from azure.identity import DefaultAzureCredential
    agent = create_orchestrator_agent(FAKE_ENDPOINT, FAKE_MODEL, FAKE_CONN, DefaultAzureCredential())
    assert agent is not None
    assert agent.name == 'contoso-orchestrator'


def test_workflow_builds():
    """WorkflowBuilder.build() must not raise with all four agents."""
    from agents.hr_agent import create_hr_agent
    from agents.marketing_agent import create_marketing_agent
    from agents.products_agent import create_products_agent
    from agents.orchestrator import create_orchestrator_agent, build_contoso_workflow
    from azure.identity import DefaultAzureCredential

    cred = DefaultAzureCredential()
    hr   = create_hr_agent(FAKE_ENDPOINT, FAKE_SEARCH_EP, FAKE_MODEL, FAKE_CONN, cred)
    mkt  = create_marketing_agent(FAKE_ENDPOINT, FAKE_SEARCH_EP, FAKE_MODEL, FAKE_CONN, cred)
    prd  = create_products_agent(FAKE_ENDPOINT, FAKE_SEARCH_EP, FAKE_MODEL, FAKE_CONN, cred)
    orch = create_orchestrator_agent(FAKE_ENDPOINT, FAKE_MODEL, FAKE_CONN, cred)

    workflow = build_contoso_workflow(orch, hr, mkt, prd)
    assert workflow is not None


# ─────────────────────────────────────────────────────────────────────────────
# Live tests - require CONTOSO_LIVE_TESTS=true and populated .env
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.skipif(not LIVE, reason='Set CONTOSO_LIVE_TESTS=true to run live tests')
def test_hr_agent_live_query():
    """HR agent returns a grounded response about Contoso HR policies."""
    import asyncio
    from dotenv import load_dotenv
    from azure.identity import DefaultAzureCredential
    from agents.hr_agent import create_hr_agent

    load_dotenv(Path(__file__).resolve().parents[1] / '.env', override=True)
    cred  = DefaultAzureCredential()
    agent = create_hr_agent(
        os.environ['CONTOSO_FOUNDRY_PROJECT_ENDPOINT'],
        os.environ['CONTOSO_SEARCH_ENDPOINT'],
        os.environ.get('CHAT_MODEL', FAKE_MODEL),
        os.environ['CONTOSO_APIM_CONNECTION'],
        cred,
    )
    result = asyncio.get_event_loop().run_until_complete(
        agent.run('What is the Contoso remote work policy?')
    )
    assert result.text


@pytest.mark.skipif(not LIVE, reason='Set CONTOSO_LIVE_TESTS=true to run live tests')
def test_workflow_routes_hr_query():
    """WorkflowBuilder routes an HR query to the HR specialist agent."""
    import asyncio
    from dotenv import load_dotenv
    from azure.identity import DefaultAzureCredential
    from agents.hr_agent import create_hr_agent
    from agents.marketing_agent import create_marketing_agent
    from agents.products_agent import create_products_agent
    from agents.orchestrator import create_orchestrator_agent, build_contoso_workflow

    load_dotenv(Path(__file__).resolve().parents[1] / '.env', override=True)
    cred = DefaultAzureCredential()
    project_ep  = os.environ['CONTOSO_FOUNDRY_PROJECT_ENDPOINT']
    search_ep   = os.environ['CONTOSO_SEARCH_ENDPOINT']
    model       = os.environ.get('CHAT_MODEL', FAKE_MODEL)
    conn        = os.environ['CONTOSO_APIM_CONNECTION']

    hr   = create_hr_agent(project_ep, search_ep, model, conn, cred)
    mkt  = create_marketing_agent(project_ep, search_ep, model, conn, cred)
    prd  = create_products_agent(project_ep, search_ep, model, conn, cred)
    orch = create_orchestrator_agent(project_ep, model, conn, cred)

    workflow  = build_contoso_workflow(orch, hr, mkt, prd)
    from agent_framework import WorkflowAgent
    wa        = WorkflowAgent(workflow, name='contoso-workflow')
    result    = asyncio.get_event_loop().run_until_complete(
        wa.run('What are the PTO accrual rates at Contoso?')
    )
    assert result.text
