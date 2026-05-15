# Lab 12: Foundry IQ Deep Research

This lab demonstrates **deep research** over the `arxiv-nlp` knowledge base using
`o3-deep-research` — OpenAI's reasoning model designed for multi-step research tasks.
The model runs an **agentic loop**, calling `search` and `fetch` tools backed by the
Foundry IQ knowledge base from Lab 10, then synthesises a comprehensive cited report
using `gpt-4.1-mini`.

The lab reuses the AI Search index and Foundry IQ knowledge bases created in Lab 10
(`iq-search-{suffix}` / `arxiv-nlp-kb`). No new search infrastructure is deployed.

## Notebooks

| Notebook | Purpose |
|----------|---------|
| [`12-01-deploy-o3-backend.ipynb`](12-01-deploy-o3-backend.ipynb) | **Optional.** Checks if the Norway East `o3-deep-research` APIM backend already exists (from Lab 05-02). If not, deploys `main.bicep` to add it. Writes `DR_*` env vars to `.env`. Skip if Lab 05-02 has already been run. |
| [`12-02-deep-research-loop.ipynb`](12-02-deep-research-loop.ipynb) | Runs the agentic deep research loop over the `arxiv-nlp-kb` Foundry IQ knowledge base. Executes four representative NLP-domain research queries and displays cited reports with tool-call telemetry. |

## Run order

```
Lab 10 complete (iq-search-{suffix}, arxiv-nlp-kb, IQ_* env vars in .env)
  ↓
12-01-deploy-o3-backend   ← optional if o3-deep-research APIM backend already exists
  ↓
12-02-deep-research-loop  ← main lab notebook
```

## Architecture

```
                          ┌─────────────────────────────────┐
                          │  12-02-deep-research-loop        │
                          │                                  │
                          │  o3-deep-research (agentic loop) │
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
                     │  gpt-4.1-mini  │   │ o3-deep-research     │
                     └────────────────┘   └─────────────────────┘
                                                    ▲
                                   routes when deployment-id =
                                       "o3-deep-research"

                          ┌──────────────────────────────┐
                          │  iq-search-{suffix}          │
                          │  (from Lab 10)               │
                          │  arxiv-nlp index             │
                          │    └─ arxiv-nlp-ks  ─────────┤
                          │         └─ arxiv-nlp-kb       │
                          └──────────────────────────────┘
```

All model calls route through the APIM gateway. The gateway policy routes requests
for `o3-deep-research` to the Norway East research hub backend (`openai-research`),
while all other model requests go to the primary core (`openai`).

## Background concepts

### o3-deep-research

`o3-deep-research` is an OpenAI reasoning model optimised for multi-step research
tasks. Unlike standard chat models that respond in a single pass, it:

- Plans a research strategy and executes it iteratively
- Calls tools (`search`, `fetch`) to gather evidence
- Reasons over gathered information before formulating answers
- Produces comprehensive, citation-rich reports

The model is available only in **Norway East**. The APIM routing policy in
`aif-core-{suffix}` (deployed by Lab 05-02) forwards requests to the Norway East
`aif-research-{suffix}` account when the `deployment-id` path parameter is
`o3-deep-research`.

### Agentic loop

The agentic loop uses the **Chat Completions API with function calling** — the same
interface as standard `gpt-4.1-mini` calls. The loop:

1. Sends the research query to `o3-deep-research` with tool definitions
2. Model responds with one or more tool calls (`search` or `fetch`)
3. Client executes the tool against Foundry IQ, appends the result to the message chain
4. Repeat until the model returns a response with no tool calls
5. Pass the model's reasoning to `gpt-4.1-mini` for final synthesis and formatting

```
query ──► o3-deep-research ──► tool_calls ──► search()/fetch()
                  ▲                                    │
                  └─────────── tool_results ◄──────────┘
                  │
                  └── no tool_calls ──► gpt-4.1-mini ──► final report
```

### Foundry IQ knowledge base

The `arxiv-nlp-kb` knowledge base (created in Lab 10) wraps the `arxiv-nlp` Azure AI
Search index. When queried via the Foundry IQ retrieve API, it:

- Decomposes the query into focused sub-queries
- Fans out across the search index using hybrid (BM25 + vector) retrieval
- Semantically reranks results
- Returns cited chunks to the caller

Lab 12 queries the KB directly via HTTP (the same retrieve endpoint used by Foundry
agents) — no agent is involved on the Foundry side.

## Environment variables

Lab 12 reads these from `.env`:

| Variable | Source | Description |
|----------|--------|-------------|
| `GATEWAY_URL` | Lab 05-02 | APIM gateway URL (`https://apim-foundry-{sfx}.azure-api.net/openai`) |
| `CHAT_MODEL` | Lab 05-02 | Chat model name (`gpt-4.1-mini`) |
| `IQ_SEARCH_ENDPOINT` | Lab 10-01 | Foundry IQ search endpoint |
| `IQ_GATEWAY_KEY` | Lab 10-01 | APIM subscription key for IQ workload |
| `DR_MODEL` | Lab 12-01 | Deep research model name (`o3-deep-research`) |
| `DR_GATEWAY_KEY` | Lab 12-01 | APIM subscription key for deep research |

## Prerequisites

1. **Lab 05-02 complete** — hub, APIM gateway, and Norway East research hub deployed.
   `.env` must contain `GATEWAY_URL`, `CHAT_MODEL`.
2. **Lab 10 complete** — `iq-search-{suffix}` and `arxiv-nlp-kb` must exist.
   `.env` must contain `IQ_SEARCH_ENDPOINT`, `IQ_GATEWAY_KEY`.
3. **Python environment** — run `uv sync` from the repo root; select the `.venv` kernel.
4. **Azure CLI** — run `az login` before executing cells.
