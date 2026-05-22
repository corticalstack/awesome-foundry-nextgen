# Agent live observability

Demonstrates how to trace Foundry agents using **OpenTelemetry** and **Azure Monitor Application Insights** from your own application code. The example agent throughout is **`aria-rm-briefing-agent`** - the intent-level MCP briefing assistant from [08-05b](../08-05b-contoso-private-banking-mcp/), which must be deployed first.

## What this lab is

This is **application-level (client-side) tracing** - not the Foundry Portal's built-in server-side tracing.

> **Note:** Tracing is GA for prompt agents. Workflow, hosted, and custom agents are in preview.

| Dimension | This lab |
|-----------|----------|
| **What it traces** | SDK calls your code makes - `agents.create_version`, `responses.create`, tool invocations - instrumented via OpenTelemetry hooks in the `azure-ai-projects` SDK |
| **Where traces go** | Your own Application Insights instance, queryable via KQL |
| **Who controls it** | You - you configure the exporter, set `enable_content_recording`, flush the buffer |

This is distinct from the Foundry Portal's built-in tracing, which is server-side and captures traces for any agent invocation regardless of client. The lab's approach lets you:

- **Correlate** agent traces with the rest of your application's telemetry (e.g. alongside HTTP requests, DB calls)
- **Route** traces to your own workspace, not just the Foundry portal
- **Apply** custom span attributes or sampling rules

It's the **"bring your own observability stack"** pattern - useful when Foundry agents are one component inside a larger application you're already monitoring.

## Sub-topics

| Document | What it covers |
|----------|---------------|
| [08-07-02-agent-tracing.md](08-07-02-agent-tracing.md) | OTel concepts, span hierarchy, span attribute schema, GA/preview status |
| [08-07-04-real-time-observability.md](08-07-04-real-time-observability.md) | Foundry Portal Monitor tab, dashboard metrics, continuous evaluation, Monitor Settings |

## Notebooks

| Notebook | Purpose |
|----------|---------|
| [08-07-01-deploy-observability-infra.ipynb](08-07-01-deploy-observability-infra.ipynb) | Deploys Log Analytics, Application Insights, and `obs-project` into the existing `rg-foundry-multi-{suffix}` resource group |
| [08-07-03-agent-observability.ipynb](08-07-03-agent-observability.ipynb) | Configures OpenTelemetry, instruments the SDK, invokes the existing `aria-rm-briefing-agent` from [08-05b](../08-05b-contoso-private-banking-mcp/), and verifies traces in App Insights - including MCP-tool spans |
| [08-07-05-agent-continuous-evaluation.ipynb](08-07-05-agent-continuous-evaluation.ipynb) | Sets up continuous evaluation via the Python SDK against `aria-rm-briefing-agent`; generates RM-briefing traffic and verifies relevance scoring in the portal Monitor tab |

## Key SDK pattern

```python
from azure.monitor.opentelemetry import configure_azure_monitor
from azure.ai.projects.telemetry import AIProjectInstrumentor

# 1. Set up OTel provider pointing at your App Insights instance
configure_azure_monitor(connection_string=OBS_APP_INSIGHTS_CONN_STRING)

# 2. Hook the azure-ai-projects SDK into the OTel pipeline
#    Must happen before creating any clients
AIProjectInstrumentor().instrument(enable_content_recording=True)

# All subsequent SDK calls are automatically traced
project_client = AIProjectClient(endpoint=..., credential=DefaultAzureCredential())
```

`AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING=true` must also be set before instrumentation to capture full request/response content.

## Infrastructure deployed

| Resource | Name | Purpose |
|----------|------|---------|
| Log Analytics Workspace | `log-obs-{suffix}` | Required backend for Application Insights |
| Application Insights | `appi-obs-{suffix}` | Trace storage and KQL query target |
| Foundry Project | `obs-project` | Child of the existing shared multi-account |
| Account connection | `appinsights-connection` | `isSharedToAll: true` - visible to all projects on the account |
| Project connection | `landing-zone-apim` | APIM gateway access for model inference |

## References

- [Agent Tracing Overview](https://learn.microsoft.com/azure/ai-foundry/observability/concepts/trace-agent-concept?view=foundry)
- [Set Up Tracing in Microsoft Foundry](https://learn.microsoft.com/azure/ai-foundry/observability/how-to/trace-agent-setup?view=foundry)
- [Tracing Integrations](https://learn.microsoft.com/azure/ai-foundry/observability/how-to/trace-agent-framework?view=foundry)
- [Agent Monitoring Dashboard](https://learn.microsoft.com/azure/ai-foundry/observability/how-to/how-to-monitor-agents-dashboard?view=foundry)

---

[Next: Deploy observability infrastructure →](08-07-01-deploy-observability-infra.ipynb)
