**IMPORTANT!** All samples and other resources made available in this GitHub repository ("samples") are designed to assist in accelerating development of agents, solutions, and agent workflows for various scenarios. Review all provided resources and carefully test output behavior in the context of your use case. AI responses may be inaccurate and AI actions should be monitored with human oversight.

# GitHub Copilot SDK — Invocations Protocol (Streaming)

A minimal getting-started agent using the [GitHub Copilot SDK](https://pypi.org/project/github-copilot-sdk/) (`CopilotClient`) with the [azure-ai-agentserver-invocations](https://pypi.org/project/azure-ai-agentserver-invocations/) protocol. Streams raw Copilot SDK session events as SSE with multi-turn support.

> Deploying this agent to Microsoft Foundry is driven by the lab notebook [`08-10-01-deploy-hosted-copilot-sdk-agent.ipynb`](../../08-10-01-deploy-hosted-copilot-sdk-agent.ipynb), which builds the container image with `az acr build` and registers it via the `azure-ai-projects` SDK. This README documents the agent itself and how to run it locally.

## How It Works

1. Receives `{"input": "..."}` via `POST /invocations`
2. On first request, tries to resume a persisted Copilot session (by `FOUNDRY_AGENT_SESSION_ID`); if none exists, creates a new one
3. Each `SessionEvent` from the Copilot SDK is streamed back as an SSE `data:` event using `event.to_dict()`
4. A final `event: done` signal marks the end of the response
5. The session is cached in memory and reused across requests for multi-turn conversation
6. Skills in the `skills/` directory are auto-loaded — e.g. the included `m365-license-analytics` skill supplies the M365 license analysis method

## Environment Variables

This agent supports two LLM backends. Configure one of the following:

| Variable | Required | Description |
|----------|----------|-------------|
| `GITHUB_TOKEN` | For Copilot model | GitHub fine-grained PAT with **Copilot Requests → Read-only** permission |
| `AZURE_AI_PROJECT_ENDPOINT` | For Foundry model | The Foundry project endpoint (`https://<account>.services.ai.azure.com/api/projects/<project>`); `main.py` appends `/openai/v1/` as the provider base URL. Auto-injected as `FOUNDRY_PROJECT_ENDPOINT` when hosted |
| `AZURE_AI_MODEL_DEPLOYMENT_NAME` | For Foundry model | Model deployment name (e.g. `gpt-5.4-mini`) |
| `FOUNDRY_AGENT_SESSION_ID` | No | Session ID for persistence/resume. If unset, a UUID is generated |

**How the agent selects its LLM backend** (`_byok_provider` in `main.py`):
- If `AZURE_AI_PROJECT_ENDPOINT` (or the auto-injected `FOUNDRY_PROJECT_ENDPOINT`) and `AZURE_AI_MODEL_DEPLOYMENT_NAME` are set → uses your **Foundry model** via Managed Identity (no `GITHUB_TOKEN` needed)
- If only `GITHUB_TOKEN` is set → uses the **GitHub Copilot model** (quickest way to get started)
- If both are set → the **Foundry model takes precedence**

## Running Locally

### Prerequisites

- Python 3.10+
- A GitHub fine-grained PAT (`github_pat_` prefix) for the Copilot-model path

Create one at [github.com/settings/personal-access-tokens/new](https://github.com/settings/personal-access-tokens/new) with **Account permissions → Copilot Requests → Read-only**.

> **Note:** Classic tokens (`ghp_`) are not supported. Use a fine-grained PAT (`github_pat_`), OAuth token (`gho_`), or GitHub App user token (`ghu_`).

### Start the agent

```bash
pip install -r requirements.txt
export GITHUB_TOKEN=github_pat_...        # Copilot-model path
python main.py
```

The agent starts on `http://localhost:8088/`.

To use a Foundry model instead of the Copilot model, set the Foundry variables (no `GITHUB_TOKEN` needed):

```bash
export AZURE_AI_PROJECT_ENDPOINT=https://<account>.services.ai.azure.com/api/projects/<project>
export AZURE_AI_MODEL_DEPLOYMENT_NAME=gpt-5.4-mini
python main.py
```

Authentication uses Managed Identity via `DefaultAzureCredential`. When deployed as a hosted agent, the lab notebook injects `AZURE_AI_PROJECT_ENDPOINT`, `AZURE_AI_MODEL_DEPLOYMENT_NAME`, and `AZURE_CLIENT_ID` for you (and the platform auto-injects `FOUNDRY_PROJECT_ENDPOINT`).

### Test with curl

```bash
# First message
curl -N -X POST http://localhost:8088/invocations \
  -H "Content-Type: application/json" \
  -d '{"input": "What is Python?"}'

# Follow-up (multi-turn — same session remembers context)
curl -N -X POST http://localhost:8088/invocations \
  -H "Content-Type: application/json" \
  -d '{"input": "Give me a code example"}'
```

### SSE Event Format

Each Copilot SDK event is streamed via `event.to_dict()`:

```
data: {"type": "assistant.message_delta", "data": {"delta_content": "Python is"}}\n\n
data: {"type": "assistant.message_delta", "data": {"delta_content": " a programming"}}\n\n
...
event: done
data: {"invocation_id": "...", "session_id": "..."}
```

## Customizing the Agent

This agent has two extension surfaces — pick the one that matches your need:

| File | Purpose | Example |
|------|---------|---------|
| `system_prompt.md` | **Persona / global policy** that applies to every turn. Appended to the Copilot CLI's built-in system message (CLI guardrails preserved). | "You are Acme Corp's internal devops agent. Always prefer Bicep over Terraform." |
| `skills/<name>/SKILL.md` | **Task-specific procedure** the model discovers and follows on demand. | The bundled `m365-license-analytics` skill supplies the M365 license analysis method. |

To change the persona, edit `system_prompt.md`, then rebuild and re-register the agent (Steps 3-4 of the notebook). If `system_prompt.md` is empty or missing, the CLI's default system message is used unchanged.

## Observability — Foundry portal Tracing

When deployed, every invocation produces an OpenTelemetry trace tree:

```
invoke_agent github-copilot-invocations   (parent)
├── execute_tool <name>                   (one per tool call)
└── chat <model>                          (token usage + estimated cost)
```

Open **Foundry portal → your project → Tracing** to inspect the spans, tool inputs/outputs, and per-turn token counts. The mapping logic lives in `tracing.py`; tracing is best-effort and never breaks an invocation.

## Adding Skills

Any subdirectory under `skills/` containing a `SKILL.md` file is automatically loaded by the Copilot SDK. The included `m365-license-analytics` skill demonstrates this:

```
skills/
└── m365-license-analytics/
    └── SKILL.md    ← the M365 license analysis method
```

To add your own skill, create a new folder under `skills/` with a `SKILL.md`:

```bash
mkdir skills/my-skill
cat > skills/my-skill/SKILL.md << 'EOF'
---
name: my-skill
description: What this skill does.
---

# My Skill

Instructions for Copilot when this skill is active.
EOF
```

## Troubleshooting

### Images must be built for `linux/amd64`

Foundry's hosted runtime is `linux/amd64`. The notebook's `az acr build` step does a remote build that always produces the correct architecture.

If you build locally on a non-`amd64` machine (for example, an Apple Silicon Mac), the image will not be compatible with the service and will fail at runtime. Force the architecture:

```bash
docker build --platform=linux/amd64 -t image .
```
