# Real-Time Observability — Foundry Portal Monitor Tab

Covers the Foundry Portal's built-in agent monitoring surface: portal navigation, dashboard metrics, Monitor Settings, and its relationship to client-side OTel tracing.

## Overview

The Agent Monitoring Dashboard is **server-side observability built into the Foundry Portal** — it requires no client instrumentation. Foundry captures traffic for any agent invocation and surfaces metrics, evaluation scores, and red team results in a dedicated Monitor tab.

This is distinct from the client-side OTel tracing demonstrated in [08-07-03-agent-observability.ipynb](08-07-03-agent-observability.ipynb), where you configure the exporter and own the destination. The two approaches are complementary — see [Relationship to Application Insights](#relationship-to-application-insights) below.

---

## Portal Navigation

### Standard agents (prompt, workflow)

1. Sign in to `https://ai.azure.com` — confirm the **New Foundry** toggle is on (top-right)
2. Navigate to **Build** page
3. Select your agent from the agent list
4. Select the **Monitor** tab

### Custom agents

1. Open **Foundry Control Plane** in the left navigation
2. Select **Asset** page
3. Select your agent
4. Select the **Monitor** tab

---

## Dashboard Metrics

The Monitor tab displays the following metrics for a configurable time range:

| Metric | Description | Threshold guidance |
|--------|-------------|-------------------|
| Token usage | Token counts for agent traffic in the selected time range | — |
| Latency | Response time per run | >10s suggests throttling, complex tools, or network issues |
| Run success rate | Percentage of runs that completed without error | <95% warrants investigation |
| Evaluation metrics | Scores from evaluators running continuously on sampled outputs | Depends on evaluator; see Monitor Settings |
| Red teaming results | Outcomes from scheduled adversarial scans | — |

---

## Monitor Settings

Four configurable features are available under **Monitor Settings** for each agent:

| Feature | Purpose | Status |
|---------|---------|--------|
| Continuous evaluation | Always-on quality and safety checks on sampled agent responses, configured via the Python SDK | GA |
| Scheduled evaluations | Scheduled eval runs against benchmark datasets | Preview |
| Red team scans | Adversarial tests for data leakage and prohibited actions | Preview |
| Alerts | Anomaly detection for latency, token usage, eval scores, and red team results | Preview |

Continuous evaluation is the only Monitor Settings feature available in GA. See [08-07-05-agent-continuous-evaluation.ipynb](08-07-05-agent-continuous-evaluation.ipynb) for the Python SDK setup.

---

## Relationship to Application Insights

Both the portal dashboard and client-side OTel traces write to the **same Application Insights instance** (`appi-obs-{suffix}` in this lab). They are complementary:

| Surface | What it shows | Who configures it |
|---------|--------------|-------------------|
| Foundry Portal Monitor tab | Server-side metrics, eval scores, red team results | Foundry (automatic) |
| Application Insights / KQL | Full span-level traces, token counts, content events | You — via `AIProjectInstrumentor` |

Use the portal for a quick operational view; use App Insights for correlation with the rest of your application's telemetry or for custom KQL queries.

---

## Cross-References

- [08-07-05-agent-continuous-evaluation.ipynb](08-07-05-agent-continuous-evaluation.ipynb) — Python SDK setup for continuous evaluation; also shows how to navigate to the Monitor tab to verify results
- [08-07-03-agent-observability.ipynb](08-07-03-agent-observability.ipynb) — client-side OTel instrumentation pattern
- [08-07-00-agent-live-observability.md](08-07-00-agent-live-observability.md) — lab overview

---

## References

- [Agent Monitoring Dashboard](https://learn.microsoft.com/azure/ai-foundry/observability/how-to/how-to-monitor-agents-dashboard?view=foundry)
- [Agent Tracing Overview](https://learn.microsoft.com/azure/ai-foundry/observability/concepts/trace-agent-concept?view=foundry)
