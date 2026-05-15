# 08-05b – Contoso Private Banking MCP Server (intent-level design)

A self-hosted **6-tool MCP server** on Azure Functions that supports the morning workflow of a Swiss private-banking relationship manager. The headline tool, [`cpb_prepare_client_briefing`](private-banking-mcp/function_app.py), returns a fully-stitched briefing for a client meeting — portfolio summary, IPS drift, recent activity, CRM flags, relevant research, and next-best-actions — in **one** call.

```
assets/contoso-private-banking-dataset/   ←── synthetic Contoso Private Investments KB
    │   5 clients · 5 IPS · 45 portfolio positions · 24 transactions
    │   9 CRM events · 14 instruments · 15 corpus documents
    ▼
private-banking-mcp/                       ←── Azure Functions app (Flex Consumption, Python)
  function_app.py            6 mcpToolTrigger wrappers
  kb.py                      Intent-level business logic + drift math + citations
  host.json                  Standard GA extension bundle [4, 5)
  data/                      Bundled KB (copied at build time)
          │
          ▼ SSE endpoint: https://<func-app>.azurewebsites.net/runtime/webhooks/mcp/sse
          │
  PromptAgentDefinition       ←── tools=[{type:'mcp', require_approval:'never'}]
          │
          ▼ project_client.agents.create_version on project-admin-{suffix}
  Foundry Agent (versioned)   ←── aria-rm-briefing-agent v1, v2, …
```

## What it teaches

This lab is the **intent-level counterpoint** to the existing [08-05 Contoso PMO MCP](../08-05-contoso-pmo-mcp/) lab. They sit on the same Azure plumbing — Functions Flex Consumption, `mcpToolTrigger`, the Foundry agent surface — and now both use the **versioned-agent API** (`PromptAgentDefinition` + `create_version` + Responses API for invocation). What differs is the tool design: intent-level (6 verbs) here vs endpoint-level CRUD (37 tools) in 08-05. The contrast is the lesson.

| | [08-05 PMO MCP](../08-05-contoso-pmo-mcp/) | **08-05b Private Banking MCP (this lab)** |
|---|---|---|
| Tool count | 37 | 6 |
| Style | Endpoint-style (CRUD across projects, people, meetings, tasks, documents, risks, distribution lists) | Intent-style (workflows the user actually runs) |
| Headline | `create_project`, `get_project`, `list_projects`, `update_project`, ... | `cpb_prepare_client_briefing`, `cpb_analyze_portfolio_drift`, `cpb_find_relevant_research`, ... |
| Joins / synthesis | Pushed to the agent (it must compose `get_project_context` → `list_tasks` → `list_documents` → ...) | Done server-side; one call returns the full brief with citations |
| ID surface | IDs everywhere (`person-001`, `proj-001`, `mtg-001`) | `response_format='concise'` (default) returns names/dates/amounts; `'detailed'` adds IDs for chained calls |
| Pagination | None on most `list_*` tools | `page` + `page_size` on `cpb_run_query`; truncation flag on every list-y tool |
| Errors | `{'error': '...'}` strings | `{code, message, next_steps}` — every error tells the agent what to try next |
| Escape hatch | Implicit (compose lower-level tools) | Explicit (`cpb_run_query`) — common path is one verb, long tail is composable |
| Eval set | Manual smoke tests | [`workflow_evals.jsonl`](tests/workflow_evals.jsonl) of real RM journeys + automated [`test_workflow_evals.py`](tests/test_workflow_evals.py) runner |

The pedagogical contrast is the lesson. Run both labs in sequence and the design point lands without needing a slide.

## Why this matters (the deeper principle)

A traditional REST contract is between two deterministic systems — the schema *is* the contract. An MCP tool is a contract between a deterministic backend and a **non-deterministic planner**. The contract surface is now four-dimensional: **name, description, response shape, failure modes** — because all four steer the planner. Wrapping REST 1:1 ports the schema and discards the other three. That's why endpoint-style MCPs underperform.

This lab implements the seven principles from Anthropic's [Writing tools for AI agents](https://www.anthropic.com/engineering/writing-tools-for-agents) post:

| # | Principle | How this lab implements it |
|---|---|---|
| 1 | Intent-level verbs | 6 tools that match what an RM actually does in their day |
| 2 | Small registry + escape hatch | 5 intent tools for the common path, [`cpb_run_query`](private-banking-mcp/function_app.py) for the long tail |
| 3 | Namespace tools | All tools prefixed `cpb_*` (Contoso Private Banking) — overlap with other servers obvious to the planner |
| 4 | Human-readable fields by default | `response_format` enum: `'concise'` (default) returns names/dates/money; `'detailed'` adds IDs for chained calls |
| 5 | Pagination + sensible truncation | `cpb_find_relevant_research` defaults `max_results=5` with `truncated`/`more_with` hints; `cpb_run_query` defaults `page_size=20` |
| 6 | Actionable error messages | Every error includes `code`, `message`, and `next_steps` — what should the agent try next |
| 7 | Evals on real workflows | [`tests/workflow_evals.jsonl`](tests/workflow_evals.jsonl) — natural RM requests, asserted tool selection + response fields |

## The tool surface

| Tool | Intent | When to use |
|---|---|---|
| [`cpb_prepare_client_briefing`](private-banking-mcp/function_app.py) | The headline — full meeting brief | Default for any "prepare for the X meeting" / "what should I know about Y" query |
| [`cpb_get_client_context`](private-banking-mcp/function_app.py) | Identity + IPS without portfolio synthesis | When only basics are needed (RM email, base currency, segment) |
| [`cpb_analyze_portfolio_drift`](private-banking-mcp/function_app.py) | Drift-only deep dive | When user explicitly asks about drift / rebalancing |
| [`cpb_find_relevant_research`](private-banking-mcp/function_app.py) | Search research / commentary / regulatory | Filterable by client, ISIN, free-text query |
| [`cpb_summarize_recent_activity`](private-banking-mcp/function_app.py) | Transactions grouped by intent | When user asks "what's been happening" / wants to explain recent moves |
| [`cpb_run_query`](private-banking-mcp/function_app.py) | Read-only escape hatch | Long-tail / unusual queries the intent tools don't cover |

## Synthetic Contoso Private Investments dataset

Five fictional clients spanning the standard Swiss private-bank persona set (per the [private-banking-workshop-agenda](../../docs/private-banking-workshop-agenda.md) §12 build list):

| Client | Segment | Base | AUM CHF | Notable | Drift / flag |
|---|---|---|---|---|---|
| `cli-001` Berger Family Trust | UHNW Multi-Generation | CHF | 87.5M | ESG mandate, philanthropic | Equities +6.5pp over band (material breach) |
| `cli-002` Eichmann Foundation | Philanthropic Foundation | CHF | 42.3M | Income mandate, conservative | New chair starts 2026-06-01; tightening exclusions |
| `cli-003` Lindemann Family Office | Single-Family Office | EUR | 156.8M | Growth + alts, PE permitted | PE sleeve at 28% (target 25%) — secondary-market window open |
| `cli-004` Müller Entrepreneurial Wealth | Post-Liquidity Entrepreneur | USD | 68.2M | Concentrated legacy stake (locked) | Müller Holding AG at 12.18% > 10% cap (concentration flag) |
| `cli-005` Riedi Pension Plan | Institutional Pension | CHF | 234.5M | LDI mandate, FI-heavy | Largely in-line; FINMA Circular 2024/2 packs due |

All ISINs use the documentation prefix `XX0000…`; all personas are fictional. See [open-source readiness checklist](../../docs/private-banking-workshop-agenda.md#15-open-source-readiness).

## Getting started

### 1. Install dependencies

```bash
uv sync
```

### 2. Authenticate

```bash
az login
```

### 3. Configure `.env`

| Variable | Description |
|---|---|
| `CHAT_MODEL` | Model deployment name on the hub account (e.g. `gpt-4.1-mini`) |

Optional overrides:

| Variable | Default |
|---|---|
| `AZURE_SUBSCRIPTION_ID` | active `az` subscription |
| `PRIVATE_BANKING_MCP_RESOURCE_GROUP` | `rg-foundry-private-banking-mcp` |
| `PRIVATE_BANKING_MCP_LOCATION` | `swedencentral` |
| `PRIVATE_BANKING_FUNC_APP_NAME` | `func-private-banking-mcp-{md5(sub-id+rg)[:6]}` |

### 4. Run the notebooks

| Order | Notebook |
|---|---|
| 1 | [`08-05b-01-private-banking-agent-setup.ipynb`](08-05b-01-private-banking-agent-setup.ipynb) — deploy MCP server + create agent |
| 2 | [`08-05b-02-private-banking-agent-queries.ipynb`](08-05b-02-private-banking-agent-queries.ipynb) — interactive demos including side-by-side intent vs endpoint contrast |

### 5. Run the local test suite

No Azure credentials required — these tests run against the bundled fixture data.

```bash
uv run pytest 08-agents/08-05b-contoso-private-banking-mcp/tests/ -v
```

Expected: **58 passed** (48 unit tests + 10 workflow evals).

## Verification

| Step | Expected result |
|---|---|
| Imports & config | Prints `Project endpoint`, `Function app`, `Agent name`, `Chat model` |
| Phase 1 (build) | Prints sizes for `function_app.py` and `kb.py`; reports JSON files bundled |
| Phase 2 (deploy) | `✓` lines for resource group, storage, function app, all storage roles, and `DATA_DIR=data` |
| Phase 3 (package) | Prints `Zip archive` size and `✓ code deployed` |
| Phase 4 (key) | Prints `Function base URL` and `MCP SSE endpoint` |
| Phase 5 (agent) | Prints `Created agent 'aria-rm-briefing-agent'` (or `Reusing existing agent ...` on re-run) |

## Notes

- **Read-only by design.** The demo workflow is read-and-synthesise. Write tools (e.g. `cpb_propose_trade` with `require_approval`) would be the natural next addition for HITL — see [08-08 human-in-the-loop](../08-08-human-in-the-loop/) for the pattern.
- **No API keys to the model.** The agent talks to the admin project via `DefaultAzureCredential`. The only `code=` query parameter is on the MCP SSE URL itself (the `mcp_extension` Azure Functions system key) which authenticates the **agent → MCP server** path.
- **Standard GA extension bundle.** Same `Microsoft.Azure.Functions.ExtensionBundle [4.0.0, 5.0.0)` as 08-05 — the `mcpToolTrigger` binding is GA, no preview bundle needed.
- **Open-source-safe by construction.** All ISINs prefixed `XX0000…`, all client/manager names fictional, no real FINMA verbatim text, internal codename `Project Edelweiss` per workshop convention.

## References

- Anthropic, [Writing tools for AI agents](https://www.anthropic.com/engineering/writing-tools-for-agents) — the design checklist this lab implements
- [Private Banking Workshop Agenda](../../docs/private-banking-workshop-agenda.md) — workshop module 4 protagonist (Aria the wealth-team RM assistant)
- [08-05 Contoso PMO MCP](../08-05-contoso-pmo-mcp/) — the endpoint-style counterpart (37 CRUD tools)
- [08-08 Human-in-the-loop](../08-08-human-in-the-loop/) — pattern for adding write tools with `require_approval`
