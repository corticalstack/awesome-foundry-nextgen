# Foundry-hosted agent powered by the GitHub Copilot SDK

This lab deploys a containerised agent built on the [**GitHub Copilot SDK**](https://pypi.org/project/github-copilot-sdk/) and hosts it as a **Microsoft Foundry hosted agent**. Inference is served by a **Foundry-deployed `gpt-5.4-mini` model** wired in via BYOK (Bring Your Own Key; here, your own Foundry model reached through Managed Identity), so the container needs no secrets at runtime.

The notebook follows the same pattern as the rest of this repo (see [`08-03-hosted-agents`](../08-03-hosted-agents/08-03-00-hosted-agents.md)): `az deployment sub create` runs the Bicep, `az acr build` builds the container, and `AIProjectClient.agents.create_version` registers it with the project as a hosted agent.

## What this example demonstrates

- **Hosted agent runtime.** Foundry runs the container for you under the project's capability host. There is no Container App, Web App, or AKS to manage.
- **Copilot SDK as the agent loop.** `CopilotClient` owns sessions, tool-calling, streaming, and skill discovery. Your `main.py` only forwards SSE events out through Foundry's [invocations protocol](https://pypi.org/project/azure-ai-agentserver-invocations/).
- **BYOK Foundry model via Managed Identity.** When `AZURE_AI_PROJECT_ENDPOINT` + `AZURE_AI_MODEL_DEPLOYMENT_NAME` are set, the Copilot SDK routes every chat turn to your Foundry model over the project's OpenAI surface (`<project-endpoint>/openai/v1/`, token audience `ai.azure.com/.default`) - no GitHub PAT, no OpenAI key. Set only `GITHUB_TOKEN` and it falls back to the GitHub Copilot model; if both are set, the Foundry model wins.
- **Two extension surfaces:**
  - `system_prompt.md` for persona / global policy that applies to every turn.
  - `skills/<name>/SKILL.md` for task-specific procedures the model discovers on demand (an `m365-license-analytics` skill is included - it carries the analysis method, while the cost/department data is uploaded separately).
- **OTel tracing into Foundry portal.** `tracing.py` maps `SessionEvent`s to GenAI semantic-convention spans, so the Foundry Tracing tab shows the per-invocation tree with token usage and estimated cost.

## How the agentic loop works

The agent runs **two nested loops**. The reason/act/observe loop that makes it agentic does **not** live in `main.py` - it runs inside a **Copilot CLI subprocess** that the SDK spawns. `main.py` is a thin Foundry-protocol shell that boots that subprocess and forwards its event stream.

```
Foundry hosted runtime
  └── container: `python main.py`   (Dockerfile CMD, port 8088)
        └── InvocationAgentServerHost      outer loop: one HTTP POST /invocations per user turn
              └── CopilotClient  ->  spawns the Copilot CLI subprocess
                    └── inner agentic loop: model <-> tools, until the session goes idle
```

### Inner loop - the agentic part, inside the Copilot CLI

`_ensure_session` calls `_client.start()`, which boots the Copilot CLI subprocess. The CLI is the agent harness: it owns the system prompt, **skill discovery** (`skill_directories`), and **tool execution** (shell, python, file edits). Each `session.send(input)` runs one turn of the loop inside the CLI:

```
send(user_text)
  -> model call (chat)         emits assistant.message_delta (streamed text) + ASSISTANT_USAGE (tokens)
       -> model wants a tool?  emits TOOL_EXECUTION_START
            run shell/python/...
                               emits TOOL_EXECUTION_COMPLETE
       -> feed tool result back, call the model again     (repeat: reason -> act -> observe)
  -> no more tool calls, final answer
SESSION_IDLE                   the turn is complete
```

`main.py` never decides tool use or sees individual model calls - it only observes these events. `tracing.py` maps them to the span tree shown below (`TOOL_EXECUTION_*` -> `execute_tool`, `ASSISTANT_USAGE` -> `chat <model>`), so a single CSV-analytics turn shows multiple `execute_tool` spans: that span tree *is* the agentic loop made visible. The inner loop's model calls are routed to your Foundry model by `_byok_provider` (see [How the BYOK wiring works](#how-the-byok-wiring-works) below).

### Outer loop - the request and event drain, in `main.py`

Foundry calls `POST /invocations` once per user message. `handle_invoke` validates `{"input": "..."}` and returns a streaming response backed by `_stream_response`, which bridges the SDK's callback world to SSE with an `asyncio.Queue`:

- `session.on(on_event)` pushes every event onto the queue; `SESSION_IDLE` pushes a `None` sentinel and `SESSION_ERROR` pushes an exception.
- a `while True` drain loop awaits the queue and `yield`s each event as an SSE `data:` frame until the `None` sentinel arrives, then emits `event: done`.

This `while` loop is an **event-drain** loop, not the agentic loop - the reasoning has already happened inside the CLI subprocess.

### Multi-turn conversation

Two mechanisms stack, so a follow-up request starts with the full prior context already loaded:

1. **In-process singleton.** `_session` is a module global; the first request lazy-creates it and every later request reuses the same Copilot session, so the CLI subprocess keeps the message thread in memory. Turn 2 already remembers turn 1.
2. **Resume by ID for durability.** The session is keyed to `FOUNDRY_AGENT_SESSION_ID` (injected by the runtime; falls back to a generated UUID). On startup the agent tries `resume_session(session_id)` first and only falls back to `create_session`, so a restarted container resumes the same conversation by ID rather than starting cold.

> **Design assumption:** `_session` is a single global and `_session_id` is read once from the environment, so the agent assumes **one logical conversation per container instance** (the hosted runtime stamps the session id into the container's env). To fan one container across multiple concurrent users, replace the singleton with a `dict[session_id -> session]` keyed cache.

## How the BYOK wiring works

```
+---------------------------------+        +--------------------------+
| Hosted agent container          |        | Foundry AI Services      |
|                                 |        |   account                |
|  CopilotClient(provider=openai) |        |                          |
|         |  bearer = MI token    | HTTPS  |  services.ai.azure.com/  |
|         v                       |------->|  …/openai/v1/responses   |
|   azure-ai-agentserver-         |        |                          |
|   invocations                   |        |  gpt-5.4-mini deployment |
+------------+--------------------+        +--------------------------+
             | SSE
             v
   requests.post(...&agent_session_id=...)
        (helpers in the notebook)
```

Container env vars (set at registration time via `AIProjectClient.agents.create_version(..., environment_variables=...)` in the notebook):

| Variable | Source | Why |
|---|---|---|
| `AZURE_AI_PROJECT_ENDPOINT` | Not hand-configured - it is a Bicep output, read back in **Step 2** as the `PROJECT_ENDPOINT` variable and injected here at registration (the platform also auto-injects the same value as `FOUNDRY_PROJECT_ENDPOINT`) | `main.py` appends `/openai/v1/` and uses `<project-endpoint>/openai/v1/` as the Copilot SDK provider `base_url`, with token audience `ai.azure.com` |
| `AZURE_AI_MODEL_DEPLOYMENT_NAME` | Hardcoded in the `DEPLOYMENT_NAME` variable in **Step 1** (defaults to `gpt-5.4-mini`). To use a different model, change it there - the same variable also names the Bicep model deployment created in Step 2, so provisioning and BYOK routing stay in sync | Model deployment to route inference to |
| `AZURE_CLIENT_ID` | `instance_identity.client_id` from agent version metadata | Disambiguates the **AgentIdentity** managed identity inside `DefaultAzureCredential`. Each hosted-agent version has two identities in metadata: `AgentIdentityBlueprint` (a template, NOT used at runtime) and `instance_identity` = `AgentIdentity` (the actual Entra SP the container assumes). RBAC grants and `AZURE_CLIENT_ID` both target AgentIdentity |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | auto-injected by platform | OTel export target |

RBAC role grants on the AgentIdentity principal (Step 5 of the notebook):
- `AcrPull` on the ACR (image pull)
- `Foundry User` on the project (general data plane)
- `Cognitive Services OpenAI User` on the **account** scope (specifically grants `/openai/v1/responses/*` data actions)
- `Cognitive Services User` on the account (broader safety net)

## What the agent is allowed to do (permission model)

The Copilot CLI gates each tool call (shell, python, file read/write/edit) behind a permission request. In an interactive CLI a human approves each one; a hosted agent has nobody at a terminal, so `main.py` answers those requests programmatically through a single callback:

```python
on_permission_request=PermissionHandler.approve_all,   # main.py
```

`approve_all` auto-approves every request - the direct equivalent of Copilot CLI yolo mode or Claude's `--dangerously-skip-permissions`. There is **no `settings.local.json`-style file** in this lab: in the embedded-SDK hosting model the host app owns the gate, and that one callback is the single in-process control point.

To gate tool use, replace `approve_all` with your own callback that inspects each request (tool name plus arguments, for example the shell command or target path) and returns an approve or deny decision - that is where an allow-list / deny-list belongs.

In practice "what the agent can do" is governed by four layers, weakest to strongest:

| Layer | Where | Strength |
|---|---|---|
| Permission callback | `on_permission_request` in `main.py` (currently `approve_all`) | The in-process gate. Open by default; tighten with a custom callback |
| Working directory | `working_directory=$HOME` in `main.py` | Scopes filesystem ops to the session sandbox |
| System prompt policy | `system_prompt.md` | Soft - guidance the model may or may not follow |
| Container identity + RBAC | per-agent **AgentIdentity** + the Step 5 role grants + platform network egress | Hard boundary - even with `approve_all` the agent acts only as the managed identity and cannot exceed its Azure permissions or reach resources it has no role on |

The identity layer is the one that actually contains the agent: `approve_all` lets it run any tool, but it still acts only as the AgentIdentity with the four roles from Step 5, so the blast radius is whatever that principal can touch. Grant narrowly.

Every tool call is also fully **observable**: it emits `TOOL_EXECUTION_START` / `TOOL_EXECUTION_COMPLETE` events (streamed as SSE) and an `execute_tool <name>` span in Foundry Tracing, so you get an audit trail of every shell / python / file action even though nothing is gated.

## When this pattern is interesting

| Use case | Why this stack fits |
|---|---|
| Internal devops / coding assistants | Copilot SDK already understands shell, code, file edits, and skill discovery. You inherit that. |
| Domain agents that need persona + procedures | `system_prompt.md` is persona; `skills/*` are procedures. Two clean knobs. |
| Compliance / sovereignty constraints on model traffic | Inference stays inside your Foundry project (BYOK Foundry model + Managed Identity), not GitHub Copilot's backend. |
| Multi-turn sessions with resume | Copilot SDK caches the session by `FOUNDRY_AGENT_SESSION_ID`; the agent resumes across container restarts. |

## When to choose a different pattern

| Need | Pattern in this repo |
|---|---|
| Containerised Microsoft Agent Framework agent against an APIM-fronted core gateway | [`08-03-hosted-agents`](../08-03-hosted-agents/08-03-00-hosted-agents.md) |
| MCP tool servers backing a hosted agent | [`08-05-contoso-pmo-mcp`](../08-05-contoso-pmo-mcp/) |
| Vector-store-backed agent with grounding | The Foundry IQ / Bing Grounding stack referenced in [`infra/core/search/`](./infra/core/search/) is wired but disabled by default here |

## Files

| File | Purpose |
|---|---|
| [`08-10-01-deploy-hosted-copilot-sdk-agent.ipynb`](08-10-01-deploy-hosted-copilot-sdk-agent.ipynb) | Walks the full `az deployment sub create` → `az acr build` → `AIProjectClient.agents.create_version` → role-grant → invoke loop, then uploads `data/m365-licenses.csv` into a session, runs five M365 license analytics prompts through the deployed agent, and has the agent render a cost-by-department chart that the notebook downloads back out of the sandbox |
| [`data/m365-licenses.csv`](data/m365-licenses.csv) | Synthetic M365 license export (100 users, real SKUs, engineered outliers: 5 disabled-but-licensed, 6 stale SPE_E5 holders, 14 ghost users). Used by Step 7 of the notebook to demonstrate hosted-agent session file ops |
| [`data/m365-reference.json`](data/m365-reference.json) | Per-SKU monthly costs + department-code names. Uploaded to the session in Step 7 so the agent joins costs/names onto the licenses CSV - keeps this volatile data out of the skill |
| [`infra/main.bicep`](infra/main.bicep) | Subscription-scoped Bicep that provisions the AI Foundry account, project, model deployment, ACR, capability host, and (optionally) App Insights / Log Analytics / Bing Grounding / AI Search |
| [`src/github-copilot-invocations/main.py`](src/github-copilot-invocations/main.py) | The agent. Picks `GITHUB_TOKEN` vs Foundry BYOK at startup, manages a singleton Copilot session, streams `SessionEvent`s as SSE |
| [`src/github-copilot-invocations/system_prompt.md`](src/github-copilot-invocations/system_prompt.md) | Persona appended to the Copilot CLI's built-in system message |
| [`src/github-copilot-invocations/skills/m365-license-analytics/SKILL.md`](src/github-copilot-invocations/skills/m365-license-analytics/SKILL.md) | Skill supplying the M365 license analysis method, column glossary, and reclaim definition - costs and department names come from the uploaded reference, not the skill |
| [`src/github-copilot-invocations/tracing.py`](src/github-copilot-invocations/tracing.py) | OTel span tree (`invoke_agent` → `execute_tool` / `chat <model>`) emitted to Application Insights |

## Prerequisites

- Azure subscription with **Cognitive Services** quota for `gpt-5.4-mini` in `swedencentral` (or another supported region listed in `infra/main.bicep`).
- `az` CLI (signed in via `az login`) and `python>=3.11`.
- Python packages: `azure-ai-projects>=2.1.0`, `azure-identity`, `requests` (provided by the repo's `uv` environment).

---

[Next: Deploy the hosted Copilot SDK agent →](08-10-01-deploy-hosted-copilot-sdk-agent.ipynb)
