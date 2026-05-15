"""Contoso HR Specialist Agent — Lab 11: Foundry IQ Multi-Agent.

Answers questions about Contoso HR policies, benefits, PTO, onboarding,
and employee programs by retrieving from the contoso-kb-hr knowledge base.
"""
from agent_framework import Agent
from agent_framework.azure import AzureAISearchContextProvider
from agent_framework_foundry import FoundryChatClient

_INSTRUCTIONS = """\
You are the Contoso HR Specialist, an expert on all Contoso Corporation human resources \
topics including policies, benefits, compensation, time off, onboarding, performance \
reviews, and professional development.

Answer the user's question accurately and concisely, citing the specific document titles \
from the knowledge base to support your answer. If the knowledge base does not contain \
relevant information, say so clearly rather than guessing.

Respond in plain text — do not use markdown headings or bullet lists unless the question \
explicitly asks for a list."""


def create_hr_agent(
    project_endpoint: str,
    search_endpoint: str,
    model_name: str,
    connection_name: str,
    credential,
) -> Agent:
    """Construct the HR specialist agent.

    Args:
        project_endpoint: Foundry project endpoint URL.
        search_endpoint: Azure AI Search endpoint URL.
        model_name: Chat model deployment name (e.g. 'gpt-4.1-mini').
        connection_name: APIM connection on the project (e.g. 'contoso-apim-connection').
        credential: Azure credential (e.g. DefaultAzureCredential).

    Returns:
        A configured Agent ready to answer HR queries.
    """
    client = FoundryChatClient(
        project_endpoint=project_endpoint,
        model=f'{connection_name}/{model_name}',
        credential=credential,
        allow_preview=True,
    )

    kb_context = AzureAISearchContextProvider(
        source_id='contoso_hr_kb',
        endpoint=search_endpoint,
        credential=credential,
        mode='agentic',
        knowledge_base_name='contoso-kb-hr',
        knowledge_base_output_mode='answer_synthesis',
        retrieval_reasoning_effort='low',
    )

    return Agent(
        client=client,
        instructions=_INSTRUCTIONS,
        name='contoso-hr-agent',
        description='Contoso HR specialist: policies, benefits, PTO, onboarding, performance.',
        context_providers=[kb_context],
    )
