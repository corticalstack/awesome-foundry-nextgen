"""Contoso multi-agent module — Lab 11: Foundry IQ Multi-Agent."""

from .hr_agent import create_hr_agent
from .marketing_agent import create_marketing_agent
from .products_agent import create_products_agent
from .orchestrator import create_orchestrator_agent, build_contoso_workflow

__all__ = [
    'create_hr_agent',
    'create_marketing_agent',
    'create_products_agent',
    'create_orchestrator_agent',
    'build_contoso_workflow',
]
