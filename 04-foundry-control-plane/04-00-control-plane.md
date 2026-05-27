# Foundry Control Plane

## What is a control plane?

In cloud platforms, the *data plane* is where work actually runs - requests being processed, traffic being routed, models being invoked. The *control plane* is the management surface above it: the place where you configure what should happen, monitor what is happening, and govern who can do what.

For Foundry, the data plane is your agents in action: chatting with users, calling tools, retrieving data, generating responses. The **Foundry Control Plane** is the single surface where developers and operations teams see, govern, and act on those agents across the fleet - identity, policies, security, observability, costs - regardless of where each agent was built or which cloud it runs on.

The Control Plane is scoped to a Foundry resource - it surfaces agent activity and policy state across every project within that resource.

## In this chapter

| File | Description |
|------|-------------|
| [04-01-foundry-enterprise-provisioning.md](04-01-foundry-enterprise-provisioning.md) | Enterprise provisioning patterns, hub/spoke topology, RBAC, Bicep templates, and managed network configurations |
| [04-02-region-availability.md](04-02-region-availability.md) | Azure regions supporting Foundry resources, feature availability by region, and region selection guidance |
| [04-03-foundry-api-and-sdks.md](04-03-foundry-api-and-sdks.md) | Foundry SDK and REST API overview, language-specific package names, authentication, and key client classes |
| [04-04-foundry-costs.md](04-04-foundry-costs.md) | Cost components for Foundry resources, billing models, AI Gateway pricing, and cost optimisation guidance |
| [04-05-register-and-manage-custom-agents.md](04-05-register-and-manage-custom-agents.md) | Registering external (BYO) agents in the Control Plane via AI Gateway, lifecycle operations, and OTel instrumentation |
| [04-06-publish-agents-teams-m365-copilot.md](04-06-publish-agents-teams-m365-copilot.md) | Publishing Foundry agents to Microsoft Teams and Microsoft 365 Copilot, metadata requirements, and limitations |
| [04-07-foundry-for-vscode-extension.md](04-07-foundry-for-vscode-extension.md) | Installing and using the Foundry for Visual Studio Code extension: model catalog, playground, agent builder |
| [04-08-control-plane-customer-conversation.md](04-08-control-plane-customer-conversation.md) | Example customer conversation for introducing the Foundry Control Plane (Controls, Observability, Security, Fleet) |
| [04-09-foundry-control-plane-cheat-sheet.md](04-09-foundry-control-plane-cheat-sheet.md) | Quick-reference deep-links into the Foundry portal for live demos: guardrails, traces, evaluations, red-team runs, Defender alerts |

## Why agents need a control plane

Building an agent is easy. Running them at scale is the hard part. The teams that win with AI will not be running one chat agent - they will be running hundreds, then thousands, across call centres, decision routing, research workflows, and back-office automation, built in different frameworks and deployed across different clouds. When something goes wrong, signals scatter across tools, alerts arrive without context, and while you are investigating one agent, ten more are running.

Agents introduce categories of failure that traditional applications never had to think about. Every agent sits at the intersection of internal data, systems, and IP on one side, and the external world (the open internet, MCP tools, partner APIs, third-party content) on the other - and the power of an agent is that it can use both at once. The risk is also that it can use both at once:

- **Prompt injection**: untrusted content from a tool, document, or web page can hijack the agent's instructions and steer it toward actions no one intended.
- **Task drift**: the agent quietly stops doing what was asked and starts doing something else, sometimes with a destructive side effect.
- **Sensitive data leakage**: an agent with access to confidential data, a confused instruction, and an outbound channel is one wrong step away from exfiltration.

Connect more tools, more data, and more downstream agents into multi-agent workflows, and these risks do not grow linearly - they compound.

No single role inside an organisation owns this problem. Developers ship the agent. IT manages identity, access, and cost. Security looks for threats and protects data. Compliance defines what is permissible. They all touch the same agents and face the same risks, and they have historically lived in different tools. Trust is the multiplier: the teams that trust their agents are the ones that scale them.

Microsoft's approach has two halves that meet in the Control Plane:

1. **Treat agents as a new kind of identity.** Just like users and devices, agents need to be governed (identity, access, security posture, audit). The existing identity and security stack - Entra, Defender, Purview, Intune, Microsoft 365 - extends to cover them. This work is bundled under **Agent 365**.
2. **Build new defences for new risks.** Prompt injection, indirect injection, task drift, and agentic jailbreaks do not have a thirty-year toolkit behind them. They need purpose-built runtime controls and continuous evaluation, layered on top of traditional security to deliver defence in depth.

## What the Control Plane brings together

The Control Plane is organized around four essentials of running a trustworthy fleet:

- **Controls**: runtime guardrails on inputs, outputs, tool calls, and tool responses, covering task adherence, sensitive data detection, groundedness, prompt injection mitigation, and protected materials.
- **Observability**: built-in evaluators in the playground, OpenTelemetry tracing across prompt → model → tool, continuous evaluations against live production traffic, and the AI Red Teaming Agent (now generally available).
- **Security**: Microsoft Entra Agent ID for durable agent identity, Microsoft Defender for posture management and threat detection, Microsoft Purview for data protection and org-wide content safety policies.
- **Fleet-wide operations**: one view across Foundry-built agents (issued an Entra Agent ID at publish) and external agents brought in through AI Gateway, regardless of cloud or framework.

Crucially, the Control Plane keeps building and operating in the same flow. When an alert fires (a continuous evaluation drops below threshold, a jailbreak attempt is blocked by Prompt Shield, a compliance gap appears across the fleet), a developer can jump from the fleet view into the agent's build experience, refine the prompt, the tools, or the guardrails, and ship the fix without switching systems.

The feature is in **public preview**, accessible via the **Operate** tab at [ai.azure.com](https://ai.azure.com).

---

## Controls

The Control Plane supports policy-based guardrails that apply to agent inputs, outputs, and tool interactions.

### Control types

The following control types are available:

- **Task adherence**: checks that agent responses stay within defined task scope
- **Sensitive data detection**: identifies and blocks PII, credentials, or other sensitive content
- **Groundedness**: checks that responses are grounded in retrieved context
- **Prompt injection mitigation**: detects and blocks adversarial prompt injection attempts
- **Protected materials detection**: identifies content protected by intellectual property
- **Tool call filtering**: validates agent tool calls before execution (public preview)
- **Tool response validation**: validates tool responses before the agent processes them (public preview)

### Policy creation workflow

Policies are scoped to a subscription or resource group and can include exceptions for specific projects or agents.

1. Navigate to **Operate** → **Compliance** tab
2. Select **Create policy**
3. Choose the control type and configure thresholds
4. Set the policy scope (subscription or resource group)
5. Optionally add exceptions for specific resources
6. Save and activate the policy

### Compliance monitoring tabs

| Tab | Content |
|-----|---------|
| Overview | Policy coverage summary across the fleet |
| Active violations | Current policy violations and affected agents |
| History | Historical violation data and remediation records |
| Exceptions | Explicitly exempted agents or projects |

---

## Observability

### Instrumentation scope

Observability in the Control Plane is built on OpenTelemetry (OTel) semantic conventions for generative AI. Application Insights or Azure Monitor serves as the telemetry backend.

**Supported agent frameworks for automatic tracing:**
- Microsoft Agent Framework
- LangChain
- LangGraph

Custom agents can be instrumented manually using the `langchain-azure-ai` package (see [04-05-register-and-manage-custom-agents.md](04-05-register-and-manage-custom-agents.md)).

**OTel attributes used for agent identity:**
- `gen_ai.agents.id`: agent identifier
- `gen_ai.agents.name`: agent display name
- Spans with `operation="create_agent"` are correlated to the agent registry

### Monitoring dashboard surfaces

The Control Plane monitoring dashboard aggregates:

- Cost by agent and project
- Performance metrics (latency, error rate, throughput)
- Evaluation results
- Red teaming scan data
- OTel trace data

### Evaluations (public preview)

The built-in evaluator catalogue includes quality, risk, and safety evaluators. Custom evaluators can be created and registered.

**Planned GA capabilities:**
- Cloud-based evaluation execution
- Expanded evaluator collection
- Synthetic dataset generation
- Agent-specific evaluators: groundedness, task adherence, tool call accuracy

**Cluster analysis view:** Groups agent runs by behaviour pattern, surfacing anomalies and performance clusters without requiring manual labelling.

### Continuous evaluations

Evaluations can be configured to run continuously against production traffic, not just on discrete test runs.

### AI Red Teaming Agent

Status: **Generally available (GA)**. Provides no-code setup for automated red teaming scans against deployed agents.

---

## Security

### Microsoft Entra Agent ID

Foundry-built agents are issued a durable identity at build time via **Microsoft Entra Agent ID** (part of the Agent 365 infrastructure).

- The identity persists across deployments and is used for lineage tracking
- External agents connecting via AI Gateway acquire observability and access control without receiving a Foundry-issued identity
- Entra Agent ID enables policy-based access and conditional permissions

### Microsoft Defender integration

Defender provides the following capabilities within the Control Plane:

- **AI security posture management**: continuous assessment of agent configurations for security risks
- **Attack path analysis**: identifies potential attack chains involving deployed agents
- **Jailbreak detection**: alerts on adversarial prompts that bypass guardrails
- **Threat intelligence**: surfaces known threat patterns relevant to AI workloads

Security alerts from Defender surface in the Control Plane dashboard alongside observability data.

### Microsoft Purview integration

Purview provides:

- **Audit logging**: organisation-wide log of agent interactions for compliance records
- **Content safety policies**: org-level content safety configuration applied across all projects
- **Compliance remediation**: workflow for addressing identified compliance gaps

Purview compliance status is visible in the Control Plane Compliance tab.

### Third-party security integrations

- **Palo Alto Networks Prisma AIRS**: content safety, prompt injection blocking, malicious code detection
- **Zenity**: anomaly detection, policy enforcement, and inline prevention

---

## Fleet inventory

The Control Plane maintains a registry of agents associated with a Foundry resource. Agents appear in the **Assets** inventory under the **Operate** tab.

### Auto-discovered agent types

The following agent types are registered automatically when deployed within Foundry:

- **Foundry Agent Service agents**: agents built and deployed using the Foundry Agent Service
- **Azure SRE Agent**: site reliability engineering agents managed by Azure
- **Logic Apps agents**: agents orchestrated via Azure Logic Apps workflows

### Custom (BYO) agent registration

Agents hosted outside Foundry (on Azure compute, other clouds, or on-premises) can be registered manually. Registration routes traffic through the AI Gateway (Azure API Management), enabling observability and access control without modifying the agent's underlying implementation.

See [04-05-register-and-manage-custom-agents.md](04-05-register-and-manage-custom-agents.md) for the full registration procedure.

### Assets inventory columns

The Assets inventory table surfaces the following fields for each agent:

| Column | Description |
|--------|-------------|
| Name | Agent display name |
| Status | Active, Blocked, or error state |
| Source | Auto-discovered platform or Custom (BYO) |
| Project | Foundry project the agent is registered under |
| Health | Aggregated health signal from monitoring data |
| Cost | Token and compute cost aggregated from telemetry |
| Risk | Risk assessment from guardrail and security signals |
| Policy coverage | Whether guardrail policies are applied |

### Lifecycle operations per agent type

| Operation | Foundry agents | Custom agents |
|-----------|----------------|---------------|
| Block traffic | Yes | Yes (via gateway) |
| Unblock traffic | Yes | Yes |
| Delete registration | Yes | Yes |
| Start/stop infrastructure | Yes | No (Foundry cannot control external compute) |
| View traces | Yes (with App Insights) | Yes (with OTel instrumentation + App Insights) |

---

## AI Gateway

The AI Gateway is powered by Azure API Management (APIM) and acts as a proxy between clients and agents (both Foundry-native and custom).

### Roles of the AI Gateway

- Routes inference traffic to model deployments
- Applies token-per-minute (TPM) rate limits per deployment or subscription
- Manages total quota across multiple downstream consumers
- Proxies registered custom agents, enabling observability and access control
- Provides governance for MCP (Model Context Protocol) and A2A (Agent-to-Agent) tool calls

### TPM rate limiting

Rate limits are set per deployment in the AI Gateway configuration. The gateway enforces limits before requests reach the model, returning a `429 Too Many Requests` response when limits are exceeded.

### Setup steps

1. Navigate to **Operate** → **Admin** tab
2. Under **AI Gateway**, select the Foundry resource
3. Select **Add AI Gateway** if not yet configured
4. Configure rate limits and quota per project or deployment

### Pricing note

Setting up the AI Gateway is **free**. Standard Azure API Management request charges apply for traffic routed through the gateway. See [04-04-foundry-costs.md](04-04-foundry-costs.md) for full pricing details.

---

## Portal navigation

Access the Control Plane via the **Operate** tab at [ai.azure.com](https://ai.azure.com). The **New Foundry** toggle must be enabled.

| Tab | Location in portal | Content |
|-----|--------------------|---------|
| Overview | Operate → Overview | Fleet summary, agent registry, quick-register action |
| Assets | Operate → Assets | Agent inventory with status, cost, risk, and policy fields |
| Compliance | Operate → Compliance | Policy management, violation tracking, exception list |
| Quota | Operate → Quota | Per-deployment token quotas and rate limit configuration |
| Admin | Operate → Admin | AI Gateway configuration, Application Insights connections, project list |

---

## Related examples

| Section | Area | Example |
|---|---|---|
| [05 Project pattern setup](../05-foundry-project-pattern-setup/05-00-project-setup.md) | Hub/spoke + AI Gateway | [05-02-01-deploy-foundry-core-gateway.ipynb](../05-foundry-project-pattern-setup/05-02-deploy-foundry-core-gateway/05-02-01-deploy-foundry-core-gateway.ipynb) |
| [05 Project pattern setup](../05-foundry-project-pattern-setup/05-00-project-setup.md) | Multi-project topology | [05-04-01-deploy-foundry-multi-project.ipynb](../05-foundry-project-pattern-setup/05-04-deploy-foundry-multi-project/05-04-01-deploy-foundry-multi-project.ipynb) |
| [06 Governance policy](../06-governance-policy/06-00-governance-policy.md) | Governance policy deployment | [06-01-deploy-governance-policy.ipynb](../06-governance-policy/06-01-deploy-governance-policy.ipynb) |
| [08 Agents](../08-agents/08-00-what-is-an-agent.md) | Agent versioning and lifecycle | [08-01-create-versioned-storytelling-agent.ipynb](../08-agents/08-01-create-versioned-storytelling-agent.ipynb) |
| [08 Agents](../08-agents/08-00-what-is-an-agent.md) | Agent observability (OpenTelemetry) | [08-07-03-agent-observability.ipynb](../08-agents/08-07-agent-live-observability/08-07-03-agent-observability.ipynb) |
| [08 Agents](../08-agents/08-00-what-is-an-agent.md) | Custom MCP server + tool governance | [08-05-03-contoso-pmo-tool-catalog.ipynb](../08-agents/08-05-contoso-pmo-mcp/08-05-03-contoso-pmo-tool-catalog.ipynb) |
| [08 Agents](../08-agents/08-00-what-is-an-agent.md) | Agent offline evaluation | [08-06-05-results-and-portal.ipynb](../08-agents/08-06-agent-offline-evaluation/08-06-05-results-and-portal.ipynb) |
| [11 Foundry IQ multi-agent](../11-foundry-iq-multi-agent/11-00-foundry-iq-multi-agent.md) | Multi-agent fleet (Foundry IQ) | [11-05-multi-agent-queries.ipynb](../11-foundry-iq-multi-agent/11-05-multi-agent-queries.ipynb) |
| [14 Red teaming](../14-red-teaming/14-01-red-team-basics.ipynb) | AI Red Teaming | [14-01-red-team-basics.ipynb](../14-red-teaming/14-01-red-team-basics.ipynb) |

---

## Resources

- [Foundry Control Plane: Where Developers Build, Operate and Govern Every Agent](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/foundry-control-plane-where-developers-build-operate-and-govern-every-agent/4467885)

---

[Next: Foundry enterprise provisioning →](04-01-foundry-enterprise-provisioning.md)
