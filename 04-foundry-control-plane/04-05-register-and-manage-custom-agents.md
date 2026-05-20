# Register and manage custom agents

The Foundry Control Plane supports registering agents that run outside of the Foundry Agent Service - including agents hosted on Azure compute, other cloud environments, or on-premises infrastructure. Registration routes traffic through the AI Gateway (Azure API Management), enabling observability and lifecycle operations without modifying the agent's existing implementation.

> **Note:** This capability is available only in the **Foundry (new)** portal (`ai.azure.com` with the New Foundry toggle enabled).

---

## What "custom agent" means

A custom agent is any agent not built and hosted natively in the Foundry Agent Service. This includes:

- Agents built with LangGraph, LangChain, or other orchestration frameworks
- Agents hosted on Azure Container Apps, Azure Kubernetes Service, or Azure Functions
- Agents running on-premises or in other cloud environments
- Agents exposing an HTTP or A2A protocol endpoint

After registration, Foundry generates a new proxy URL backed by API Management. Clients must use this new URL instead of the original endpoint.

---

## Prerequisites

- An Azure account with an active subscription
- A Foundry project
- An AI Gateway configured in the Foundry resource (uses Azure API Management; free to set up)
- An agent deployed and accessible via a reachable HTTP endpoint
- The agent's endpoint communicates via **HTTP** (general) or **A2A** (Agent-to-Agent protocol)
- (Optional) The agent emits telemetry using [OpenTelemetry semantic conventions for generative AI](https://opentelemetry.io/docs/specs/semconv/gen-ai/)

---

## Registration architecture

```
Client → AI Gateway (APIM proxy URL) → Custom Agent Endpoint
                ↓
       Application Insights (telemetry)
                ↓
       Foundry Control Plane (Assets inventory)
```

The original agent endpoint is not exposed directly to clients after registration. All traffic routes through the APIM-backed proxy URL.

---

## Step 1: Prepare your Foundry project

### Verify AI Gateway configuration

1. Sign in to [ai.azure.com](https://ai.azure.com). Confirm the **New Foundry** toggle is on.
2. Navigate to **Operate** → **Admin** tab
3. Open the **AI Gateway** section
4. Confirm an AI Gateway is listed for the Foundry resource
5. If not listed, select **Add AI Gateway** (setup is free)

### Verify Application Insights connection

1. Navigate to **Operate** → **Admin** tab
2. Under **All projects**, search for and select your project
3. Open the **Connected resources** tab
4. Confirm a resource in the **AppInsights** category is listed
5. If not present, select **Add connection** → **Application Insights**

> **Note:** If you add Application Insights after registering an agent, you must unregister and re-register the agent. The connection is not automatically updated.

---

## Step 2: Register the agent

1. Navigate to **Operate** → **Overview**
2. Select **Register agent**
3. Complete the **Agent properties** form:

**Table: Agent properties (step 3 of the registration form)**

| Property | Description | Required |
|----------|-------------|----------|
| **Agent URL** | The endpoint where the agent runs and receives requests. For agents using the OpenAI Chat Completions API, enter `https://<host>/v1/` without `/chat/completions` - clients append the path. | Yes |
| **Protocol** | Communication protocol: `HTTP` (general) or `A2A` (Agent-to-Agent protocol). | Yes |
| **A2A agent card URL** | Path to the agent card JSON spec. Default: `/.well-known/agent-card.json`. | No |
| **OpenTelemetry Agent ID** | The agent ID used to emit traces, found in the `gen_ai.agents.id` OTel attribute on spans with `operation="create_agent"`. If not specified, Foundry uses **Agent name** to find traces in Application Insights. | No |
| **Admin portal URL** | Administration URL for the agent's own management interface. Stored by Foundry for convenience only; Foundry does not access it. | No |

4. Complete the **Foundry Control Plane appearance** form:

**Table: Foundry Control Plane appearance properties (step 4 of the registration form)**

| Property | Description | Required |
|----------|-------------|----------|
| **Project** | The Foundry project under which the agent is registered. Must have an AI Gateway enabled in its resource. | Yes |
| **Agent name** | Display name in the Foundry Assets inventory. Used to match traces if no OpenTelemetry Agent ID is specified. | Yes |
| **Description** | Description of the agent's function. | No |

5. Select **Save**.
6. To verify: navigate to **Operate** → **Assets** → use the **Source** filter → select **Custom**.

---

## Step 3: Connect clients to the registered agent

After registration, Foundry generates a new proxy URL via APIM. Update all clients to use this URL.

1. In the Assets inventory, select the custom agent
2. Under **Agent URL**, select **Copy** to copy the new proxy URL
3. Replace the original endpoint with the new URL in all clients

The original authentication mechanism of the underlying agent still applies. Pass the same credentials when consuming the proxy URL.

**Example: LangGraph SDK client using the proxy URL (Python)**

```python
from langgraph_sdk import get_client

client = get_client(url="https://apim-my-foundry-resource.azure-api.net/my-custom-agent/")

async def stream_run():
    thread = await client.threads.create()
    input_data = {"messages": [{"role": "human", "content": "What is the weather in Seattle?"}]}

    async for chunk in client.runs.stream(
        thread["thread_id"],
        assistant_id="your_assistant_id",
        input=input_data
    ):
        print(chunk)
```

---

## Block and unblock the agent

Foundry cannot start or stop the underlying infrastructure for custom agents. It can, however, block or allow incoming requests via the gateway.

**To block:**

1. Navigate to **Operate** → **Assets**
2. Select the agent
3. Select **Update status** → **Block** → Confirm

After blocking, **Status** changes to **Blocked**. The agent's infrastructure continues running, but Foundry rejects all incoming requests at the gateway.

**To unblock:**

1. Select **Update status** → **Unblock** → Confirm

---

## Observability: enabling diagnostic data

The Control Plane uses OpenTelemetry to understand agent activity. With Application Insights configured, Foundry logs all requests by default and computes:

- Run count
- Error rate
- Token usage (if instrumentation provides it)

### View traces

1. Navigate to **Operate** → **Assets**
2. Select the agent
3. The **Traces** section displays one entry per HTTP call to the agent endpoint

### Instrument agents with LangChain (Python)

```bash
pip install -U "langchain-azure-ai[opentelemetry]"
```

```python
from langchain.agents import create_agent
from langchain_azure_ai.callbacks.tracers import AzureAIOpenTelemetryTracer

tracer = AzureAIOpenTelemetryTracer(
    connection_string="InstrumentationKey=<your-key>;...",
    enable_content_recording=True,
)

def get_weather(city: str) -> str:
    """Get weather for a given city."""
    return f"The weather in {city} is currently sunny."

agent = create_agent(
    model="openai:gpt-4.1-mini",
    tools=[get_weather],
    system_prompt="You are a helpful assistant.",
).with_config({"callbacks": [tracer]})
```

Pass the Application Insights connection string via the `APPLICATIONINSIGHTS_CONNECTION_STRING` environment variable to avoid hardcoding it.

### Instrument platform solutions (OpenTelemetry collector)

For agents that support OpenTelemetry but not Application Insights natively, deploy an OpenTelemetry collector with the Azure Monitor exporter. Reference: [Configure Azure Monitor OpenTelemetry](https://learn.microsoft.com/en-us/azure/azure-monitor/app/opentelemetry-configuration).

---

## Troubleshooting traces

If traces are not appearing in the Control Plane:

| Check | Detail |
|-------|--------|
| Application Insights configured | Project must have App Insights connected. If added after registration, unregister and re-register the agent. |
| Correct App Insights instance | The agent must send traces to the same App Insights resource connected to the Foundry project. |
| OTel conventions followed | Instrumentation must comply with [OpenTelemetry semantic conventions for generative AI](https://opentelemetry.io/docs/specs/semconv/gen-ai/). |
| Correct span attributes | Traces must include spans with `operation="create_agent"` and either `gen_ai.agents.id` or `gen_ai.agents.name` matching the registered agent name. |

---

## Resources

- [Register and manage custom agents (Microsoft Learn)](https://learn.microsoft.com/en-us/azure/ai-foundry/control-plane/register-custom-agent)
- [Foundry Control Plane overview](04-00-control-plane.md)
- [OpenTelemetry semantic conventions for generative AI](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
- [Configure Azure Monitor OpenTelemetry](https://learn.microsoft.com/en-us/azure/azure-monitor/app/opentelemetry-configuration)
- [langchain-azure-ai on PyPI](https://pypi.org/project/langchain-azure-ai/)

---

[Next: Publish agents to Teams and M365 Copilot →](04-06-publish-agents-teams-m365-copilot.md)
