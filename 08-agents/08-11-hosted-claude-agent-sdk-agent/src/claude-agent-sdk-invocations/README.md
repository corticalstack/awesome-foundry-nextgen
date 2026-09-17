**IMPORTANT!** All samples and other resources made available in this GitHub repository ("samples") are designed to assist in accelerating development of agents, solutions, and agent workflows for various scenarios. Review all provided resources and carefully test output behavior in the context of your use case. AI responses may be inaccurate and AI actions should be monitored with human oversight.

# Claude Agent SDK - Invocations Protocol (Streaming)

A getting-started agent using the [Claude Agent SDK](https://pypi.org/project/claude-agent-sdk/) (`ClaudeSDKClient`) with the [azure-ai-agentserver-invocations](https://pypi.org/project/azure-ai-agentserver-invocations/) protocol. It is the Claude counterpart to [`08-10`](../../08-10-hosted-copilot-sdk-agent/)'s GitHub Copilot SDK agent: the Foundry hosting shell is identical, only the agent loop changes.

> Deploying this agent to Microsoft Foundry is driven by the lab notebook [`08-11-01-deploy-hosted-claude-agent-sdk-agent.ipynb`](../../08-11-01-deploy-hosted-claude-agent-sdk-agent.ipynb), which builds the container image with `az acr build` and registers it via the `azure-ai-projects` SDK. This README documents the agent itself and how to run it locally.

## How It Works

1. Receives `{"input": "..."}` via `POST /invocations`
2. On first request, lazy-creates a singleton `ClaudeSDKClient` that spawns and supervises a bundled `claude` CLI subprocess (the reason/act/observe loop)
3. Each Claude SDK message is forwarded as an SSE `data:` event (text deltas, tool-use, and a final result)
4. A final `event: done` signal marks the end of the response
5. The client is cached in memory and reused across requests for multi-turn conversation
6. Skills in `skills/` are copied into the working dir's `.claude/skills` so the CLI discovers them - e.g. the included `m365-license-analytics` skill

## Why the Claude Agent SDK needs a Claude model (the format match)

The Claude Agent SDK only speaks the **Anthropic Messages API** (`/v1/messages`). Foundry serves Claude models over exactly that surface (`https://<resource>.services.ai.azure.com/anthropic/v1/messages`), so the SDK points straight at a Foundry Claude deployment with **no translation layer**. This is the mirror image of 08-10, where the OpenAI-native Copilot SDK pointed straight at Foundry's `/openai/v1/` surface. A non-Claude (e.g. gpt) Foundry model would require an Anthropic<->OpenAI translation proxy (LiteLLM) in front - it is not a drop-in.

## Environment Variables

This agent supports two backends. Configure one:

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_FOUNDRY_RESOURCE` | For Foundry model | The Foundry resource (account) name. The SDK calls `https://<resource>.services.ai.azure.com/anthropic`. If unset, it is derived from `AZURE_AI_PROJECT_ENDPOINT` / `FOUNDRY_PROJECT_ENDPOINT` |
| `AZURE_AI_MODEL_DEPLOYMENT_NAME` | For Foundry model | Your Claude deployment name (e.g. `claude-sonnet-4-6`). Pointed at the sonnet/haiku/opus roles |
| `AZURE_CLIENT_ID` | For Foundry model (hosted) | The AgentIdentity client_id, so `DefaultAzureCredential` resolves to the per-agent managed identity |
| `ANTHROPIC_API_KEY` | For Anthropic API | Public `api.anthropic.com` backend (a real Claude model, but traffic leaves Foundry) |
| `FOUNDRY_AGENT_SESSION_ID` | No | Session ID injected by the hosted runtime; falls back to a generated UUID |

**Backend selection** (`_configure_backend` in `main.py`):
- If a Foundry resource (explicit or derived) **and** `AZURE_AI_MODEL_DEPLOYMENT_NAME` are set -> sets `CLAUDE_CODE_USE_FOUNDRY=1` and uses your **Foundry Claude model** via Managed Identity (no key).
- Else if `ANTHROPIC_API_KEY` is set -> uses the **public Anthropic API**.

## Running Locally

### Prerequisites

- Python 3.10+
- Either a deployed Foundry Claude model + `az login` (Entra), or an `ANTHROPIC_API_KEY`.

### Start the agent (Foundry Claude model)

```bash
pip install -r requirements.txt
export AZURE_AI_PROJECT_ENDPOINT=https://<resource>.services.ai.azure.com/api/projects/<project>
export AZURE_AI_MODEL_DEPLOYMENT_NAME=claude-sonnet-4-6
python main.py            # http://localhost:8088/
```

Authentication uses Managed Identity via `DefaultAzureCredential`; locally that resolves to your `az login`. The caller principal needs **Cognitive Services User** (or Foundry User) on the account so it can reach the account-level `/anthropic` endpoint.

### Test with curl

```bash
curl -N -X POST http://localhost:8088/invocations \
  -H "Content-Type: application/json" \
  -d '{"input": "Use your shell tools to print the date, then summarise in one line."}'
```

### SSE Event Format

```
data: {"type": "assistant.message_delta", "data": {"deltaContent": "Python is"}}
data: {"type": "tool.use", "data": {"name": "Bash", "id": "toolu_..."}}
data: {"type": "result", "data": {"session_id": "...", "num_turns": 3, "total_cost_usd": 0.01, "usage": {...}}}
event: done
data: {"invocation_id": "...", "session_id": "..."}
```

## Customizing the Agent

| File | Purpose |
|------|---------|
| `system_prompt.md` | Persona / global policy, **appended** to the Claude Code preset system prompt (its built-in guardrails and tool instructions are preserved). Empty/missing -> preset unchanged. |
| `skills/<name>/SKILL.md` | A task-specific Agent Skill the model discovers on demand. Copied into `.claude/skills` at startup. The bundled `m365-license-analytics` skill supplies the M365 license analysis method. |

## Observability - Foundry portal Tracing

`tracing.py` maps Claude SDK messages to OpenTelemetry GenAI spans:

```
invoke_agent claude-agent-sdk   (parent)
+-- execute_tool <name>         (one per ToolUseBlock)
+-- chat <model>                (token usage + estimated cost, from ResultMessage)
```

Open **Foundry portal -> your project -> Tracing** to inspect the spans and per-turn token counts.

## Troubleshooting

### Images must be built for `linux/amd64`

Foundry's hosted runtime is `linux/amd64`, which is also the platform the bundled `claude` binary targets. The notebook's `az acr build` step does a remote build that always produces the correct architecture.
