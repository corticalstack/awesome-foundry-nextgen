# Azure AI Foundry: Enterprise Provisioning & RBAC Guide

This guide introduces teams new to Azure AI Foundry to the essential Azure infrastructure concepts, enterprise provisioning patterns, and Role-Based Access Control (RBAC) model needed to deploy and govern Foundry workloads at scale. It uses a **greenfield Foundry resource** lens (new architecture) throughout. No hub-based content is included. The intended audience is developers and enterprise architects responsible for provisioning and governing AI infrastructure.

## Table of Contents

- [1. Azure Management Hierarchy](#1-azure-management-hierarchy)
- [2. Subscriptions](#2-subscriptions)
- [3. Resource Groups](#3-resource-groups)
- [4. Foundry Resource Architecture](#4-foundry-resource-architecture)
  - [Foundry Resource](#foundry-resource)
  - [Foundry Project](#foundry-project)
  - [What is Shared vs Isolated](#what-is-shared-vs-isolated)
- [5. Enterprise Provisioning Patterns](#5-enterprise-provisioning-patterns)
  - [Pattern A: One Resource, One Project](#pattern-a-one-resource-one-project)
  - [Pattern B: One Resource, Multiple Projects](#pattern-b-one-resource-multiple-projects)
  - [Pattern C: Multiple Resources, Multiple Projects](#pattern-c-multiple-resources-multiple-projects)
  - [Pattern D: Environment Separation](#pattern-d-environment-separation)
  - [Decision Guide](#decision-guide)
  - [Connection Scoping](#connection-scoping)
- [6. Role-Based Access Control](#6-role-based-access-control)
  - [What is RBAC](#what-is-rbac)
  - [Built-in Foundry Roles](#built-in-foundry-roles)
    - [Azure AI User](#azure-ai-user)
    - [Azure AI Project Manager](#azure-ai-project-manager)
    - [Azure AI Account Owner](#azure-ai-account-owner)
    - [Azure AI Owner](#azure-ai-owner)
    - [Standard Azure Roles](#standard-azure-roles)
  - [Role Permissions Summary](#role-permissions-summary)
  - [Enterprise RBAC Assignment Matrix](#enterprise-rbac-assignment-matrix)
  - [RBAC Best Practices](#rbac-best-practices)
- [7. Network Isolation](#7-network-isolation)
- [8. Azure Policy Governance](#8-azure-policy-governance)
  - [Built-in Policy Definitions](#built-in-policy-definitions)
  - [Model Deployment Control](#model-deployment-control)
- [9. Cost Management](#9-cost-management)
  - [Billing Models](#billing-models)
  - [Cost Attribution](#cost-attribution)
  - [TPM Management and AI Gateway](#tpm-management-and-ai-gateway)
  - [Cost Optimization Strategies](#cost-optimization-strategies)
  - [Monitoring and Metrics](#monitoring-and-metrics)
- [10. Infrastructure as Code](#10-infrastructure-as-code)
  - [Terraform](#terraform)
  - [Bicep](#bicep)
- [11. CI/CD Integration](#11-cicd-integration)
- [12. Additional Resources](#12-additional-resources)

---

## 1. Azure Management Hierarchy

Azure organises resources into a four-level management hierarchy. Understanding this hierarchy is essential for applying governance, policies, and RBAC at the right scope.

```
Management Groups
└── Subscriptions
    └── Resource Groups
        └── Resources
```

**Management Groups** are optional containers that sit above subscriptions. They enable you to apply Azure Policy and RBAC across multiple subscriptions in a single operation. Enterprises typically create management groups aligned to business units, regulatory domains, or workload types. Policy and RBAC assigned at a management group scope **inherit downward** to all subscriptions and resources within it.

**Subscriptions** are billing and isolation boundaries (covered in detail in [Section 2](#2-subscriptions)).

**Resource Groups** are logical containers for deploying and managing related Azure resources as a lifecycle unit (covered in detail in [Section 3](#3-resource-groups)).

**Resources** are the individual Azure services you provision — in the context of this guide, a Foundry resource or Foundry project.

> The Azure Cloud Adoption Framework (CAF) AI scenario guidance, updated January 2026, recommends creating separate management groups for internet-facing and internal AI workloads to enforce data governance boundaries via policy inheritance. It also recommends deploying AI resources in workload-specific subscriptions within application landing zones, rather than in platform subscriptions.

---

## 2. Subscriptions

An Azure **subscription** serves three distinct purposes simultaneously: it is your **billing boundary** (all charges in a subscription appear on a single invoice), your **management boundary** (subscription-level Azure Policy and RBAC apply to everything within it), and your **quota boundary** (Azure resource and service quotas are tracked per subscription per region).

### Subscription Considerations for Foundry

**One subscription is often enough for small teams**, but enterprises typically adopt a subscription-per-environment or subscription-per-workload model. Key drivers for creating separate subscriptions include:

- **Billing separation**: Different teams, cost centres, or business units need independent invoices.
- **Quota isolation**: Model deployment Tokens Per Minute (TPM) quotas are tracked per subscription per region. High-volume workloads can exhaust quota, blocking other teams in the same subscription.
- **Blast radius**: Isolating production workloads from development workloads in separate subscriptions prevents a misconfiguration or resource exhaustion in one environment from affecting the other.
- **Policy divergence**: Development environments often require looser policies (e.g., public network access allowed) while production requires strict controls (private endpoints only, CMK encryption). Separate subscriptions make applying different policy sets straightforward.

> CAF guidance: Deploy AI resources in workload-specific subscriptions within **application landing zones**, not in shared platform subscriptions. This preserves platform subscription stability and enables workload teams to manage their own governance settings.

### Subscription Quota

Azure OpenAI and Foundry model deployments consume **Tokens Per Minute (TPM) quota** that is scoped to a subscription + region combination. Before designing your provisioning topology, check current quota availability in your target regions at *ai.azure.com → Management → Quota*. Quota increase requests are submitted via the Azure portal and may take several business days to process for certain models and regions.

---

## 3. Resource Groups

A **resource group** is a logical container that holds related Azure resources. All resources in a resource group share a **lifecycle** — when you delete the resource group, all resources inside it are deleted. Resource groups also serve as the default scope for Azure Cost Management views and for many RBAC assignments.

### Resource Group Best Practices for Foundry

- **Group by lifecycle, not by type.** A Foundry resource and the resources it depends on (e.g., an Azure API Management instance for AI Gateway, a Log Analytics workspace) should be in the same resource group so they can be managed and deleted together.
- **One resource group per environment per workload** is a common baseline. For example: `rg-foundry-payments-dev`, `rg-foundry-payments-prod`.
- **Tags are your friend.** Apply consistent tags (e.g., `environment`, `team`, `cost-centre`, `workload`) to the resource group so that Azure Cost Management can filter and allocate charges accurately.
- **Resource group region does not constrain resource region.** The resource group's location only stores metadata; Foundry resources inside it can be in any Azure region.

---

## 4. Foundry Resource Architecture

Microsoft Foundry uses a **two-level hierarchy**: a **Foundry resource** (the account-level container) contains one or more **Foundry projects** (the workspace-level containers where AI applications are built and operated).

### Foundry Resource

The Foundry resource is the top-level Azure resource. It is provisioned in your subscription and resource group and carries the settings that govern all projects beneath it: networking configuration, RBAC assignments, Azure Policy applicability, and model deployment quotas.

| Property | Value |
|---|---|
| Azure resource type | `Microsoft.CognitiveServices/accounts` |
| Kind | `AIServices` |
| Scope | Subscription / Resource Group |

**Storage and Key Vault in the new architecture**: The Foundry resource does **not** automatically provision a Storage Account or Key Vault in your subscription. The new architecture uses **Microsoft-managed storage** for project data (threads, messages, files) and a **Microsoft-managed Key Vault** for connection secrets by default. This is a deliberate design choice that reduces resource sprawl and operational overhead for most workloads. If you require full control over data residency or secret management, you can optionally bring your own storage account (BYOS) or your own Key Vault (BYKV) — these are opt-in configurations, not defaults.

### Foundry Project

A Foundry project is a **child resource** of the Foundry resource. Because it is a child resource (not a sibling), it inherits all governance settings from the parent — networking isolation, Azure Policy assignments, and most RBAC assignments — without requiring separate configuration.

| Property | Value |
|---|---|
| Azure resource type | `Microsoft.CognitiveServices/accounts/project` |
| Kind | `AIServices` |
| Scope | Child of Foundry resource |

Projects are the workspaces where teams build AI applications. Each project has its own:
- Agent definitions and deployment history
- Connections (API keys, endpoints) scoped to that project
- Evaluation runs and metrics
- Build, Operate, and Admin console views in the portal

### What is Shared vs Isolated

| Capability | Shared across projects | Isolated per project |
|---|---|---|
| Network configuration (VNet, private endpoints) | Yes — set at Foundry resource level | No |
| Azure Policy assignments | Yes — inherited from Foundry resource | No |
| Model deployments | Yes — deployed at resource level, accessible to all projects | No |
| RBAC (resource-level assignments) | Yes — resource-level roles apply to all projects | No |
| RBAC (project-level assignments) | No | Yes — project-scoped roles are isolated |
| Connections (resource-scoped) | Yes — all projects can use them | No |
| Connections (project-scoped) | No | Yes — visible only to the owning project |
| Agent definitions | No | Yes |
| Evaluation history | No | Yes |
| Data storage (default managed) | No | Yes — Microsoft-managed logical separation per project |
| Fine-tuned model deployments | No | Yes |

---

## 5. Enterprise Provisioning Patterns

Choosing the right provisioning topology before you start building avoids costly restructuring later. The patterns below are ordered from simplest to most complex.

### Pattern A: One Resource, One Project

> Avoid this pattern for any workload that will grow beyond a single team or use case.

**Structure:** One Foundry resource → one Foundry project.

**Suitable for:** Proof-of-concept work, individual experimentation, or transient demos.

**Problems at scale:**
- No isolation between teams or workloads — everyone shares the same project namespace.
- RBAC becomes coarse-grained; you cannot give one team access without giving all teams access.
- Model deployment quota is consumed by a single project, creating contention.
- Impossible to enforce per-team cost attribution without external tagging hacks.

### Pattern B: One Resource, Multiple Projects

**Structure:** One Foundry resource → multiple Foundry projects (one per team, use case, or product).

**Suitable for:** Small-to-medium enterprises with a single AI platform team managing a shared Foundry resource on behalf of multiple product teams.

**Benefits:**
- Strong isolation between teams at the project layer — RBAC, connections, and agent definitions are all project-scoped.
- Shared model deployments reduce redundant quota consumption across teams using the same models.
- Centralised governance: networking, policy, and resource-level RBAC managed once.
- Cost attribution is possible via the Foundry portal per-project cost tile.

**Limitations:**
- All projects share the same quota pool — a quota burst in one project can affect others.
- Networking settings (e.g., VNet isolation mode) are shared; you cannot apply different network topologies to different projects.
- A single Foundry resource creates a single point of failure — regional outages or misconfiguration affect all teams simultaneously.

### Pattern C: Multiple Resources, Multiple Projects

**Structure:** Multiple Foundry resources (one per team, department, or business unit) → each with one or more Foundry projects.

**Suitable for:** Enterprises with multiple business units, regulatory data separation requirements, or teams needing independent networking configurations.

**Benefits:**
- Full isolation at every level: quota, networking, RBAC, and data.
- Independent governance per team — each BU can own their Foundry resource and configure it to their requirements.
- Regional distribution is natural — each resource can be provisioned in the region optimal for its workload.
- Blast radius is contained to the resource boundary.

**Limitations:**
- Higher operational overhead — each resource requires independent management.
- No shared model deployments across resources; each resource has its own quota consumption.
- Azure subscription quota limits may constrain how many resources can be provisioned in a single subscription (consider Pattern D for environment isolation alongside this pattern).

### Pattern D: Environment Separation

**Structure:** Replicate Pattern B or C across separate subscriptions for each environment (dev, test, prod).

**Suitable for:** Any workload moving toward production.

**Benefits:**
- Hard blast-radius boundary between environments — a misconfiguration in dev cannot impact prod.
- Separate Azure Policy sets per environment (loose in dev, strict in prod).
- Independent quota pools per environment.
- Subscription-level cost separation provides clean billing per environment.
- Enables testing policy and RBAC changes in lower environments before applying to prod.

**Implementation approach:** Use Infrastructure as Code (see [Section 10](#10-infrastructure-as-code)) to parameterise the environment differences and deploy the same topology to each subscription. Use CI/CD pipeline gates (see [Section 11](#11-cicd-integration)) to control promotion from dev → test → prod.

### Decision Guide

| Scenario | Recommended Pattern |
|---|---|
| Single team, PoC or experimentation | Pattern A (short-term only) |
| Single AI platform team, multiple product teams | Pattern B |
| Multiple business units with independent governance needs | Pattern C |
| Any workload approaching production | Pattern D (layered with B or C) |
| Regulatory data separation required between teams | Pattern C + Pattern D |
| Multi-region deployment for latency or DR | Pattern C (one resource per region per BU) |

### Connection Scoping

Connections in Foundry (API endpoints, API keys, storage references) can be scoped at two levels:

- **Resource-scoped connections**: Visible to all projects in the Foundry resource. Use for shared services that all teams can access — for example, a shared Azure AI Search index or a shared Azure Cosmos DB instance.
- **Project-scoped connections**: Visible only to the owning project. Use for team-specific or workload-specific services that should not be discoverable or accessible by other teams.

> As a rule of thumb, scope connections at the most restrictive level that meets your sharing requirements. Start with project-scoped connections and elevate to resource-scoped only when cross-project sharing is explicitly required.

---

## 6. Role-Based Access Control

### What is RBAC

**Role-Based Access Control (RBAC)** is the Azure mechanism for authorising principals (users, groups, service principals, managed identities) to perform actions on resources. An RBAC assignment combines three elements: a **principal** (who), a **role definition** (what actions are allowed), and a **scope** (which resources).

In Azure AI Foundry, there are two categories of actions:

- **Control plane actions** (`Actions` in role definitions): Management operations such as creating projects, deploying models, configuring connections, and assigning roles. These are governed by Azure Resource Manager (ARM).
- **Data plane actions** (`DataActions` in role definitions): Runtime operations such as calling model inference endpoints, creating agents, submitting evaluations, and reading conversation history. These are governed by the Foundry resource provider directly.

Standard Azure roles (Owner, Contributor, Reader) only cover control plane actions. They do **not** grant data plane access to Foundry resources. Foundry-specific built-in roles cover both planes or data plane only, depending on the role.

### Built-in Foundry Roles

Azure AI Foundry ships four purpose-built RBAC roles aligned to the new Foundry resource architecture. All four are confirmed current as of February 2026.

#### Azure AI User

**Role Definition ID:** `53ca6127-db72-4b80-b1b0-d745d6d5456d`

**Purpose:** Grants a principal the ability to build within a Foundry project — use models, create and run agents, submit evaluations, and interact with the full data plane. Does not grant any management capabilities.

**Control plane (Actions):**
- `Microsoft.CognitiveServices/*/read` — read resource and project metadata
- `Microsoft.CognitiveServices/accounts/listkeys/action` — list API keys (Note: key-based auth bypasses RBAC; Entra ID auth is preferred)

**Data plane (DataActions):**
- `Microsoft.CognitiveServices/*` — full data plane wildcard (all inference, agent, evaluation, and storage operations)

**Assign at:** Project scope to limit a developer to a single project. Assigning at resource scope grants the same data plane access to all projects in the resource.

**Cannot:** Create projects, deploy models, configure connections, or assign roles to others.

#### Azure AI Project Manager

**Role Definition ID:** `eadc314b-1a2d-4efa-be10-5d325db5065e`

**Purpose:** Grants a principal the ability to manage Foundry projects within a resource — create, update, and delete projects, and assign the Azure AI User role to other principals within their projects. Project Managers retain full data plane access and can build within projects themselves, not just administrate them.

**Control plane (Actions):**
- `Microsoft.CognitiveServices/accounts/projects/*` — full project CRUD
- `Microsoft.Authorization/roleAssignments/write` and `delete` (ABAC-conditioned to Azure AI User role only — cannot escalate permissions)

**Data plane (DataActions):**
- `Microsoft.CognitiveServices/*` — full data plane wildcard

**Assign at:** Resource scope (to manage all projects in a resource) or project scope (to manage a single project).

**Cannot:** Deploy models, configure resource-level connections, manage networking, or assign roles beyond Azure AI User.

#### Azure AI Account Owner

**Role Definition ID:** `e47c6f54-e4a2-4754-9501-8e0985b135e1`

**Purpose:** Grants a principal full control plane access to a Foundry resource — deploy models, create and manage connections, configure quota, and manage resource-level settings. Critically, this role has **no data plane access**. An Account Owner administers the platform but cannot build in projects.

**Control plane (Actions):**
- `Microsoft.CognitiveServices/*` — full control plane wildcard
- `Microsoft.Authorization/roleAssignments/write` and `delete` (ABAC-conditioned to Azure AI User role only)

**Data plane (DataActions):** None.

**Assign at:** Resource scope.

**Note:** For fine-tuning workflows, a principal needs both control plane access (to create fine-tuning jobs) and data plane access (to upload training data and retrieve results). Assign both Azure AI Account Owner and Azure AI User to the same principal, or use Azure AI Owner instead.

#### Azure AI Owner

**Role Definition ID:** `c883944f-8b7b-4483-af10-35834be79c4a`

**Purpose:** The highest-privilege Foundry role. Combines full control plane and full data plane access, with unrestricted role assignment capability (no ABAC conditions). Use for break-glass accounts and automation service principals that need to manage the entire platform.

**Control plane (Actions):**
- `Microsoft.CognitiveServices/*` — full control plane wildcard
- `Microsoft.Authorization/*/read` — read all role assignments and definitions
- Full AlertsManagement and Insights permissions (added February 5, 2026, for observability management)

**Data plane (DataActions):**
- `Microsoft.CognitiveServices/*` — full data plane wildcard

**Assign at:** Resource scope. Assign sparingly — this role can assign any role to any principal on the resource.

**Note:** This role received a permissions update on February 5, 2026 adding eight AlertsManagement and Insights permissions to support alerting and monitoring management. This was a purely additive update; no permissions were removed.

#### Standard Azure Roles

Standard Azure roles — **Owner**, **Contributor**, and **Reader** — apply to Foundry resources but cover **only control plane actions**. They do not grant any data plane access.

| Standard Role | Can manage Foundry resource? | Can build in projects? |
|---|---|---|
| Owner | Yes (full control plane + role assignment) | No |
| Contributor | Yes (full control plane, no role assignment) | No |
| Reader | Read-only metadata | No |

> Note: The Contributor role includes model deployment capability via control plane actions. If your governance model requires separating infrastructure management from model lifecycle management, be aware that Contributor can deploy models. Use Azure Policy to enforce model deployment controls independently of RBAC (see [Section 8](#8-azure-policy-governance)).

### Role Permissions Summary

| Role | Control Plane | Data Plane | Role Assignment | Model Deploy | Create Projects |
|---|---|---|---|---|---|
| Azure AI User | Read only | Full | No | No | No |
| Azure AI Project Manager | Project CRUD | Full | AI User only (ABAC) | No | Yes |
| Azure AI Account Owner | Full | None | AI User only (ABAC) | Yes | Yes |
| Azure AI Owner | Full | Full | Unrestricted | Yes | Yes |
| Owner (standard) | Full | None | Yes (unrestricted) | Yes | Yes |
| Contributor (standard) | Full (no RBAC) | None | No | Yes | Yes |
| Reader (standard) | Read only | None | No | No | No |

### Enterprise RBAC Assignment Matrix

| Persona | Recommended Role | Recommended Scope |
|---|---|---|
| Platform / infra engineer | Azure AI Account Owner | Resource scope |
| AI application developer | Azure AI User | Project scope |
| Team lead / project admin | Azure AI Project Manager | Resource or project scope |
| Break-glass / automation service principal | Azure AI Owner | Resource scope |
| Security/compliance auditor | Reader | Resource scope |
| CI/CD service principal (build & deploy) | Azure AI Account Owner + Azure AI User | Resource scope |
| Fine-tuning service principal | Azure AI Owner (or Account Owner + User) | Resource scope |

### RBAC Best Practices

**Prefer project scope over resource scope for developers.** Assign Azure AI User at the Foundry **project** scope rather than the resource scope. Combine this with Reader at the **resource** scope so the developer can navigate to the resource in the portal without gaining data plane access to all other projects.

**Use managed identities, not API keys.** When creating a project via SDK or CLI (not the portal), the project's managed identity is **not** automatically assigned Azure AI User. You must explicitly assign it. API keys bypass RBAC entirely and grant full access — use Entra ID authentication wherever possible. Note: Agents and Evaluations specifically require Entra ID authentication and do not support API key auth.

**ABAC conditions protect privilege escalation.** Azure AI Project Manager and Azure AI Account Owner can only assign the Azure AI User role, enforced via ABAC conditions. Azure AI Owner has no such restriction. Limit Azure AI Owner assignments strictly.

**Standard Contributor can deploy models.** If your security policy requires separating model deployment authority from general resource management, do not use Contributor for principals that should not deploy models. Use Azure AI Account Owner instead (which carries the same control plane capabilities but is purpose-built for Foundry).

**Fine-tuning requires both planes.** Only Azure AI Owner has both natively. If you prefer to avoid assigning the most privileged role for fine-tuning workflows, explicitly assign Azure AI Account Owner (control plane) and Azure AI User (data plane) to the same service principal.

**Viewing and purging deleted accounts** requires Contributor at the **subscription** scope, not resource scope. Plan for this in your break-glass or platform team role assignments.

---

## 7. Network Isolation

Network isolation for Foundry resources is configured at the resource level and inherited by all projects within that resource. Three isolation modes are supported:

| Mode | Description | Recommended for |
|---|---|---|
| **Disabled** | Foundry resource is publicly accessible over the internet | Development and prototyping only |
| **Allow Internet Outbound** | Microsoft-managed VNet; inbound traffic via private endpoints, outbound internet traffic allowed | Most production workloads; covers the majority of SaaS integrations |
| **Allow Only Approved Outbound** | Fully private managed network; outbound only to explicitly approved destinations | Highly regulated industries (financial services, healthcare, government); air-gapped or zero-trust environments |

**Important constraints:**

- You cannot **disable** managed VNet isolation after it has been enabled on a resource. Changing from an isolated mode back to *Disabled* requires reprovisioning the resource.
- There is no upgrade path from a **custom VNet** configuration to a **managed VNet** configuration. Resources must be reprovisioned.
- As of April 30, 2025, automatic role assignment for private endpoint connections was discontinued. You must explicitly assign the **Azure AI Enterprise Network Connection Approver** role to the principals responsible for approving private endpoint connections to Foundry resources.

> Managed VNet for new Foundry projects is in Preview as of February 2026. Evaluate Preview limitations against your production readiness criteria before enabling managed VNet in production environments.

---

## 8. Azure Policy Governance

Azure Policy provides guardrails that enforce your organisation's standards across all Foundry resources, regardless of who provisions them. Policies are assigned at the management group, subscription, or resource group scope and apply to all matching resources within that scope.

### Built-in Policy Definitions

The following built-in Azure Policy definitions apply to Azure AI Foundry resources (listed under the **Machine Learning** category in the Azure Policy portal):

| Policy | Effect | Purpose |
|---|---|---|
| Hubs should be encrypted with a customer-managed key | Audit / Deny | Require CMK for data at rest |
| Hubs should disable public network access | Audit / Deny | Enforce private network access |
| Hubs should use private link | Audit / Deny | Require private endpoint connectivity |
| Hubs should use user-assigned managed identity | Audit / Deny | Prevent use of system-assigned identities |
| Compute instances should have idle shutdown | Audit / Deny | Prevent idle compute cost accumulation |
| Configure hubs to disable public network access | Modify / DeployIfNotExists | Auto-remediate public access settings |
| Configure Azure hubs with private endpoints | DeployIfNotExists | Auto-deploy private endpoint on new resources |
| Configure hubs to use private DNS zones | DeployIfNotExists | Auto-configure DNS for private endpoints |
| Configure diagnostic settings for hubs to Log Analytics | DeployIfNotExists | Enforce centralised log collection |

> These built-in definitions target the **hub** resource type but apply governance principles that are directly relevant to any Foundry provisioning strategy. Assign them at the subscription or management group level so they cover all Foundry resources as they are provisioned.

### Model Deployment Control

The built-in policy **`[Preview]: Azure ML Deployments should only use approved Registry Models`** controls which models can be deployed across serverless (MaaS) and Model-as-a-Platform (MaaP) endpoints.

Policy parameters:
- `allowedModelPublishers` — restrict by publisher name (e.g., `"azure-openai"`, `"Meta"`, `"Mistral"`). Leave empty to allow all publishers.
- `allowedAssetIds` — restrict to specific model version identifiers. Use this for strict reproducibility requirements in regulated environments.

> This policy is still in **Preview**. Test it in a non-production environment and validate its effect against your model catalog before enforcing it with a Deny effect in production.

---

## 9. Cost Management

### Billing Models

Azure AI Foundry model deployments support three billing models:

| Model | How it is billed | Best suited for |
|---|---|---|
| **Pay-as-you-go (token-based)** | Per 1,000 tokens; input and output tokens priced separately | Bursty or unpredictable workloads; development and experimentation |
| **Commitment Tiers** | Fixed-fee commitment per month; overage charged at standard per-token rates | Predictable moderate workloads with some burst headroom needed |
| **Provisioned Throughput Units (PTUs)** | Model-independent capacity units billed hourly; billed regardless of utilisation | Steady high-volume production workloads with predictable load profiles |

**PTU considerations:** PTUs guarantee consistent throughput (no throttling at capacity) and are billed hourly whether or not the deployment is actively serving traffic. Azure Reservations (1-month or 1-year commitments) provide significant discounts on PTU costs. Before purchasing a reservation, create the deployment first to confirm capacity availability in your target region. Use the built-in **PTU Quota Calculator** at *ai.azure.com → Management → Quota Calculator* to size your PTU commitment.

> Azure AI Foundry does **not** support hard billing cutoffs. Azure Budgets can send alerts and trigger automated actions when spending thresholds are reached, but stopping all AI API calls requires custom automation (e.g., a Logic App or Azure Function that removes RBAC or rotates keys on a budget alert trigger). Plan for this explicitly in your cost governance design.

### Cost Attribution

| Level | Where to view | Latency |
|---|---|---|
| Foundry resource (account) | Azure Cost Management (billing meters under CognitiveServices resource in Azure portal) | ~5 hours |
| Project | *Foundry portal → Operate → Overview → Estimated cost tile* | Near real-time |
| Model deployment | *Foundry portal → Models → Monitor tab* | Near real-time |
| Agent | *Foundry portal → Build → Agents → Estimated costs column* | Near real-time |

Note: The Azure portal Cost Management view shows aggregated charges at the Cognitive Services account level, not per individual model deployment. For per-model cost granularity, use the Foundry portal views listed above.

**Third-party model billing:** Partner and community models (Mistral, Cohere, Meta Llama) deployed through Azure Marketplace are billed as `microsoft.saas/resources`. These charges appear at the **resource group** level in Cost Analysis, not under the Foundry resource. Each project generates one SaaS resource per model offer, enabling per-project tracking. Note that Azure Prepayment credit (previously called Azure Monetary Commitment) cannot be applied to Marketplace-billed models.

### TPM Management and AI Gateway

The **AI Gateway** (backed by Azure API Management) provides project-scoped token consumption controls that go beyond what Azure Budgets offers:

- **TPM rate limit**: Caps token consumption per minute. Requests exceeding the limit receive an HTTP 429 response.
- **Total token quota**: Caps total token consumption over a configurable period (hourly, daily, weekly, or monthly). Requests after the quota is exhausted receive an HTTP 403 response.

Configure via: *Foundry portal → Operate → Admin console → AI Gateway tab → Token management*.

> The AI Gateway requires setting up Azure API Management (APIM), which carries its own pricing. A free tier is available for AI Gateway scenarios — evaluate whether the free tier meets your throughput and policy requirements before committing to a paid APIM tier.

### Cost Optimization Strategies

| Strategy | Potential Saving | Detail |
|---|---|---|
| **Model routing** | 10–20x cost reduction | Route simple classification and extraction tasks to lighter, cheaper models. Reserve expensive reasoning models for complex multi-step tasks only. |
| **Batch API** | 50% cost reduction vs real-time | Asynchronous batch processing with up to 24-hour latency. Ideal for bulk evaluation, document processing, and offline classification. |
| **Prompt caching** | 50–90% on cached prefixes | Structure reusable content (system prompts, retrieved documents) at the beginning of the prompt so caching maximises across requests. |
| **Token minimisation** | Up to 71% per request | Set explicit `max_tokens`, use structured outputs to reduce verbose responses, limit few-shot examples to what is needed. |
| **RAG over document stuffing** | Significant | Retrieve the top 3–5 relevant chunks from your knowledge base rather than sending entire source documents in context. |
| **Fine-tuned model lifecycle** | Avoids idle deployment costs | Microsoft auto-deletes fine-tuned model deployments that have been inactive for 15 or more consecutive days. Redeploy from the registered model when needed. |
| **PTU reservations** | Significant at scale | 1-month or 1-year Azure Reservations on PTU deployments reduce per-unit hourly costs materially for stable production workloads. |

### Monitoring and Metrics

Azure Monitor collects metrics automatically from Foundry resources. These metrics are available in the Azure portal Metrics Explorer, Foundry portal built-in dashboards, Azure Monitor Workbooks, and the community Grafana dashboard.

| Metric | Unit | Available on |
|---|---|---|
| ModelRequests | Count | All deployment types |
| ModelAvailabilityRate | Percent | All deployment types |
| InputTokens | Count | All deployment types |
| OutputTokens | Count | All deployment types |
| TotalTokens | Count | All deployment types |
| ProvisionedUtilization | Percent | PTU, PTU-managed |
| TokensCacheMatchRate | Percent | PTU, PTU-managed |
| TimeToResponse | Milliseconds | PTU, PTU-managed |

> Set up Azure Monitor alerts on `ModelAvailabilityRate` and `ProvisionedUtilization` as baseline operational alerts. A sustained `ProvisionedUtilization` above 80% on a PTU deployment indicates capacity pressure and may require a quota increase or load redistribution.

---

## 10. Infrastructure as Code

Managing Foundry resources via Infrastructure as Code (IaC) is strongly recommended for any environment beyond individual experimentation. IaC enables consistent, repeatable provisioning, supports environment promotion (dev → test → prod), and integrates naturally into CI/CD pipelines.

### Terraform

Two active **Azure Verified Modules (AVM)** for Terraform cover Foundry provisioning:

| Module | Purpose | Registry |
|---|---|---|
| `avm-ptn-aiml-ai-foundry` | Primary Foundry AVM pattern: provisions the Foundry resource with optional BYOS, BYKV, and project submodule | [registry.terraform.io/modules/Azure/avm-ptn-aiml-ai-foundry](https://registry.terraform.io/modules/Azure/avm-ptn-aiml-ai-foundry/azurerm/latest) |
| `avm-ptn-aiml-landing-zone` | Full enterprise AI/ML landing zone: Foundry resource + VNet, Azure API Management, monitoring, and compute | [registry.terraform.io/modules/Azure/avm-ptn-aiml-landing-zone](https://registry.terraform.io/modules/Azure/avm-ptn-aiml-landing-zone/azurerm/latest) |

Both modules were created in June 2025 and are actively maintained. `avm-ptn-aiml-ai-foundry` is the right starting point for most teams. Use `avm-ptn-aiml-landing-zone` when you need a full network stack and operational components (APIM for AI Gateway, Log Analytics, monitoring) provisioned together.

**Requirements:** Terraform >= 1.9, AzAPI provider (required for Foundry-specific resource types not yet in the AzureRM provider).

> The previously referenced module `avm-ptn-ai-foundry-enterprise` was **archived on July 11, 2025** and must not be used for new provisioning. Use `avm-ptn-aiml-ai-foundry` instead.

### Bicep

| Option | Description | Status |
|---|---|---|
| `Azure-Samples/azure-ai-studio-secure-bicep` | Official Azure Samples repository with secure Bicep templates for two scenarios: VNet-isolated and no-VNet. Hub-focused but provides a solid structural reference. | Active |
| `Azure/AI-Landing-Zones` | CAF-aligned AI landing zone reference architecture in both Bicep and Terraform. Covers Foundry and hub resource types. | Preview |
| Microsoft Learn quickstart templates | Minimal Bicep templates for provisioning Foundry resources and projects. Available in the [Foundry resource template quickstart](https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/create-resource-template?view=foundry-classic). | Active |

> Bicep Azure Verified Modules for Platform Landing Zone reached GA on January 20, 2026, but do not include AI Foundry-specific modules. The `Azure/AI-Landing-Zones` repository fills this gap but is still in Preview — evaluate its production-readiness against your requirements before adopting it for enterprise deployments.

---

## 11. CI/CD Integration

A CI/CD pipeline for AI workloads should automate both infrastructure provisioning and AI-specific validation (model evaluation and quality gating) before promoting to production.

### Official GitHub Actions for Evaluation

Microsoft provides two official GitHub Actions for pre-production AI evaluation:

| Action | Purpose | Status |
|---|---|---|
| `microsoft/ai-agent-evals` | Agent evaluation: intent resolution accuracy, tool call accuracy, task adherence | v2-beta |
| `microsoft/genai-evals` | Generative AI evaluation: coherence, fluency, groundedness, safety (content harm) | v3-beta |

Both actions are in beta. Pin to a specific release tag in production pipelines to avoid unexpected behaviour from mid-pipeline updates.

### Enterprise Pipeline Stages

| Stage | Action | Tooling |
|---|---|---|
| 1. IaC Validate | `terraform plan` or `bicep build` — validate templates, check for drift | GitHub Actions / Azure DevOps |
| 2. IaC Deploy | `terraform apply` or `az deployment group create` — provision or update infrastructure | GitHub Actions / Azure DevOps |
| 3. Model Deploy | Deploy or update model deployment via Azure AI SDK or Azure CLI | Python script / Azure CLI task |
| 4. Pre-production Eval | Run `microsoft/ai-agent-evals` or `microsoft/genai-evals` against the deployment | GitHub Action |
| 5. Threshold Gate | Fail the pipeline and block promotion if evaluation metrics fall below defined thresholds | GitHub Action conditions / Azure DevOps gate |
| 6. Production Deploy | Promote to production subscription — requires manual approval in regulated environments | Manual approval + automation |
| 7. Monitor | Post-deployment: Azure Monitor alerts, Foundry portal metrics, anomaly detection active | Ongoing |

> Azure DevOps does not have purpose-built pipeline templates for Foundry CI/CD. Azure DevOps users should adapt the GitHub Actions patterns using the Azure CLI and Python SDK tasks available in Azure DevOps. The evaluation GitHub Actions can be executed from Azure DevOps via a `script` step calling the same underlying Python evaluation SDK.

---

## 12. Additional Resources

| Topic | Link |
|---|---|
| Microsoft Foundry Architecture | [learn.microsoft.com — Foundry Architecture](https://learn.microsoft.com/en-us/azure/ai-foundry/concepts/architecture?view=foundry-classic) |
| What is Microsoft Foundry? | [learn.microsoft.com — What is Microsoft Foundry](https://learn.microsoft.com/en-us/azure/ai-foundry/what-is-foundry?view=foundry-classic) |
| Choose a resource type (Foundry vs hub) | [learn.microsoft.com — Choose a Resource Type](https://learn.microsoft.com/en-us/azure/ai-foundry/concepts/resource-types?view=foundry-classic) |
| RBAC for Foundry (new architecture) | [learn.microsoft.com — RBAC for Foundry](https://learn.microsoft.com/en-us/azure/ai-foundry/concepts/rbac-foundry?view=foundry-classic) |
| Authentication and Authorization in Foundry | [learn.microsoft.com — Authentication and Authorization](https://learn.microsoft.com/en-us/azure/ai-foundry/concepts/authentication-authorization-foundry?view=foundry-classic) |
| Azure Built-in Roles — AI + Machine Learning | [learn.microsoft.com — Built-in Roles](https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles/ai-machine-learning) |
| Enterprise provisioning planning guide | [learn.microsoft.com — Planning Guide](https://learn.microsoft.com/en-us/azure/ai-foundry/concepts/planning) |
| Configure managed virtual network | [learn.microsoft.com — Managed VNet](https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/configure-managed-network?view=foundry-classic) |
| Azure Policy for Foundry | [learn.microsoft.com — Azure Policy](https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/azure-policy) |
| Control model deployment with policies | [learn.microsoft.com — Model Deployment Policy](https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/built-in-policy-model-deployment) |
| Plan and manage costs | [learn.microsoft.com — Manage Costs](https://learn.microsoft.com/en-us/azure/ai-foundry/concepts/manage-costs?view=foundry-classic) |
| Enforce token limits (AI Gateway) | [learn.microsoft.com — Enforce Token Limits](https://learn.microsoft.com/en-us/azure/ai-foundry/control-plane/how-to/enforce-limits-models?view=foundry) |
| Monitor model deployments | [learn.microsoft.com — Monitor Models](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-models/how-to/monitor-models?view=foundry-classic) |
| PTU onboarding and billing | [learn.microsoft.com — PTU Onboarding](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/provisioned-throughput-onboarding?view=foundry-classic) |
| Evaluation in GitHub Actions | [learn.microsoft.com — Evaluation in GitHub Actions](https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/evaluation-github-action?view=foundry-classic) |
| AI Ready — Cloud Adoption Framework | [learn.microsoft.com — CAF AI Ready](https://learn.microsoft.com/en-us/azure/cloud-adoption-framework/scenarios/ai/ready) |
| Govern AI PaaS — Cloud Adoption Framework | [learn.microsoft.com — CAF AI Governance](https://learn.microsoft.com/en-us/azure/cloud-adoption-framework/scenarios/ai/platform/governance) |
| Create Foundry resource from Bicep template | [learn.microsoft.com — Resource Template](https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/create-resource-template?view=foundry-classic) |
| Migrate hub-based projects to Foundry projects | [learn.microsoft.com — Migrate Project](https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/migrate-project?view=foundry-classic) |
| Terraform AVM: AI Foundry pattern module | [github.com/Azure/terraform-azurerm-avm-ptn-aiml-ai-foundry](https://github.com/Azure/terraform-azurerm-avm-ptn-aiml-ai-foundry) |
| Terraform AVM: AI/ML landing zone | [github.com/Azure/terraform-azurerm-avm-ptn-aiml-landing-zone](https://github.com/Azure/terraform-azurerm-avm-ptn-aiml-landing-zone) |
| AI Landing Zones (Bicep + Terraform, Preview) | [github.com/Azure/AI-Landing-Zones](https://github.com/Azure/AI-Landing-Zones) |
| Secure Bicep deployment samples | [github.com/Azure-Samples/azure-ai-studio-secure-bicep](https://github.com/Azure-Samples/azure-ai-studio-secure-bicep) |
| GitHub Action: AI Agent Evals | [github.com/microsoft/ai-agent-evals](https://github.com/microsoft/ai-agent-evals) |
| GitHub Action: GenAI Evals | [github.com/microsoft/genai-evals](https://github.com/microsoft/genai-evals) |
| Cost optimisation blog (Azure AI Services) | [techcommunity.microsoft.com — Cost Optimization](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/cost-optimization-of-azure-ai-services/4459100) |
| Grafana community dashboard for Foundry | [grafana.com/grafana/dashboards/24039-ai-foundry](https://grafana.com/grafana/dashboards/24039-ai-foundry/) |
