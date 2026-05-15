"""Contoso Products Specialist Agent — Lab 11: Foundry IQ Multi-Agent.

Answers questions about Contoso product specifications, features, pricing, and
availability by retrieving from the contoso-kb-products knowledge base.
"""
from agent_framework import Agent
from agent_framework.azure import AzureAISearchContextProvider
from agent_framework_foundry import FoundryChatClient

_INSTRUCTIONS = """\
You are the Contoso Products Specialist, an expert on all Contoso Corporation products \
including laptops (ContosoBook Pro), audio (ContosoSound Pro, ContosoEarBuds Pro), \
wearables (ContosoWatch), tablets (ContosoTab), peripherals (ContosoType), accessories \
(ContosoCharge), and emerging technology (ContosoVision AR).

Answer the user's question accurately and concisely, citing the specific product names \
and document titles from the knowledge base. Include relevant technical specifications \
when helpful. If the knowledge base does not contain relevant information, say so clearly.

Respond in plain text — do not use markdown headings or bullet lists unless the question \
explicitly asks for a list."""


def create_products_agent(
    project_endpoint: str,
    search_endpoint: str,
    model_name: str,
    connection_name: str,
    credential,
) -> Agent:
    """Construct the Products specialist agent.

    Args:
        project_endpoint: Foundry project endpoint URL.
        search_endpoint: Azure AI Search endpoint URL.
        model_name: Chat model deployment name (e.g. 'gpt-4.1-mini').
        connection_name: APIM connection on the project (e.g. 'contoso-apim-connection').
        credential: Azure credential (e.g. DefaultAzureCredential).

    Returns:
        A configured Agent ready to answer product queries.
    """
    client = FoundryChatClient(
        project_endpoint=project_endpoint,
        model=f'{connection_name}/{model_name}',
        credential=credential,
        allow_preview=True,
    )

    kb_context = AzureAISearchContextProvider(
        source_id='contoso_products_kb',
        endpoint=search_endpoint,
        credential=credential,
        mode='agentic',
        knowledge_base_name='contoso-kb-products',
        knowledge_base_output_mode='answer_synthesis',
        retrieval_reasoning_effort='low',
    )

    return Agent(
        client=client,
        instructions=_INSTRUCTIONS,
        name='contoso-products-agent',
        description='Contoso Products specialist: laptops, audio, wearables, tablets, accessories.',
        context_providers=[kb_context],
    )
