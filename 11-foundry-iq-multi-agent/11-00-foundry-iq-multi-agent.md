# Foundry IQ multi-agent

This lab demonstrates a **router + specialist multi-agent system** built on Azure AI
Foundry. A lightweight orchestrator classifies each user query into one of three
domains (HR, Marketing, Products) and routes it to the matching specialist agent,
which answers from its own Foundry IQ Knowledge Base. The Microsoft Agent Framework
`WorkflowBuilder` provides the switch-case routing graph; each agent is grounded on
its KB via `AzureAISearchContextProvider`.

The lab also illustrates the **1:N multi-project pattern**: instead of provisioning a
new Foundry account, it adds a new `contoso-project` to the existing shared
`aif-spoke-multi-{suffix}` account from the multi-project deployment, demonstrating how a complete workload
(agents + KBs + dedicated search service) attaches to existing infrastructure.

## Notebooks

| Notebook | Purpose |
|----------|---------|
| [`11-01-deploy-setup.ipynb`](11-01-deploy-setup.ipynb) | Deploys [`main.bicep`](main.bicep) into the existing `rg-foundry-multi-{suffix}` resource group. Adds a Standard-SKU Azure AI Search service, the `contoso-project`, an APIM connection on the project, and RBAC. Creates a dedicated `foundry-gateway-contoso` APIM subscription for traffic isolation and writes all `CONTOSO_*` env vars to `.env`. |
| [`11-02-index-and-ingest.ipynb`](11-02-index-and-ingest.ipynb) | Creates three Azure AI Search indexes (`contoso-hr`, `contoso-marketing`, `contoso-products`) with semantic configuration and uploads 24 Contoso Corporation sample documents (8 per domain) from [`sample_data/`](sample_data). |
| [`11-03-knowledge-base-setup.ipynb`](11-03-knowledge-base-setup.ipynb) | Builds the Foundry IQ stack on top of the indexes: three Knowledge Sources → three Knowledge Bases (`answerSynthesis` / low reasoning effort) → three `RemoteTool` MCP connections on `contoso-project`. Validates each KB with a representative query. |
| [`11-04-multi-agent-setup.ipynb`](11-04-multi-agent-setup.ipynb) | Instantiates the four agents (orchestrator + HR / Marketing / Products specialists) defined in [`agents/`](agents), builds the `WorkflowBuilder` routing graph, then validates that each specialist returns a grounded answer and that routing sends queries to the correct specialist. |
| [`11-05-multi-agent-queries.ipynb`](11-05-multi-agent-queries.ipynb) | Demonstrates end-to-end routing over five representative queries (HR, Marketing, Products, ambiguous-HR, out-of-scope) using an `ask()` helper that does explicit classify-then-answer with exponential backoff on rate limits. |

## Run order

```
Multi-project deployment complete (aif-spoke-multi-{suffix}, MULTI_ACCOUNT in .env)
  ↓
11-01-deploy-setup          ← provision contoso-* resources, write .env
11-02-index-and-ingest      ← create three search indexes, upload sample docs
11-03-knowledge-base-setup  ← KS + KB + MCP connections
11-04-multi-agent-setup     ← instantiate agents + workflow + validate routing
11-05-multi-agent-queries   ← end-to-end demo
```

## Architecture

```
aif-spoke-multi-{suffix}     (existing shared AI Foundry account, from the multi-project deployment)
  └── contoso-project         (new - added by this lab)
        ├── contoso-apim-connection   → APIM gateway → gpt-4.1-mini
        ├── contoso-mcp-hr            → Foundry IQ KB MCP endpoint
        ├── contoso-mcp-marketing     → Foundry IQ KB MCP endpoint
        └── contoso-mcp-products      → Foundry IQ KB MCP endpoint

contoso-search-{suffix}      (new Azure AI Search service, Standard SKU)
  ├── contoso-hr index
  │     └── contoso-ks-hr ──→ contoso-kb-hr (answerSynthesis)
  ├── contoso-marketing index
  │     └── contoso-ks-marketing ──→ contoso-kb-marketing (answerSynthesis)
  └── contoso-products index
        └── contoso-ks-products ──→ contoso-kb-products (answerSynthesis)
```

The routing graph at runtime:

```
                       user query
                            │
                            ▼
                     orchestrator             (classifies → HR | MARKETING | PRODUCTS)
                            │
              ┌─────────────┼──────────────┐
              ▼             ▼              ▼
          hr_agent    marketing_agent   products_agent  (Default)
              │             │              │
              ▼             ▼              ▼
        contoso-kb-hr  contoso-kb-mkt  contoso-kb-products
```

All chat-model inference (orchestrator classification, specialist answers, KB
answer-synthesis) routes through the APIM gateway. Embeddings (`text-embedding-3-large`)
are called by the search service's integrated vectorizer at query time, also via APIM.
No model deployments exist locally on `aif-spoke-multi-{suffix}`.

## Background concepts

### Microsoft Agent Framework

The [Microsoft Agent Framework](https://learn.microsoft.com/en-us/agent-framework/)
(successor to Semantic Kernel + AutoGen) provides the `Agent` abstraction, the
`FoundryChatClient` chat client, and the `WorkflowBuilder` orchestration graph. This
lab uses:

- `Agent` - local agent wrapping a chat client + instructions + context providers
- `FoundryChatClient` - calls the project's Responses API; model is named as
  `"<connection-name>/<deployment>"` so Foundry resolves through the named APIM
  connection (e.g. `contoso-apim-connection/gpt-4.1-mini`)
- `AzureAISearchContextProvider` - injects KB-grounded context into each agent turn
  in `'agentic'` mode against a named Foundry IQ Knowledge Base
- `WorkflowBuilder` with `add_switch_case_edge_group` - runs the orchestrator, then
  routes by `Case`/`Default` conditions over the classifier's text

### Foundry IQ in answer-synthesis mode

The three Knowledge Bases use `output_mode=ANSWER_SYNTHESIS` with `low` reasoning
effort. Each KB call decomposes the question, retrieves from its dedicated index, then
runs **one LLM pass** through `gpt-4.1-mini` (via APIM) to produce a grounded
natural-language answer with citations. Standard SKU search is required for this
mode - hence the dedicated `contoso-search-{suffix}` service (the Basic-SKU
`iq-search-{suffix}` from Foundry IQ cannot be used).

### 1:N multi-project pattern

This lab is a worked example of the pattern introduced by the multi-project deployment: a single AI Foundry
account hosts multiple projects, each owning its own workload-specific resources
(connections, MCP tools, RBAC scopes). The Bicep [`main.bicep`](main.bicep) references
the existing account with `existing = { name: existingAccountName }` and adds the
project as a child resource - no new account is created. Inference is isolated by a
dedicated APIM subscription (`foundry-gateway-contoso`) so the Contoso workload has its
own rate-limit bucket.

## Environment variables

This lab reads these from `.env`:

| Variable | Source | Description |
|----------|--------|-------------|
| `MULTI_ACCOUNT` | Multi-project deployment | Existing shared Foundry account (`aif-spoke-multi-{suffix}`) |
| `GATEWAY_URL` | Multi-project deployment | APIM gateway URL (`https://apim-foundry-{sfx}.azure-api.net/openai`) |
| `ALPHA_GATEWAY_KEY` | Multi-project deployment | Bootstrap APIM subscription key for initial Bicep deploy |
| `CHAT_MODEL` | Multi-project deployment | Chat model name (`gpt-4.1-mini`) |
| `CONTOSO_FOUNDRY_PROJECT` | Deploy setup | New project name (`contoso-project`) |
| `CONTOSO_FOUNDRY_PROJECT_ENDPOINT` | Deploy setup | Project endpoint URL |
| `CONTOSO_APIM_CONNECTION` | Deploy setup | APIM connection name on the project |
| `CONTOSO_SEARCH_ENDPOINT` | Deploy setup | Azure AI Search endpoint |
| `CONTOSO_SEARCH_NAME` | Deploy setup | Search service name |
| `CONTOSO_GATEWAY_KEY` | Deploy setup | Dedicated APIM subscription key for Contoso |
| `CONTOSO_RESOURCE_GROUP` | Deploy setup | Multi-spoke resource group |
| `AZURE_SUBSCRIPTION_ID` | Deploy setup | Subscription ID |

## Prerequisites

1. **Multi-project deployment complete** - `aif-spoke-multi-{suffix}` and APIM gateway must exist with
   `gpt-4.1-mini` and `text-embedding-3-large` deployments. `.env` must contain
   `MULTI_ACCOUNT`, `GATEWAY_URL`, `ALPHA_GATEWAY_KEY`, `CHAT_MODEL`.
2. **Python environment** - run `uv sync` from the repo root; select the `.venv` kernel.
3. **Azure CLI** - run `az login` before executing cells.

---

[Next: Deploy the Contoso project →](11-01-deploy-setup.ipynb)
