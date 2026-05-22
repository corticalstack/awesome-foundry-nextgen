"""Contoso Orchestrator Agent.

A lightweight classifier that routes user queries to the appropriate Contoso
specialist agent (HR, Marketing, or Products) using WorkflowBuilder routing.
"""
from agent_framework import Agent, Case, Default, Workflow, WorkflowBuilder
from agent_framework_foundry import FoundryChatClient

_INSTRUCTIONS = """\
You are a query routing assistant for Contoso Corporation. Classify the user's question \
into exactly one of three domains and respond with only the domain label:

- HR          - questions about HR policies, benefits, PTO, onboarding, performance, compensation
- MARKETING   - questions about campaigns, brand, social media, email marketing, SEO, competitors
- PRODUCTS    - questions about Contoso products, specifications, features, pricing, availability

Respond with exactly one word: HR, MARKETING, or PRODUCTS.
Do not include any explanation or punctuation."""


def create_orchestrator_agent(
    project_endpoint: str,
    model_name: str,
    connection_name: str,
    credential,
) -> Agent:
    """Construct the orchestrator / routing agent.

    Args:
        project_endpoint: Foundry project endpoint URL.
        model_name: Chat model deployment name (e.g. 'gpt-4.1-mini').
        connection_name: APIM connection on the project (e.g. 'contoso-apim-connection').
        credential: Azure credential (e.g. DefaultAzureCredential).

    Returns:
        A lightweight Agent that classifies queries to HR, MARKETING, or PRODUCTS.
    """
    client = FoundryChatClient(
        project_endpoint=project_endpoint,
        model=f'{connection_name}/{model_name}',
        credential=credential,
        allow_preview=True,
    )

    return Agent(
        client=client,
        instructions=_INSTRUCTIONS,
        name='contoso-orchestrator',
        description='Routes Contoso queries to the HR, Marketing, or Products specialist.',
    )


def build_contoso_workflow(
    orchestrator: Agent,
    hr_agent: Agent,
    marketing_agent: Agent,
    products_agent: Agent,
) -> Workflow:
    """Build the Contoso multi-agent routing workflow.

    Graph:
        [user query]
              ↓
        orchestrator   (classifies: HR | MARKETING | PRODUCTS)
              ↓
        ┌─────┼──────┐
      hr_agent │ marketing_agent
               products_agent (Default)

    Each specialist answers using its knowledge base and returns the grounded response.

    Args:
        orchestrator:     Routing agent - classifies the query.
        hr_agent:         HR specialist - answers from contoso-kb-hr.
        marketing_agent:  Marketing specialist - answers from contoso-kb-marketing.
        products_agent:   Products specialist - answers from contoso-kb-products (Default).

    Returns:
        Built Workflow ready to run.
    """
    # In a Workflow, case conditions receive an AgentExecutorResponse that wraps
    # the underlying AgentResponse - the classifier's text lives on .agent_response.
    def _is_hr(response) -> bool:
        text = str(response.agent_response.text).upper()
        return 'HR' in text and 'MARKETING' not in text

    def _is_marketing(response) -> bool:
        return 'MARKETING' in str(response.agent_response.text).upper()

    workflow = (
        WorkflowBuilder(
            start_executor=orchestrator,
            output_executors=[hr_agent, marketing_agent, products_agent],
        )
        .add_switch_case_edge_group(
            source=orchestrator,
            cases=[
                Case(condition=_is_hr,        target=hr_agent),
                Case(condition=_is_marketing,  target=marketing_agent),
                Default(target=products_agent),
            ],
        )
        .build()
    )
    return workflow
