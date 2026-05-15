# Microsoft Foundry Control Plane

## From one agent to a fleet

A developer can build an agent in minutes. The hard part is everything that happens next. What actions is it taking? Is it staying on task? Is it leaking sensitive data? Are the guardrails actually firing? When something goes wrong, where do you start looking? Signals scatter across tools and clouds, alerts arrive without context, and root causes hide behind tangled traces. And while you are investigating one agent, ten more are running.

This is the shift happening across the industry: from agentic *conceptual* to agentic *operational*, from *"if"* and *"what"* to *"how many"*. The teams that win with AI will not be running one chat agent — they will be running hundreds, then thousands, across call centres, decision routing, research workflows, and back-office automation. Built in different frameworks, deployed across different clouds, owned by different teams.

That kind of scale exposes a trust gap that already exists. Customers see the potential, but they also see the headlines, and most people say they are more worried about AI agents than confident in them. The honest question is: **do we trust these agents enough to scale them?** Trust is the multiplier — the teams that trust their agents are the ones that scale them, and the teams that scale effectively are the ones that win.

## Why agents are a different problem

Every agent sits at an intersection. On one side, the organization's internal data, systems, and IP — the unique value the business brings. On the other, the external world — the open internet, MCP tools, partner APIs, and third-party content. The power of an agent is that it can use both at once. The risk is also that it can use both at once.

That intersection introduces categories of failure that traditional applications never had to think about:

- **Prompt injection** — untrusted content from a tool, document, or web page can hijack the agent's instructions and steer it toward actions no one intended.
- **Task drift** — the agent quietly stops doing what was asked and starts doing something else. The consequence might be a few wasted tokens, or it might be a destructive side effect.
- **Sensitive data leakage** — an agent with access to confidential data, a confused instruction, and an outbound channel is one wrong step away from exfiltration.

Connect more tools, more data, and more downstream agents into multi-agent workflows, and these risks do not grow linearly. They compound.

## Trust is a team sport

No single role inside an organization owns this problem. Developers ship the agent. IT manages identity, access, and cost. Security looks for threats and protects data. Compliance defines what is permissible. They all touch the same agents and face the same risks, and they have historically lived in different tools.

Microsoft's approach has two halves that meet in the Control Plane:

1. **Treat agents as a new kind of identity.** Just like users and devices, agents need to be governed — identity, access, security posture, audit. The existing identity and security stack — Entra, Defender, Purview, Intune, Microsoft 365 — extends to cover them. This work is bundled under **Agent 365**.
2. **Build new defences for new risks.** Prompt injection, indirect injection, task drift, and agentic jailbreaks do not have a thirty-year toolkit behind them. They need purpose-built runtime controls and continuous evaluation, layered on top of traditional security to deliver defence in depth.

The **Foundry Control Plane** is the operational and governance surface of Azure AI Foundry — the single place where developer and operations teams see, govern, and act on every agent in the estate, regardless of where it was built.

## What the Control Plane brings together

The Control Plane is organized around four essentials of running a trustworthy fleet:

- **Controls** — runtime guardrails on inputs, outputs, tool calls, and tool responses, covering task adherence, sensitive data detection, groundedness, prompt injection mitigation, and protected materials.
- **Observability** — built-in evaluators in the playground, OpenTelemetry tracing across prompt → model → tool, continuous evaluations against live production traffic, and the AI Red Teaming Agent (now generally available).
- **Security** — Microsoft Entra Agent ID for durable agent identity, Microsoft Defender for posture management and threat detection, Microsoft Purview for data protection and org-wide content safety policies.
- **Fleet-wide operations** — one view across Foundry-built agents (issued an Entra Agent ID at publish) and external agents brought in through AI Gateway, regardless of cloud or framework.

Crucially, the Control Plane keeps building and operating in the same flow. When an alert fires — a continuous evaluation drops below threshold, a jailbreak attempt is blocked by Prompt Shield, a compliance gap appears across the fleet — a developer can jump from the fleet view into the agent's build experience, refine the prompt, the tools, or the guardrails, and ship the fix without switching systems.

The feature is in **public preview**, accessible via the **Operate** tab at [ai.azure.com](https://ai.azure.com).

**Primary source:** [Foundry Control Plane — Where Developers Build, Operate and Govern Every Agent](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/foundry-control-plane-where-developers-build-operate-and-govern-every-agent/4467885)

---

## Directory Contents

| File | Description |
|------|-------------|
| [04-01-foundry-enterprise-provisioning.md](04-01-foundry-enterprise-provisioning.md) | Enterprise provisioning patterns, hub/spoke topology, RBAC, Bicep templates, and managed network configurations |
| [04-02-region-availability.md](04-02-region-availability.md) | Azure regions supporting Foundry resources, feature availability by region, and region selection guidance |
| [04-03-foundry-api-and-sdks.md](04-03-foundry-api-and-sdks.md) | Foundry SDK and REST API overview, language-specific package names, authentication, and key client classes |
| [04-04-foundry-costs.md](04-04-foundry-costs.md) | Cost components for Foundry resources, billing models, AI Gateway pricing, and cost optimisation guidance |
| [04-05-register-and-manage-custom-agents.md](04-05-register-and-manage-custom-agents.md) | Registering external (BYO) agents in the Control Plane via AI Gateway, lifecycle operations, and OTel instrumentation |
| [04-06-publish-agents.md](04-06-publish-agents.md) | Publishing Foundry agents to Microsoft Teams and Microsoft 365 Copilot, metadata requirements, and limitations |
| [04-07-foundry-for-vscode-extension.md](04-07-foundry-for-vscode-extension.md) | Installing and using the Foundry for Visual Studio Code extension: model catalog, playground, agent builder |
| [04-08-control-plane-customer-conversation.md](04-08-control-plane-customer-conversation.md) | Toastmasters-style customer conversation script for introducing the Foundry Control Plane (Controls, Observability, Security, Fleet) |
| [04-09-foundry-control-plane-cheat-sheet.md](04-09-foundry-control-plane-cheat-sheet.md) | Quick-reference deep-links into the Foundry portal for live demos: guardrails, traces, evaluations, red-team runs, Defender alerts |

---

## Section 5a — What is the Foundry Control Plane?

The Foundry Control Plane provides a unified operational surface for agents built on or registered with Azure AI Foundry. It is hosted at [ai.azure.com](https://ai.azure.com) and accessed via the **Operate** tab in the portal.

**Relationship to hub/spoke topology:**
- A Foundry resource (hub) hosts model deployments, connections, and gateway configuration.
- Projects (spokes) are scoped workloads within a resource that inherit gateway and observability settings.
- The Control Plane surfaces agent activity and policy state across all projects within a resource.

**Status:** Public preview. Not all features are generally available; see individual sections for GA status.

**Four core pillars of the Control Plane:**

| Pillar | Function |
|--------|----------|
| Controls | Guardrails applied to agent inputs, outputs, tool calls, and tool responses |
| Observability | Tracing, evaluation, monitoring, and behaviour analysis across agents |
| Security | Integrations with Defender, Purview, and Entra for identity and compliance |
| Fleet-wide Operations | Unified lifecycle management across agents regardless of hosting platform |

---

## Section 5b — Agent Registry and Fleet Inventory

The Control Plane maintains a registry of agents associated with a Foundry resource. Agents appear in the **Assets** inventory under the **Operate** tab.

### Auto-discovered agent types

The following agent types are registered automatically when deployed within Foundry:

- **Foundry Agent Service agents** — agents built and deployed using the Foundry Agent Service
- **Azure SRE Agent** — site reliability engineering agents managed by Azure
- **Logic Apps agents** — agents orchestrated via Azure Logic Apps workflows

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

## Section 5c — Controls and Guardrail Policies

The Control Plane supports policy-based guardrails that apply to agent inputs, outputs, and tool interactions.

### Control types

The following control types are available:

- **Task adherence** — checks that agent responses stay within defined task scope
- **Sensitive data detection** — identifies and blocks PII, credentials, or other sensitive content
- **Groundedness** — checks that responses are grounded in retrieved context
- **Prompt injection mitigation** — detects and blocks adversarial prompt injection attempts
- **Protected materials detection** — identifies content protected by intellectual property
- **Tool call filtering** — validates agent tool calls before execution (public preview)
- **Tool response validation** — validates tool responses before the agent processes them (public preview)

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

## Section 5d — Observability

### Instrumentation scope

Observability in the Control Plane is built on OpenTelemetry (OTel) semantic conventions for generative AI. Application Insights or Azure Monitor serves as the telemetry backend.

**Supported agent frameworks for automatic tracing:**
- Microsoft Agent Framework
- LangChain
- LangGraph

Custom agents can be instrumented manually using the `langchain-azure-ai` package (see [04-05-register-and-manage-custom-agents.md](04-05-register-and-manage-custom-agents.md)).

**OTel attributes used for agent identity:**
- `gen_ai.agents.id` — agent identifier
- `gen_ai.agents.name` — agent display name
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

## Section 5e — AI Gateway Integration

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

## Section 5f — Security Integrations

### Microsoft Entra Agent ID

Foundry-built agents are issued a durable identity at build time via **Microsoft Entra Agent ID** (part of the Agent 365 infrastructure).

- The identity persists across deployments and is used for lineage tracking
- External agents connecting via AI Gateway acquire observability and access control without receiving a Foundry-issued identity
- Entra Agent ID enables policy-based access and conditional permissions

### Microsoft Defender integration

Defender provides the following capabilities within the Control Plane:

- **AI security posture management** — continuous assessment of agent configurations for security risks
- **Attack path analysis** — identifies potential attack chains involving deployed agents
- **Jailbreak detection** — alerts on adversarial prompts that bypass guardrails
- **Threat intelligence** — surfaces known threat patterns relevant to AI workloads

Security alerts from Defender surface in the Control Plane dashboard alongside observability data.

### Microsoft Purview integration

Purview provides:

- **Audit logging** — organisation-wide log of agent interactions for compliance records
- **Content safety policies** — org-level content safety configuration applied across all projects
- **Compliance remediation** — workflow for addressing identified compliance gaps

Purview compliance status is visible in the Control Plane Compliance tab.

### Third-party security integrations

- **Palo Alto Networks Prisma AIRS** — content safety, prompt injection blocking, malicious code detection
- **Zenity** — anomaly detection, policy enforcement, and inline prevention

---

## Section 5g — Navigation Reference

Access the Control Plane via the **Operate** tab at [ai.azure.com](https://ai.azure.com). The **New Foundry** toggle must be enabled.

| Tab | Location in portal | Content |
|-----|--------------------|---------|
| Overview | Operate → Overview | Fleet summary, agent registry, quick-register action |
| Assets | Operate → Assets | Agent inventory with status, cost, risk, and policy fields |
| Compliance | Operate → Compliance | Policy management, violation tracking, exception list |
| Quota | Operate → Quota | Per-deployment token quotas and rate limit configuration |
| Admin | Operate → Admin | AI Gateway configuration, Application Insights connections, project list |

---

## Section 5h — Examples in This Repository

| Area | Example |
|------|---------|
| Hub/spoke + AI Gateway | [deploy-foundry-core-gateway.ipynb](../05-foundry-project-pattern-setup/05-02-deploy-foundry-core-gateway/deploy-foundry-core-gateway.ipynb) |
| Multi-project topology | [deploy-foundry-multi-project.ipynb](../05-foundry-project-pattern-setup/05-04-deploy-foundry-multi-project/deploy-foundry-multi-project.ipynb) |
| Agent versioning and lifecycle | [08-01-create-versioned-storytelling-agent.ipynb](../08-agents/08-01-create-versioned-storytelling-agent.ipynb) |
| Agent observability (OpenTelemetry) | [08-07-03-agent-observability.ipynb](../08-agents/08-07-agent-live-observability/08-07-03-agent-observability.ipynb) |
| Governance policy deployment | [06-01-deploy-governance-policy.ipynb](../06-governance-policy/06-01-deploy-governance-policy.ipynb) |
| Custom MCP server + tool governance | [08-05-03-contoso-pmo-tool-catalog.ipynb](../08-agents/08-05-contoso-pmo-mcp/08-05-03-contoso-pmo-tool-catalog.ipynb) |
| Agent offline evaluation | [08-06-05-results-and-portal.ipynb](../08-agents/08-06-agent-offline-evaluation/08-06-05-results-and-portal.ipynb) |
| AI Red Teaming | [main.ipynb](../14-red-teaming/main.ipynb) |
| Multi-agent fleet (Foundry IQ) | [11-05-multi-agent-queries.ipynb](../11-foundry-iq-multi-agent/11-05-multi-agent-queries.ipynb) |

---

## Section 5i — Proposed Examples (not yet implemented)

The following labs are candidates for future implementation in this repository:

- Custom agent registration via REST API and portal walkthrough
- Token rate limit enforcement: demonstrating `429` responses and client-side retry handling
- Guardrail policy creation and violation: end-to-end policy trigger and alert demonstration
- OpenTelemetry trace correlation: linking agent spans to the Control Plane Assets view
- Continuous evaluation pipeline: configuring evaluations against live production traffic
- Entra Agent ID inspection: retrieving and verifying the durable identity issued to a Foundry agent
- AI Gateway usage report: querying APIM telemetry for per-agent token and request metrics
