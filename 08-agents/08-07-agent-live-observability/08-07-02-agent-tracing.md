# Agent tracing

Explains the OpenTelemetry tracing model used by Azure AI Foundry agents, including span hierarchy, attribute schema, and GA/preview status by agent type.

## Overview

Agent tracing in Azure AI Foundry is built on **OpenTelemetry (OTel)** - the vendor-neutral observability framework. When you instrument the `azure-ai-projects` SDK (via `AIProjectInstrumentor`), every SDK operation emits spans that flow through an OTel pipeline to your chosen backend (e.g., Application Insights).

This is **client-side, application-level tracing** - you configure it, you own the destination. See [08-07-00-agent-live-observability.md](08-07-00-agent-live-observability.md) for how this differs from the Foundry Portal's built-in server-side monitoring.

---

## OTel concepts

| Concept | Description |
|---------|-------------|
| Traces | Full journey of a request through the application - from the initial call to the final response, including all nested operations |
| Spans | Individual operations within a trace, each with a start time, end time, status, and nested child spans |
| Attributes | Key-value metadata attached to spans - model name, token counts, agent name, error classification |
| Semantic Conventions | Standardized OTel attribute names and formats (Microsoft + Cisco Outshift) that enable consistent querying across tools |
| Trace Exporters | Components that forward span data to a backend - in this lab, the Azure Monitor exporter sends to Application Insights |

---

## Multi-agent span hierarchy

When an agent handles a request, Foundry emits a nested span tree. The structure below shows the canonical hierarchy:

```
execute_task (root)
  └── invoke_agent
        ├── agent_to_agent_interaction  - agent-to-agent communication
        ├── agent.state.management      - memory/context management
        ├── agent_planning              - internal planning steps
        └── agent orchestration         - orchestration calls
               └── execute_tool
                     ├── tool.call.arguments
                     └── tool.call.results
```

Evaluation events appear as named spans with `name`, `error.type`, and `label` attributes - they are emitted inline within the trace rather than as separate telemetry records.

In the lab's single-agent pattern ([08-07-03-agent-observability.ipynb](08-07-03-agent-observability.ipynb)), you will typically see `responses`, `chat`, and MCP-tool spans (e.g. `mcp.tool.call`) rather than the full multi-agent hierarchy. A `create_agent` span only appears if the notebook itself creates a version - 08-07-03 reuses the agent from 08-05b, so its trace shows invocation spans only.

---

## Span attribute reference

These attributes appear on spans emitted by the `azure-ai-projects` SDK. They follow the GenAI OTel semantic conventions.

| Attribute | Example value | Description |
|-----------|--------------|-------------|
| `gen_ai.request.model` | `gpt-4.1-mini` | Model name requested |
| `gen_ai.usage.input_tokens` | `142` | Input token count for the operation |
| `gen_ai.usage.output_tokens` | `87` | Output token count for the operation |
| `gen_ai.system` | `az.ai.inference` | AI system identifier |
| `agent.name` | `aria-rm-briefing-agent` | Name of the agent that handled the request |
| `error.type` | `"rate_limit_exceeded"` | Error classification, present on error spans only |

Content attributes (`gen_ai.event.content` inside `traces`) are only populated when `AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING=true` is set **before** instrumentation.

---

## GA vs. preview status

Tracing support varies by agent type. Plan accordingly when building production observability pipelines.

| Agent type | Tracing status |
|------------|---------------|
| Prompt agents | GA |
| Workflow agents | Preview |
| Hosted agents | Preview |
| Custom agents | Preview |

---

## Cross-references

- [08-07-03-agent-observability.ipynb](08-07-03-agent-observability.ipynb) - working code demo: OTel setup, SDK instrumentation, `aria-rm-briefing-agent` invocation, App Insights KQL queries
- [08-07-00-agent-live-observability.md](08-07-00-agent-live-observability.md) - lab overview, infrastructure, key SDK pattern

---

## References

- [Agent Tracing Overview](https://learn.microsoft.com/azure/ai-foundry/observability/concepts/trace-agent-concept?view=foundry)
- [Set Up Tracing in Microsoft Foundry](https://learn.microsoft.com/azure/ai-foundry/observability/how-to/trace-agent-setup?view=foundry)
- [Tracing Integrations](https://learn.microsoft.com/azure/ai-foundry/observability/how-to/trace-agent-framework?view=foundry)
