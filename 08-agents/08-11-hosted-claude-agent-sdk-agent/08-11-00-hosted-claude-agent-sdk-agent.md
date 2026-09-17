# Foundry-hosted agent powered by the Claude Agent SDK

This lab deploys a containerised agent built on the [**Claude Agent SDK**](https://pypi.org/project/claude-agent-sdk/) (the SDK behind Claude Code) and hosts it as a **Microsoft Foundry hosted agent**. Inference is served by a **Foundry-deployed `claude-sonnet-4-6` model** reached through Managed Identity, so the container needs no secrets at runtime.

It is the Claude counterpart to [`08-10`](../08-10-hosted-copilot-sdk-agent/08-10-00-hosted-copilot-sdk-agent.md): the Foundry hosting shell, the invocations protocol, the two-pass identity dance, the role grants, and the CSV-analytics demo are all the same. **Only the agent loop changes** - `ClaudeSDKClient` replaces `CopilotClient`.

The notebook follows the same pattern as the rest of this repo: `az deployment sub create` runs the Bicep, `az acr build` builds the container, and `AIProjectClient.agents.create_version` registers it with the project as a hosted agent.

## The format match (why this needs a Claude model)

The Claude Agent SDK only speaks the **Anthropic Messages API** (`/v1/messages`). Foundry serves Claude models over exactly that surface:

```
https://<resource>.services.ai.azure.com/anthropic/v1/messages
```

So the SDK points straight at a Foundry Claude deployment with **no translation layer** - the mirror image of 08-10, where the OpenAI-native Copilot SDK pointed straight at Foundry's `/openai/v1/responses`. Foundry serves gpt over `/openai/v1` and Claude over `/anthropic/v1`; there is no native Anthropic surface for a gpt model, so a non-Claude Foundry model would need an Anthropic<->OpenAI proxy (e.g. LiteLLM) in front. That asymmetry is the whole point of this lab: the clean, no-shim match for the Claude Agent SDK is a Foundry **Claude** model.

`main.py` enables this with a single switch: given the project endpoint + a model deployment name, it sets `CLAUDE_CODE_USE_FOUNDRY=1` and `ANTHROPIC_FOUNDRY_RESOURCE=<account>`, and the bundled `claude` CLI takes care of calling `/anthropic` with a Managed Identity token (audience `https://ai.azure.com`).

## What this example demonstrates

- **Hosted agent runtime.** Foundry runs the container under the project's capability host. No Container App, Web App, or AKS to manage.
- **Claude Agent SDK as the agent loop.** `ClaudeSDKClient` owns sessions, tool-calling, streaming, and skill discovery. Your `main.py` only forwards SDK messages out through Foundry's [invocations protocol](https://pypi.org/project/azure-ai-agentserver-invocations/).
- **BYO Foundry Claude model via Managed Identity.** No Anthropic API key, no key of any kind in the container - inference stays inside your Foundry project.
- **Two extension surfaces:** `system_prompt.md` (persona, appended to the Claude Code preset) and `skills/<name>/SKILL.md` (procedures discovered on demand).
- **OTel tracing into Foundry portal.** `tracing.py` maps Claude SDK messages to GenAI-semantic-convention spans, so the Tracing tab shows the per-invocation tree with token usage and estimated cost.

## How the agentic loop works

The agent runs **two nested loops**. The reason/act/observe loop that makes it agentic does **not** live in `main.py` - it runs inside a **`claude` CLI subprocess** that the SDK spawns and supervises over stdio. `main.py` is a thin Foundry-protocol shell that boots that subprocess and forwards its message stream.

```
Foundry hosted runtime
  └── container: `python main.py`   (Dockerfile CMD, port 8088)
        └── InvocationAgentServerHost      outer loop: one HTTP POST /invocations per user turn
              └── ClaudeSDKClient  ->  spawns the bundled `claude` CLI subprocess
                    └── inner agentic loop: model <-> tools, until the turn ends with a ResultMessage
```

### Inner loop - the agentic part, inside the `claude` CLI

`_ensure_client` builds `ClaudeAgentOptions` and calls `client.connect()`, which boots the `claude` CLI subprocess. The CLI is the agent harness: it owns the system prompt, **skill discovery** (`.claude/skills`), and **tool execution** (Bash, Read, Write, Edit, ...). Each `client.query(input)` runs one turn of the loop:

```
query(user_text)
  -> model call (chat)            streams text deltas (StreamEvent) + AssistantMessage
       -> model wants a tool?     AssistantMessage carries a ToolUseBlock
            run Bash / python / ...
                                  tool result fed back to the model
       -> call the model again    (repeat: reason -> act -> observe)
  -> no more tool calls, final answer
ResultMessage                     the turn is complete (carries session_id, usage, cost)
```

`main.py` never decides tool use - it observes the message stream. `tracing.py` maps `ToolUseBlock` -> `execute_tool` spans and `ResultMessage` -> a `chat <model>` span, so a single CSV-analytics turn shows multiple `execute_tool` spans: that span tree *is* the agentic loop made visible.

### Outer loop - the request and message drain, in `main.py`

Foundry calls `POST /invocations` once per user message. `handle_invoke` validates `{"input": "..."}` and returns a streaming response backed by `_stream_response`, which forwards each Claude SDK message as an SSE `data:` frame (text deltas as `assistant.message_delta`, tool calls as `tool.use`, a final `result`), then emits `event: done`. A `_client_lock` serialises turns because a single `ClaudeSDKClient` holds one conversation.

### Multi-turn conversation

The first request lazy-creates a module-global `ClaudeSDKClient`; every later request reuses it, so the CLI subprocess keeps the message thread in memory. As in 08-10, the design assumes **one logical conversation per container instance** (the hosted runtime stamps a session id into the container env). To fan one container across concurrent users, replace the singleton with a `dict[session_id -> client]` cache, and attach a [`SessionStore`](https://code.claude.com/docs/en/agent-sdk/session-storage) if you need transcripts to survive a container restart.

## How the BYO-model wiring works

```
+-----------------------------------+        +----------------------------+
| Hosted agent container            |        | Foundry AI Services        |
|                                   |        |   account                  |
|  ClaudeSDKClient                  |        |                            |
|   -> bundled `claude` CLI         | HTTPS  |  <account>.services.ai.    |
|   CLAUDE_CODE_USE_FOUNDRY=1       |------->|  azure.com/anthropic/v1/   |
|   bearer = MI token (ai.azure.com)|        |  messages                  |
|   azure-ai-agentserver-           |        |                            |
|   invocations                     |        |  claude-sonnet-4-6 deploy  |
+------------+----------------------+        +----------------------------+
             | SSE
             v
   requests.post(...&agent_session_id=...)     (helpers in the notebook)
```

Container env vars (set at registration time via `create_version(..., environment_variables=...)`):

| Variable | Source | Why |
|---|---|---|
| `AZURE_AI_PROJECT_ENDPOINT` | Bicep output, read back in **Step 2** and injected at registration (the platform also auto-injects `FOUNDRY_PROJECT_ENDPOINT`) | `main.py` derives the resource name from it and sets `CLAUDE_CODE_USE_FOUNDRY=1` + `ANTHROPIC_FOUNDRY_RESOURCE`, so the SDK calls `<resource>.services.ai.azure.com/anthropic/v1/messages` with audience `https://ai.azure.com` |
| `AZURE_AI_MODEL_DEPLOYMENT_NAME` | Hardcoded in **Step 1** (`claude-sonnet-4-6`). The same value names the Bicep deployment, so provisioning and routing stay in sync | Pointed at the sonnet/haiku/opus model roles so every role resolves to the one deployed model |
| `AZURE_CLIENT_ID` | `instance_identity.client_id` from agent version metadata | Disambiguates the **AgentIdentity** managed identity inside `DefaultAzureCredential` (each version has a `blueprint` template + the runtime `instance_identity`; RBAC and `AZURE_CLIENT_ID` both target `instance_identity`) |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | auto-injected by platform | OTel export target |

RBAC role grants on the AgentIdentity principal (Step 5 of the notebook):
- `AcrPull` on the ACR (image pull)
- `Foundry User` on the project (general data plane)
- `Cognitive Services User` on the **account** scope (grants the `/anthropic/v1/messages` data action)

## What the agent is allowed to do (permission model)

Claude Code gates each tool call (Bash, file read/write/edit) behind a permission prompt. A hosted agent has nobody at a terminal, so `main.py` sets:

```python
permission_mode="bypassPermissions",   # main.py
```

This auto-approves every tool call - the direct equivalent of 08-10's `PermissionHandler.approve_all` / Copilot yolo mode / Claude's `--dangerously-skip-permissions`. In the embedded-SDK hosting model the host app owns the gate; to gate tool use, swap `bypassPermissions` for `"default"` and supply a `can_use_tool` callback in `ClaudeAgentOptions` that inspects each request and approves or denies it.

In practice "what the agent can do" is governed by four layers, weakest to strongest:

| Layer | Where | Strength |
|---|---|---|
| Permission mode / `can_use_tool` | `ClaudeAgentOptions` in `main.py` (currently `bypassPermissions`) | The in-process gate. Open by default; tighten with a callback |
| Working directory | `cwd` in `main.py` | Scopes the file tools to the session workspace |
| System prompt policy | `system_prompt.md` | Soft - guidance the model may or may not follow |
| Container identity + RBAC | per-agent **AgentIdentity** + the Step 5 role grants + platform network egress | Hard boundary - even with `bypassPermissions` the agent acts only as the managed identity and cannot exceed its Azure permissions |

The identity layer is the one that actually contains the agent: `bypassPermissions` lets it run any tool, but it still acts only as the AgentIdentity with the three roles from Step 5, so the blast radius is whatever that principal can touch. Grant narrowly. Every tool call is also fully **observable**: it emits a `tool.use` SSE event and an `execute_tool <name>` span in Foundry Tracing.

## When this pattern is interesting

| Use case | Why this stack fits |
|---|---|
| Internal devops / coding assistants | Claude Code already understands shell, code, file edits, and skill discovery. You inherit that. |
| Domain agents that need persona + procedures | `system_prompt.md` is persona; `skills/*` are procedures. Two clean knobs. |
| Compliance / sovereignty constraints on model traffic | Inference stays inside your Foundry project (BYO Foundry Claude model + Managed Identity), not Anthropic's public API. |
| Teams standardising on Claude Code | The same agent harness developers use locally, now hosted and reachable over the invocations protocol. |

## When to choose a different pattern

| Need | Pattern in this repo |
|---|---|
| The same hosted shell but the GitHub Copilot SDK / a gpt model | [`08-10-hosted-copilot-sdk-agent`](../08-10-hosted-copilot-sdk-agent/08-10-00-hosted-copilot-sdk-agent.md) |
| Containerised Microsoft Agent Framework agent | [`08-03-hosted-agents`](../08-03-hosted-agents/08-03-00-hosted-agents.md) |
| MCP tool servers backing a hosted agent | [`08-05-contoso-pmo-mcp`](../08-05-contoso-pmo-mcp/) |

## Files

| File | Purpose |
|---|---|
| [`08-11-01-deploy-hosted-claude-agent-sdk-agent.ipynb`](08-11-01-deploy-hosted-claude-agent-sdk-agent.ipynb) | Walks the full `az deployment sub create` -> `az acr build` -> `create_version` -> role-grant -> invoke loop, then uploads `data/m365-licenses.csv` into a session, runs five M365 license analytics prompts, and downloads an agent-rendered cost-by-department chart |
| [`data/m365-licenses.csv`](data/m365-licenses.csv) | Synthetic M365 license export (100 users, real SKUs, engineered outliers). Used by Step 7 to demonstrate hosted-agent session file ops |
| [`data/m365-reference.json`](data/m365-reference.json) | Per-SKU monthly costs + department-code names. Uploaded to the session so the agent joins costs/names onto the CSV - keeps volatile data out of the skill |
| [`infra/main.bicep`](infra/main.bicep) | Subscription-scoped Bicep: AI Foundry account, project, Claude model deployment, ACR, capability host, App Insights / Log Analytics |
| [`infra/core/ai/ai-project.bicep`](infra/core/ai/ai-project.bicep) | Project module; its deployment loop was extended to pass the `modelProviderData` Marketplace block that Anthropic (partner) deployments require |
| [`src/claude-agent-sdk-invocations/main.py`](src/claude-agent-sdk-invocations/main.py) | The agent. Selects the Foundry Claude vs Anthropic-API backend, manages a singleton `ClaudeSDKClient`, streams SDK messages as SSE |
| [`src/claude-agent-sdk-invocations/system_prompt.md`](src/claude-agent-sdk-invocations/system_prompt.md) | Persona appended to the Claude Code preset system prompt |
| [`src/claude-agent-sdk-invocations/skills/m365-license-analytics/SKILL.md`](src/claude-agent-sdk-invocations/skills/m365-license-analytics/SKILL.md) | Skill supplying the M365 license analysis method, column glossary, and reclaim definition |
| [`src/claude-agent-sdk-invocations/tracing.py`](src/claude-agent-sdk-invocations/tracing.py) | OTel span tree (`invoke_agent` -> `execute_tool` / `chat <model>`) emitted to Application Insights |

## Prerequisites

- An **Enterprise or MCA-E** Azure subscription with **Claude quota** for `claude-sonnet-4-6` GlobalStandard in `swedencentral` (or `eastus2`). See the notebook's Step 2 eligibility note.
- **Marketplace purchases allowed** on that subscription. Claude deployments subscribe to an Anthropic Marketplace offer, so internal or sandbox subscriptions, or tenants whose policy disables Marketplace purchases, fail at the model deployment with `Marketplace Subscription purchase eligibility check failed`, even when Claude quota is available.
- `az` CLI (signed in via `az login`) and `python>=3.11`.
- Python packages: `azure-ai-projects>=2.1.0`, `azure-identity`, `requests` (provided by the repo's `uv` environment).

---

[Next: Deploy the hosted Claude Agent SDK agent →](08-11-01-deploy-hosted-claude-agent-sdk-agent.ipynb)
