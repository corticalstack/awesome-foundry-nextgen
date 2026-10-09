# Foundry IQ deep research

This lab demonstrates **deep research** over the `arxiv-nlp` knowledge base using
`gpt-5.6-sol`, deployed as `deep-research`. It replaced `o3-deep-research`, which retires on
2026-11-19. The model runs an **agentic loop**, calling `search` and `fetch` tools backed by the
Foundry IQ knowledge base from Foundry IQ, then synthesises a comprehensive cited report
using `gpt-4.1-mini`.

The lab reuses the AI Search index and Foundry IQ knowledge bases created in Foundry IQ
(`iq-search-{suffix}` / `arxiv-nlp-kb`). No new search infrastructure is deployed.

## Notebooks

| Notebook | Purpose |
|----------|---------|
| [`12-01-deploy-deep-research-backend.ipynb`](12-01-deploy-deep-research-backend.ipynb) | **Optional.** Checks if the Norway East `deep-research` deployment and its APIM routing already exist (from the core gateway deployment). If not, deploys `main.bicep` to add them. Writes `DR_*` env vars to `.env`. Skip if the core gateway deployment has already been run from this version of the repo. |
| [`12-02-deep-research-loop.ipynb`](12-02-deep-research-loop.ipynb) | Runs the agentic deep research loop over the `arxiv-nlp-kb` Foundry IQ knowledge base. Executes four representative NLP-domain research queries and displays cited reports with tool-call telemetry. |

## Run order

```
Foundry IQ complete (iq-search-{suffix}, arxiv-nlp-kb, IQ_* env vars in .env)
  ↓
12-01-deploy-deep-research-backend  ← optional if the deep-research backend already exists
  ↓
12-02-deep-research-loop  ← main lab notebook
```

## Architecture

```
                          ┌─────────────────────────────────┐
                          │  12-02-deep-research-loop        │
                          │                                  │
                          │  deep-research (agentic loop)    │
                          │    ├─ search tool ──────────────►│──► Foundry IQ KB
                          │    └─ fetch tool  ──────────────►│──► Foundry IQ KB
                          │                                  │
                          │  gpt-4.1-mini (synthesis)        │
                          └──────────────┬──────────────────┘
                                         │
                              ┌──────────▼──────────┐
                              │   APIM Gateway       │
                              │  apim-foundry-{sfx}  │
                              └──────┬──────┬────────┘
                                     │      │
                     ┌───────────────▼┐   ┌▼───────────────────┐
                     │  aif-core-{sfx} │   │ aif-research-{sfx}  │
                     │  (East US 2)   │   │ (Norway East)        │
                     │  gpt-4.1-mini  │   │ deep-research        │
                     └────────────────┘   └─────────────────────┘
                                                    ▲
                                   routes when the model is
                                         "deep-research"

                          ┌──────────────────────────────┐
                          │  iq-search-{suffix}          │
                          │  (from Foundry IQ)               │
                          │  arxiv-nlp index             │
                          │    └─ arxiv-nlp-ks  ─────────┤
                          │         └─ arxiv-nlp-kb       │
                          └──────────────────────────────┘
```

All model calls route through the APIM gateway. The gateway sends requests for the
`deep-research` deployment to the Norway East research hub backend (`openai-research`),
while all other model requests go to the primary core (`openai`). Chat Completions requests
match on the URL (`/deployments/deep-research/chat/completions`). Responses requests carry the
model in the body, so a policy on the `responses` operation reads `model` and switches the
backend when it is `deep-research`.

## Background concepts

### The deep research model

`gpt-5.6-sol` is the strongest-reasoning tier of the GPT-5.6 family and the model the
[retirement schedule](https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/model-retirement-schedule)
names as the replacement for `o3-deep-research`. The lab deploys it as `deep-research`, a
deployment named for its role, so the APIM routing and `DR_MODEL` stay the same when the model
behind it changes. In the loop, it:

- Plans a research strategy and executes it iteratively
- Calls tools (`search`, `fetch`) to gather evidence
- Reasons over gathered information before formulating answers
- Produces comprehensive, citation-rich reports

The research hub sits in **Norway East** because `o3-deep-research` was only offered there.
`gpt-5.6-sol` is offered there too, so the hub stayed. The APIM routing (deployed by the core
gateway deployment) forwards requests for `deep-research` to the Norway East
`aif-research-{suffix}` account.

### Agentic loop

The agentic loop uses the **Responses API with function calling**. `gpt-5.6-sol` rejects
`reasoning_effort` together with function tools on Chat Completions ("To use function tools,
use /v1/responses or set reasoning_effort to 'none'"), so a Chat Completions loop would run
the model with no reasoning. The loop:

1. Sends the research query to `deep-research` with tool definitions and `reasoning.effort`
2. Model responds with one or more `function_call` items (`search` or `fetch`)
3. Client executes every call against Foundry IQ and sends the `function_call_output` items
   back with `previous_response_id`, so the service keeps the reasoning between turns
4. Repeat until the model returns a response with no function calls
5. Pass the model's findings to `gpt-4.1-mini` for final synthesis and formatting

```
query ──► deep-research ──► function_call ──► search()/fetch()
               ▲                                        │
               └──────── function_call_output ◄─────────┘
               │
               └── no function_call ──► gpt-4.1-mini ──► final report
```

### Foundry IQ knowledge base

The `arxiv-nlp-kb` knowledge base (created in Foundry IQ) wraps the `arxiv-nlp` Azure AI
Search index. When queried via the Foundry IQ retrieve API, it:

- Decomposes the query into focused sub-queries
- Fans out across the search index using hybrid (BM25 + vector) retrieval
- Semantically reranks results
- Returns cited chunks to the caller

This lab queries the KB directly via HTTP (the same retrieve endpoint used by Foundry
agents) - no agent is involved on the Foundry side.

## Environment variables

This lab reads these from `.env`:

| Variable | Source | Description |
|----------|--------|-------------|
| `GATEWAY_URL` | Core gateway | APIM gateway URL (`https://apim-foundry-{sfx}.azure-api.net/openai`) |
| `CHAT_MODEL` | Core gateway | Chat model name (`gpt-4.1-mini`) |
| `IQ_SEARCH_ENDPOINT` | Foundry IQ | Foundry IQ search endpoint |
| `IQ_GATEWAY_KEY` | Foundry IQ | APIM subscription key for IQ workload |
| `DR_MODEL` | Deploy deep research backend | Deep research deployment name (`deep-research`) |
| `DR_GATEWAY_KEY` | Deploy deep research backend | APIM subscription key for deep research |

## Prerequisites

1. **Core gateway deployed** - hub, APIM gateway, and Norway East research hub deployed.
   `.env` must contain `GATEWAY_URL`, `CHAT_MODEL`.
2. **Foundry IQ complete** - `iq-search-{suffix}` and `arxiv-nlp-kb` must exist.
   `.env` must contain `IQ_SEARCH_ENDPOINT`, `IQ_GATEWAY_KEY`.
3. **Python environment** - run `uv sync` from the repo root; select the `.venv` kernel.
4. **Azure CLI** - run `az login` before executing cells.

---

[Next: Deploy the deep research backend →](12-01-deploy-deep-research-backend.ipynb)
