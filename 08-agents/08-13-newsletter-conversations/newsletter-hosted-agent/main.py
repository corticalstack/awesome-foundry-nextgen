import os

from agent_framework import Agent
from agent_framework_foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential


def main():
    chat_client = FoundryChatClient(
        project_endpoint=os.getenv("FOUNDRY_PROJECT_ENDPOINT") or os.getenv("PROJECT_ENDPOINT"),
        # "<connection-name>/<deployment>": Foundry resolves the model through the
        # project's APIM connection, as in 08-12.
        model=os.environ["CHAT_MODEL"],
        credential=DefaultAzureCredential(),
        allow_preview=True,
    )

    agent = Agent(
        chat_client,
        name="newsletter-hosted-agent",
        id="newsletter-hosted-agent",
        instructions=(
            "You answer questions about one edition of the Contoso Daily Brief newsletter. "
            "The edition is the first message of the conversation. Answer only from that edition, "
            "and give the id of each article you use in square brackets."
        ),
    )

    # The host serves the Responses protocol. For each request it rebuilds the stored
    # conversation, so the edition placed there as the first item reaches the model.
    ResponsesHostServer(agent).run()


if __name__ == "__main__":
    main()
