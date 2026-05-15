# Agent Offline Evaluation

## Introduction

This lab demonstrates how to evaluate the quality, safety, and agent-specific behaviour of `aria-rm-briefing-agent` — the Contoso Private Investments relationship-manager briefing assistant created in [Lab 08-05b (Contoso Private Banking MCP)](../08-05b-contoso-private-banking-mcp/08-05b-00-contoso-private-banking-mcp.md). Aria exposes 6 intent-level MCP tools (`cpb_prepare_client_briefing`, `cpb_analyze_portfolio_drift`, `cpb_find_relevant_research`, …) over a synthetic banking knowledge base.

This is **offline evaluation** — run during the agent development lifecycle against a curated test dataset, giving fast, reproducible feedback while you iterate on prompts, tools, models, or retrieval strategy *before* deployment. It is the dev-time complement to **continuous (online) evaluation**, which samples live production traffic to monitor quality and safety after release. For the runtime counterpart, see [08-07-agent-live-observability](../08-07-agent-live-observability/08-07-00-agent-live-observability.md).

The lab targets the **admin project on the hub account** (`project-admin-{suffix}` on `aif-core-{suffix}`), not a spoke. Evaluators rely on a model deployment that lives natively on the agent's project's parent account — spoke accounts have zero deployments by design, so the admin project (which natively hosts the centrally-managed deployments) is the natural home for the lab's agent and grader model.

Evaluation is performed using the `azure-ai-evaluation` SDK against the Foundry portal, so results are visible in the Azure AI Foundry studio.

---

## Prerequisites

- **Hub estate deployed** (Lab 5): provides `aif-core-{suffix}` with model deployments and `project-admin-{suffix}`.
- **Lab 08-05b (Contoso Private Banking MCP) deployed**: provides the Contoso Private Banking MCP server (Azure Functions) and creates the `aria-rm-briefing-agent` on the admin project that this lab evaluates.
- **Azure CLI logged in** (`az login`): used to derive the deterministic subscription suffix and fetch the MCP system key.
- A `.env` file at the repo root with `CHAT_MODEL` set (everything else is derived).
- `uv sync` run after adding `azure-ai-evaluation>=1.16.2` to `pyproject.toml`.

### Required environment variables

| Variable | Usage |
|---|---|
| `CHAT_MODEL` | Model deployment name (e.g. `gpt-4.1-mini`) on `aif-core-{suffix}` |

Optional overrides (defaults match Lab 08-05):

| Variable | Default | Usage |
|---|---|---|
| `CONTOSO_PMO_MCP_RESOURCE_GROUP` | `rg-foundry-contoso-pmo-mcp` | Resource group hosting the MCP function app |
| `CONTOSO_PMO_FUNC_APP_NAME` | `func-contoso-pmo-mcp-{md5(sub-id + rg)[:6]}` | Override if your Lab 08-05 deployment uses a different name |

---

## Evaluation Types Covered

### Quality Evaluators
Model-graded evaluators that assess response quality dimensions:

- **Coherence** — logical flow and consistency of the response
- **Fluency** — grammatical correctness and readability
- **Relevance** — how well the response addresses the user's query
- **Groundedness** — whether the response is grounded in the provided context (reduces hallucinations)
- **Similarity** — semantic similarity to the ground truth answer

### RAI (Responsible AI) Evaluators
Safety evaluators that detect harmful content:

- **ViolenceEvaluator** — detects violent content in responses
- **HateUnfairnessEvaluator** — detects hate speech or unfair characterisations

All RAI evaluators require `evaluate_query=True` (breaking change since SDK 1.10.0).

### Agent-Specific Evaluators
Evaluators designed for agentic workflows, requiring thread and run IDs from a live agent execution:

- **IntentResolutionEvaluator** — measures whether the agent correctly identified user intent
- **ToolCallAccuracyEvaluator** — measures whether the agent called the right tools with correct arguments
- **TaskAdherenceEvaluator** — measures whether the agent's final response adheres to its assigned tasks per its system message

These evaluators use `AIAgentConverter` to transform an agent thread into the JSONL format expected by the evaluation SDK.

### Custom Evaluators
Python classes implementing domain-specific evaluation logic:

- **AnswerLengthEvaluator** — checks that responses fall within an expected character-length range
- **CitationEvaluator** — checks that responses reference plausible Contoso Private Banking corpus citations (research/, market_commentary/, regulatory/, ips/, synthetic ISINs)

---

## Notebook Sequence

| Notebook | Purpose |
|---|---|
| [08-06-01-setup-and-test-data.ipynb](08-06-01-setup-and-test-data.ipynb) | Resolve `aria-rm-briefing-agent` on the admin project (created in [08-05b-01](../08-05b-contoso-private-banking-mcp/08-05b-01-private-banking-agent-setup.ipynb)), run sample queries, capture thread/run IDs, write `test_data.jsonl` |
| [08-06-02-quality-evaluators.ipynb](08-06-02-quality-evaluators.ipynb) | Run coherence, fluency, relevance, groundedness, similarity, and RAI evaluators |
| [08-06-03-agent-evaluators.ipynb](08-06-03-agent-evaluators.ipynb) | Use `AIAgentConverter` + intent/tool/task evaluators on agent threads |
| [08-06-04-custom-evaluators.ipynb](08-06-04-custom-evaluators.ipynb) | Implement and run custom answer-length and citation evaluators |
| [08-06-05-results-and-portal.ipynb](08-06-05-results-and-portal.ipynb) | Full batch `evaluate()` call with portal logging; displays `studio_url` |

Run notebooks in order — `08-06-01` must complete before the others as it produces the `test_data.jsonl` with thread/run IDs. (Note: `08-06-03`'s `AIAgentConverter` call is currently upstream-blocked on `azure-ai-projects` 2.1.0 / `azure-ai-evaluation` 1.16.5 — the notebook is wrapped in try/except so it runs cleanly with that section skipped. See the warning in 08-06-03's intro.)

---

## Authentication Pattern

- `DefaultAzureCredential` everywhere — for `AIProjectClient`, the LLM-as-judge evaluators, and the RAI evaluators
- No API keys, no APIM hub connection — model graders talk directly to the deployment on `aif-core-{suffix}` because the admin project natively hosts it

### Known issue: Python 3.13 + azure-ai-evaluation 1.16.x

`AzureOpenAIModelConfiguration.credential` is annotated `NotRequired[Any]`, and the SDK validates it with `isinstance(value, typing.Any)`. Python 3.13 turned that from "always True" into a hard `TypeError: typing.Any cannot be used with isinstance()`. The validation runs inside every evaluator's `__init__`, so any evaluator built with a `credential=`-bearing typed dict explodes on 3.13. Verified against `azure-ai-evaluation` 1.16.5 and 1.16.7.

**Workaround applied throughout this lab:** omit `credential` from the `AzureOpenAIModelConfiguration` dict and pass it as a kwarg directly to each evaluator constructor — `CoherenceEvaluator(model_config=cfg, credential=credential)`. Every evaluator class accepts the `credential` parameter. When the SDK ships a fix, the typed-dict form can be restored.

---

## Dataset

The evaluation dataset (`sample_test_data.jsonl`) contains 5 representative RM-workflow queries against `aria-rm-briefing-agent`, spanning the agent's intent surface:

1. **Quarterly briefing** — `cpb_prepare_client_briefing` for the Berger Family Trust (UHNW Multi-Generation; ESG mandate; equities over band)
2. **Drift analysis** — `cpb_analyze_portfolio_drift` for the Lindemann Family Office at the 5pp threshold (PE sleeve over IPS band)
3. **Research lookup** — `cpb_find_relevant_research` for AI infrastructure capex relevant to Müller Entrepreneurial Wealth's holdings
4. **Recent activity summary** — `cpb_summarize_recent_activity` for the Riedi Pension Plan over 90 days
5. **Regulatory follow-ups** — `cpb_run_query` against `crm_events` for the Eichmann Foundation (FINMA Circular 2024/2 status)

Ground-truth answers and contexts are derived programmatically by invoking the same `cpb_*` kb functions locally — `ground_truth` is the kb response's `summary` and `context` includes the kb response's `data` payload (truncated to ~2500 chars). The synthetic KB lives in [`assets/contoso-private-banking-dataset/`](../../assets/contoso-private-banking-dataset/).
