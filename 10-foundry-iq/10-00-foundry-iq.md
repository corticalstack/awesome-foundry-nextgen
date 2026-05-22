# Foundry IQ

This lab demonstrates how to build a knowledge retrieval system using **Foundry IQ** -
Azure AI Foundry's managed knowledge base solution - on top of an existing multi-project
Foundry account. It covers the full stack from Azure resource provisioning through to
an agent answering grounded, cited questions over a corpus of 3,000 NLP research papers.

The lab reuses the shared AI Foundry account from the multi-project deployment (`aif-spoke-multi-{suffix}`)
rather than creating a new account, illustrating how the 1:N multi-project pattern
absorbs a new workload capability without additional infrastructure overhead.

## Notebooks

| Notebook | Purpose |
|----------|---------|
| `10-01-deploy-search-and-project.ipynb` | Deploys an Azure AI Search service and a new Foundry project (`iq-project`) into the existing multi-account resource group via Bicep. Creates a dedicated APIM subscription key for the IQ workload and writes all `IQ_*` env vars to `.env`. Run once before anything else. |
| `10-02-index-and-ingest.ipynb` | Creates the `arxiv-nlp` vector + semantic search index (3,072-dim HNSW, integrated vectorizer, semantic configuration, `group_ids` security field) and uploads 3,000 NLP paper abstracts with pre-computed embeddings generated via the APIM gateway. |
| `10-03-knowledge-base-setup.ipynb` | Builds the Foundry IQ object hierarchy on top of the search index: Knowledge Source → dual Knowledge Bases (minimal and low reasoning effort) → MCP connection → versioned agent. Includes inline KB validation and a security-trimming demonstration via `filterAddOn`. |
| `10-04-search-patterns.ipynb` | Demonstrates the six raw Azure AI Search retrieval patterns in isolation - BM25, vector, hybrid RRF, semantic reranker, OData-filtered, and security-trimmed - to show what the Foundry IQ agentic pipeline does under the hood. |
| `10-05-agent-iq-queries.ipynb` | Sends research queries to the versioned agent via the Responses API. The agent invokes the KB over MCP, triggering the full agentic retrieval pipeline (query decomposition → parallel sub-queries → semantic rerank → cited synthesis). Demonstrates multi-intent, temporal, cross-lingual, and out-of-scope query handling. |

## Run order

```
10-01-deploy-search-and-project   ← provision Azure resources, write .env
10-02-index-and-ingest            ← create index schema, generate embeddings, upload docs
10-03-knowledge-base-setup        ← build KB stack, create agent
10-04-search-patterns             ← optional: explore raw search primitives
10-05-agent-iq-queries            ← run agent queries end-to-end
```

`10-04-search-patterns` can be run any time after `10-02` - it is standalone and does
not depend on `10-03`.

## Architecture

The lab uses the hub/spoke model: no model deployments exist in the IQ spoke. All
embedding and LLM calls route through the APIM gateway (`GATEWAY_URL`).

```
aif-spoke-multi-{suffix}   (existing shared AI Foundry account)
  └── iq-project            (new - added by this lab)
        └── iq-apim-connection  →  APIM gateway  →  gpt-4.1-mini / text-embedding-3-large
        └── arxiv-nlp-mcp       →  Azure AI Search MCP endpoint

iq-search-{suffix}         (new Azure AI Search service, Basic SKU)
  └── arxiv-nlp index
        └── Knowledge Source  (arxiv-nlp-ks)
              └── Knowledge Base - minimal  (arxiv-nlp-kb-fast)
              └── Knowledge Base - low      (arxiv-nlp-kb)  ← MCP endpoint
```

## Background concepts

### Foundry IQ

[Foundry IQ](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/concepts/what-is-foundry-iq?view=foundry&preserve-view=true&tabs=portal)
is a managed knowledge base solution within Azure AI Foundry. It wraps Azure AI Search
with an agentic retrieval engine that performs multi-query retrieval - decomposing a
user question into focused sub-queries, fanning out across knowledge sources, and
semantically reranking the merged results before returning cited chunks to the agent.

Key properties:
- Connects to knowledge sources: Azure AI Search indexes, Blob Storage, SharePoint, OneLake
- Supports keyword, vector, and hybrid queries across sources
- Enforces document-level access control via `group_ids` field and `filterAddOn`
- Returns answers with citations for traceability
- Exposed as an MCP endpoint - agents attach it as a tool via a `RemoteTool` project connection

### Azure AI Search

Azure AI Search is the retrieval engine underneath Foundry IQ. It provides full-text
(BM25), vector (HNSW cosine), hybrid (Reciprocal Rank Fusion), and semantic reranking
in a single service. The `arxiv-nlp` index in this lab uses all four.

### Integrated vectorizer

The integrated vectorizer lets the search service embed query text at search time by
calling an embedding model via the APIM gateway - so client applications submit plain
text and the search service handles the embedding call transparently.

> **Important**: the `resource_url` passed to `AzureOpenAIVectorizerParameters` must be
> the root APIM URL **without** the `/openai` suffix (e.g.
> `https://apim-foundry-{suffix}.azure-api.net`). The search service appends
> `/openai/deployments/{model}/embeddings` itself. Passing `GATEWAY_URL` directly
> (which includes `/openai`) results in a double-path 404.

The same applies when constructing an `AzureOpenAI` SDK client: use `apim_base`
(derived as `gateway_url.removesuffix('/openai')`) as `azure_endpoint`.

---

[Next: Deploy the IQ spoke →](10-01-deploy-search-and-project.ipynb)
