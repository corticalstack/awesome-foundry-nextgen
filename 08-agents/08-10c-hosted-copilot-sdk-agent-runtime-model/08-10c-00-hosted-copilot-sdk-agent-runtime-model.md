# Runtime model selection and out-of-the-box telemetry for a hosted agent

This is the **"C" variant** of [`08-10-hosted-copilot-sdk-agent`](../08-10-hosted-copilot-sdk-agent/08-10-00-hosted-copilot-sdk-agent.md): it borrows that lab's agent design, and answers two questions customers ask once they have a hosted agent behind a chat UI:

1. **Can the user change the agent's model or reasoning effort in the middle of a conversation**, from a dropdown in the UI, without creating a new agent version or redeploying?
2. **What logging and telemetry does a Foundry hosted agent produce out of the box?**

The lab is **self-contained**. It ships its own Bicep and its own copy of the container source, and provisions everything it needs into its own resource group: a Foundry account and project, the capability host that runs hosted agents, a container registry, Application Insights, and the three model deployments the chat UI switches between. No other notebook has to run first.

## Question 1: switching the model and reasoning effort at runtime

**Yes, but the switch lives in the container code, not in the platform.**

A hosted agent version is immutable. The version is a snapshot of the image, resources and environment variables, and changing any of them means `create_version`. So the model name set in `AZURE_AI_MODEL_DEPLOYMENT_NAME` cannot change at runtime.

What makes a runtime switch possible:

- **The invocations protocol passes the request body to your code unchanged.** A chat UI can send `{"input": "...", "model": "gpt-5.4-nano", "reasoning_effort": "low"}` and the container reads the extra fields.
- **The GitHub Copilot SDK can switch a live session.** `session.set_model(model, reasoning_effort=...)` applies from the next model call and keeps the conversation history. It emits a `session.model_change` event, and every model call emits `assistant.usage` with the model and reasoning effort it used.

`main.py` in this lab adds about 60 lines to the 08-10 container:

```
POST /invocations {"input", "model"?, "reasoning_effort"?}
  -> validate model against AZURE_AI_ALLOWED_MODELS, effort against low/medium/high/xhigh (HTTP 400 otherwise)
  -> if the selection differs from the live session: session.set_model(model, reasoning_effort=effort)
  -> session.send(input), stream events back as SSE
```

The environment variables now hold defaults only: `AZURE_AI_MODEL_DEPLOYMENT_NAME`, `AZURE_AI_REASONING_EFFORT`, and the allowlist `AZURE_AI_ALLOWED_MODELS`.

### How it was verified

- **Locally**, the modified container ran against the real Foundry deployments with a logging proxy between the Copilot CLI and Foundry. The requests reaching `<project>/openai/v1/responses` carried the switched values: `model` changed from `gpt-5.4-mini` to `gpt-5.4-nano` to `gpt-5.4`, and `reasoning.effort` from `medium` to `low` to `high` to `low`. The conversation history carried across every switch.
- **Hosted**, the notebook runs a five-turn conversation where the "UI" switches model and effort, checks every model call's `assistant.usage` event against the selection, and confirms the agent still has one version with the same image afterwards. In the reference run, `gpt-5.4` used 163 reasoning tokens at `high` and 26 at `low`.

### Things to design for

| Point | Why it matters |
|---|---|
| Send the UI selection on **every** request | Sessions are torn down after an idle timeout (15 minutes by default). The conversation is restored from `$HOME`, but the container restarts and its in-memory selection falls back to the defaults. |
| Deploy every selectable model | The container can only switch to deployments that exist on the Foundry account, and the agent identity needs access to them. |
| Keep an allowlist | The request body is untrusted input. `AZURE_AI_ALLOWED_MODELS` stops a client selecting an expensive or unapproved deployment. |
| Reasoning effort values differ by model | `xhigh` is documented for `gpt-5.4` but not for `gpt-5.4-mini` or `gpt-5.4-nano`. Restrict the UI's options per model. |
| Other frameworks need their own switch | `set_model()` is a Copilot SDK feature. With Agent Framework, LangGraph or a direct Responses API call, pass the selected model and `reasoning.effort` into the model call yourself. |

## Question 2: out-of-the-box telemetry

Telemetry from a hosted agent comes in three layers. The first two need no code.

| Layer | What you get | Where |
|---|---|---|
| **Platform** | One `invoke_agent` request per invocation, cloud role `agentsv2`, with agent name, version, session id and invocation id | Application Insights `requests`; Foundry portal agent **Traces** tab |
| **Container runtime** | Injected environment variables: `FOUNDRY_PROJECT_ENDPOINT`, `FOUNDRY_PROJECT_ARM_ID`, `FOUNDRY_AGENT_NAME`, `FOUNDRY_AGENT_VERSION`, `FOUNDRY_AGENT_SESSION_ID`, `APPLICATIONINSIGHTS_CONNECTION_STRING`. The hosting library logs a `Platform environment` line with them at startup | Container environment; session log stream |
| | Container stdout and stderr per session | Session log stream: `GET {project}/agents/{agent}/versions/{version}/sessions/{session_id}:logstream` (live only; 30-minute connection limit, 2-minute idle timeout) |
| | Python logging exported through the injected connection string, cloud role = agent name | Application Insights `traces` |
| **Agent tracing** (code) | `chat <model>` spans with model, reasoning effort, input/output/reasoning tokens, time to first token and cost; `execute_tool <name>` spans. Linked to the platform request by `operation_Id` | Application Insights `dependencies`; Foundry portal **Traces** tab |

The agent's **Monitor** tab in the Foundry portal (preview) charts token usage, latency and run success rate. For CPU, memory and request rate, use the Application Insights **Performance** blade.

Three things to know when reading the raw data:

- The platform records an invocation as successful even when the container answers with an error such as HTTP 400. Application-level errors show up only in the container's logs and spans.
- The Azure Monitor distro in the container probes the instance metadata endpoint at startup. The resulting `ConnectionError` rows in `exceptions` are harmless.
- Spans from `tracing.py` report cloud role `unknown_service`. Set `OTEL_SERVICE_NAME` in the agent definition for a clearer name.

## Files

| File | Purpose |
|---|---|
| [`08-10c-01-runtime-model-and-telemetry.ipynb`](08-10c-01-runtime-model-and-telemetry.ipynb) | Provisions the stack, builds and registers the agent, runs the model and reasoning effort switching conversation, and walks through the telemetry layers with the log stream and KQL queries |
| [`infra/main.bicep`](infra/main.bicep) | Subscription-scoped Bicep: resource group, Foundry account and project, capability host, container registry, Application Insights and Log Analytics, and the three model deployments |
| [`src/github-copilot-invocations/main.py`](src/github-copilot-invocations/main.py) | The 08-10 agent plus per-request model and reasoning effort selection |
| [`src/github-copilot-invocations/tracing.py`](src/github-copilot-invocations/tracing.py) | The 08-10 span mapping, plus `gen_ai.request.reasoning_effort` on `chat <model>` spans |

## Prerequisites

- `az login`, with rights to create a resource group, a Foundry account and role assignments in the subscription.
- Quota for `gpt-5.4-nano`, `gpt-5.4-mini` and `gpt-5.4` GlobalStandard in `swedencentral` (the notebook deploys 50K TPM each).
- The repo's `uv` environment: `azure-ai-projects>=2.1.0`, `azure-identity`, `requests`.

Everything lands in `rg-foundry-copilot-sdk-08-10c`, so the cleanup cell at the end of the notebook removes the lab with a single resource group delete.

## Sources

- [Hosted agents in Foundry Agent Service](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents): immutable versions, sessions and idle timeout
- [Deploy a hosted agent](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/deploy-hosted-agent): platform-injected environment variables
- [Manage hosted agents](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/manage-hosted-agent): session log stream
- [Agent tracing overview](https://learn.microsoft.com/en-us/azure/foundry/observability/concepts/trace-agent-concept) and [Monitor agents dashboard](https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/how-to-monitor-agents-dashboard)
- [Azure OpenAI reasoning models](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/reasoning): reasoning effort values per model

---

[Next: Runtime model selection and telemetry notebook →](08-10c-01-runtime-model-and-telemetry.ipynb)
