# Hosted agents

This lab deploys a containerised **Microsoft Agent Framework** agent, hosted via Capability Host (Azure Container Apps),
connected to the APIM gateway for model inference.

The agent - `contoso-wealth-expert-agent` - answers two kinds of questions:

- General wealth and asset management concepts (terms like Sharpe ratio, IPS,
  discretionary vs advisory mandates, UCITS structures).
- Contoso Wealth's own service tiers, mandate types, and fund families.

There are no tools, no vector store, no Foundry IQ. **The agent's "knowledge" of
Contoso products is literally pasted into the system prompt** - see the `instructions`
block in [`contoso-wealth-agent/main.py`](contoso-wealth-agent/main.py).

This is the same prompt-stuffing pattern as
[`contoso-bank-agent`](../../13-guardrails/13-02-create-bank-agent.ipynb).
On every request, the model receives the system prompt (including the bulleted
product list) plus the user's question, and synthesises an answer from that combined
context. No retrieval step, no embedding lookup, no source documents.

## When prompt stuffing is enough

- The corpus is small and stable - a dozen products with one-line descriptions
  comfortably fit in the prompt.
- No freshness requirement - service-tier names and minimums don't change between
  Tuesday and Wednesday.
- No need for source citations - nobody is auditing the agent against a document.
- Cost per call is negligible - the prompt is only a few hundred tokens.

## When prompt stuffing stops being enough

The pattern fails the moment the audience asks any of:

| Question | Why prompt stuffing fails |
|---|---|
| "What are the top 10 holdings in Contoso Sustainable Income?" | Detail per fund explodes - 50 funds × 10 lines each = unwieldy prompt |
| "What's the YTD performance of Contoso Active Equity Europe?" | Numbers change daily; static prompt goes stale instantly |
| "Cite the page in the factsheet that says that." | No source documents exist to cite |
| "What did our weekly market commentary say about energy last Friday?" | Ongoing content stream - can't sit in a prompt at all |

The next architectural step is **grounding** the agent over a knowledge base and giving it **tools** via MCP. Both move the knowledge out of the prompt and into systems built to handle volume, freshness, and citation.

## Files

| File | Purpose |
|---|---|
| [`deploy-hosted-agent.ipynb`](deploy-hosted-agent.ipynb) | Provisions ACR, builds the agent container, deploys it via Capability Host, registers it with the Foundry project, runs two test prompts |
| [`main.bicep`](main.bicep) | Deploys the Azure Container Registry into the existing Spoke Alpha resource group and grants AcrPull to the project's managed identity |
| [`contoso-wealth-agent/main.py`](contoso-wealth-agent/main.py) | The agent code - a `ChatAgent` with the prompt-stuffed product list as `instructions` |
| [`contoso-wealth-agent/Dockerfile`](contoso-wealth-agent/Dockerfile) | Container image definition |
| [`contoso-wealth-agent/requirements.txt`](contoso-wealth-agent/requirements.txt) | Python dependencies |

---

[Next: Deploy a hosted agent →](deploy-hosted-agent.ipynb)
