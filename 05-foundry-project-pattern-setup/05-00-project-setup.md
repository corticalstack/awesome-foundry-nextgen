# Introduction
Looking to leverage Microsoft Foundry for building out and managing your AI building blocks at scale will introduce you to some essential Azure infrastructure, provisioning patterns, and Role-Based Access Control models. 

The remainder of this page covers those concepts; the labs listed below put them into practice with Bicep templates and notebooks.

## Directory Contents

| File | Description |
|------|-------------|
| [05-01-architecture.md](05-01-architecture.md) | Lab series architecture overview: centralised AI gateway pattern, 1:1 spoke vs 1:N multi-project provisioning, RBAC layout, and connectivity model |
| [05-02-deploy-foundry-core-gateway/](05-02-deploy-foundry-core-gateway/) | Deploys the central Foundry core with API Management gateway as the shared entry point for model traffic ([deploy-foundry-core-gateway.ipynb](05-02-deploy-foundry-core-gateway/deploy-foundry-core-gateway.ipynb), [main.bicep](05-02-deploy-foundry-core-gateway/main.bicep)) |
| [05-03-deploy-foundry-project-spoke/](05-03-deploy-foundry-project-spoke/) | Deploys a 1:1 dedicated Foundry account spoke for a single team with a hard infrastructure boundary ([deploy-foundry-project-spoke.ipynb](05-03-deploy-foundry-project-spoke/deploy-foundry-project-spoke.ipynb), [main.bicep](05-03-deploy-foundry-project-spoke/main.bicep)) |
| [05-04-deploy-foundry-multi-project/](05-04-deploy-foundry-multi-project/) | Deploys the 1:N multi-project Foundry account hosting several team projects with project-level isolation ([deploy-foundry-multi-project.ipynb](05-04-deploy-foundry-multi-project/deploy-foundry-multi-project.ipynb), [main.bicep](05-04-deploy-foundry-multi-project/main.bicep)) |

---

## 1. Azure Management Hierarchy
Azure organises resources into a four-level management hierarchy.

```
Management Groups
└── Subscriptions
    └── Resource Groups
        └── Resources
```

**Management Groups** are optional containers that sit above subscriptions. They enable you to apply Azure Policy and RBAC across multiple subscriptions in a single operation. Enterprises typically create management groups aligned to business units, regulatory domains, or workload types. Example policies you could set at management level are denying public network access or use of API keys to access Foundry components. 

**Subscriptions** serves three distinct purposes. They are your **billing boundary** (all charges in a subscription appear on a single invoice), your **management boundary** (subscription-level Azure Policy and RBAC apply to everything within it), and your **quota boundary** (Azure resource and service quotas like Tokens Per Minute are tracked per subscription per region).

**Resource Groups** are logical containers for deploying and managing related Azure resources as a lifecycle unit. For example resources can be deleted together. You can apply tags so that for example Azure Cost Management can filter for costs by tags. 

**Resources** are the individual Azure services you provision — in the context of this guide, a Foundry resource or Foundry project.

## 2. Foundry Resource Architecture

Microsoft Foundry uses a **two-level hierarchy**: 

- a **Foundry resource** (the account-level container) and 
- one or more **Foundry projects**, the workspace-level containers where AI building blocks are built and operated.

So Foundry resources are provisioned in your subscription and resource group, and carry all settings that govern all projects beneath it: networking configuration, RBAC assignments, Azure Policy applicability, and model deployment quotas.


## 3. Foundry deployment patterns

 Because a Foundry resource acts as both a cost boundary and a governance boundary, how you map resources to teams is one of the first architectural decisions you'll make — and it shapes isolation, compliance, and operational overhead for everything beneath it.

### Why 1:N?

You should consider the 1:N pattern, which means a single Foundry resource hosting multiple projects — one account, many teams.

In enterprise environments, teams within the same department share infrastructure costs while maintaining project-level isolation:

Cost efficiency -- one AI account instead of N accounts
Isolation -- each team has its own project workspace, agents, and data
Shared RBAC -- account-level roles propagate; project-level roles scope access
Unified management -- single account to monitor, patch, and govern

You can create agents per project, as these are scoped to projects, not accounts.

### When to use 1:N vs. separate accounts

| Scenario | Recommendation |
| --- | --- |
| Teams in the same department / cost center | 1:N |
| Teams with different compliance boundaries | Separate accounts |
| Dev / staging / prod environments | Separate accounts per environment |
| Rapid prototyping with many small teams | 1:N to avoid account sprawl |


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


### Example Permissions Setup

Consider a small team with two admins and four developers getting started with Foundry on a new Azure subscription. The recommended approach is to create two Entra ID security groups and assign RBAC roles to the groups rather than to individual users. This reduces the number of role assignments consumed against the subscription limit and makes onboarding and offboarding straightforward.

#### Entra ID Security Groups

Create two **Security Groups** in Microsoft Entra ID. The key configuration requirements are:

- Set **"Microsoft Entra roles can be assigned to the group"** to **Yes** at creation time — this property is immutable and cannot be changed after the group is created.
- Use **Assigned** membership type (not Dynamic) to prevent unintended privilege escalation.

| Group | Members |
|---|---|
| `grp-foundry-admins` | Admin 1, Admin 2 |
| `grp-foundry-developers` | Dev 1, Dev 2, Dev 3, Dev 4 |

#### The Two-Layer Permission Model

Foundry access requires two independent IAM layers that must each be configured separately:

| Layer | Where assigned | Controls |
|---|---|---|
| **Layer 1 — Foundry plane** | Foundry resource or Project > Access Control (IAM) | Portal access, project creation, agent building, model deployment |
| **Layer 2 — Cognitive Services plane** | Azure AI Services resource > Access Control (IAM) | Content safety filters/guardrails, quota management, API key access |

The Foundry portal Users blade only handles Layer 1. Layer 2 must be configured directly on the underlying Azure AI Services resource — this step is commonly missed.

#### Layer 1 — Foundry-Specific Built-in Roles

The four Foundry-specific built-in roles have asymmetric permission coverage across the control plane (ARM actions) and data plane (dataActions). Understanding this split is essential:

| Role | Control plane | Data plane | Key capabilities |
|---|---|---|---|
| **Azure AI User** | Read-only | Full (`Microsoft.CognitiveServices/*`) | Build agents, call APIs, run prompts, use deployed models |
| **Azure AI Project Manager** | `accounts/projects/*` write + read | Full (`Microsoft.CognitiveServices/*`) | Everything AI User can do, plus create projects and register MCP server connections |
| **Azure AI Account Owner** | Full (`Microsoft.CognitiveServices/*`) | **None** | Deploy models, create projects, manage connections — but cannot build or develop |
| **Azure AI Owner** | Full | Full | Unrestricted; combines all capabilities of the above |

Roles assigned at the **Foundry resource (account) level** cascade down to all projects within it. Roles assigned at the **project level** are scoped to that project only.

#### Layer 2 — Cognitive Services Roles

| Role | Assigned to | Deploy models | Content filters | View quota | Edit quota |
|---|---|---|---|---|---|
| **Cognitive Services Contributor** | `grp-foundry-admins` | Yes | **Yes** | Yes | Yes |
| **Cognitive Services OpenAI Contributor** | `grp-foundry-developers` | Yes (OpenAI models) | No | No | No |
| **Cognitive Services Usages Reader** | `grp-foundry-admins` | — | — | Yes | Yes |

> **Note:** `Cognitive Services Usages Reader` must be assigned at **subscription scope** — it has no effect if assigned at the resource group or resource level.

#### Role Assignments Summary

**`grp-foundry-admins`**

| Role | Scope | Justification |
|---|---|---|
| Azure AI Account Owner | Foundry resource | Deploy models, create projects, manage connections |
| Cognitive Services Contributor | AI Services resource | Create and edit content safety filters/guardrails |
| Cognitive Services Usages Reader | Subscription | View and edit model quota in Management Center |

**`grp-foundry-developers`**

If developers only need to build agents and use existing connections (admins handle MCP server registration):

| Role | Scope | Justification |
|---|---|---|
| Azure AI User | Foundry resource | Full data-plane access across all projects |
| Cognitive Services OpenAI Contributor | AI Services resource | Create model deployments |

If developers also need to register remote MCP servers themselves, replace `Azure AI User` with `Azure AI Project Manager`, which adds control-plane write access to project resources (connections) while retaining full data-plane access.

#### Verified Permission Mapping

The following table maps specific Foundry operations to the minimum required role, sourced from Microsoft's official documentation:

| Operation | Minimum role | Plane | Scope | Source |
|---|---|---|---|---|
| Deploy a model | Azure AI Account Owner or Cognitive Services Contributor | Control | Foundry resource | [Create model deployments](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-models/how-to/create-model-deployments) |
| Create an agent | Azure AI User | Data | Foundry project | [Agent Service environment setup](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/environment-setup) |
| Create a new project | Azure AI Project Manager or Azure AI Account Owner | Control | Foundry resource | [RBAC for Microsoft Foundry](https://learn.microsoft.com/en-us/azure/ai-foundry/concepts/rbac-foundry) |
| Register a remote MCP server | Azure AI Project Manager or Contributor (at project scope) | Control | Foundry project | [Connect to MCP Server Endpoints](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/how-to/tools/model-context-protocol) |
| Use an MCP tool in an agent | Azure AI User | Data | Foundry project | [MCP server authentication](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/how-to/mcp-authentication) |
| Create/edit content safety filters | Cognitive Services Contributor | Control | AI Services resource | [Azure OpenAI RBAC](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/role-based-access-control) |
| View and edit quota limits | Cognitive Services Usages Reader | Control | Subscription | [Azure OpenAI RBAC](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/role-based-access-control) |
| View admin overview / Management Center | Azure AI Account Owner + Cognitive Services Usages Reader | Both | Resource + Subscription | [RBAC for Microsoft Foundry](https://learn.microsoft.com/en-us/azure/ai-foundry/concepts/rbac-foundry) |

> **Important:** `Azure AI Account Owner` has zero data-plane actions in its role definition. An admin assigned only this role cannot create agents or build within a project. If an admin needs to develop as well as manage, they should also be assigned `Azure AI User` on the relevant project, or use `Azure AI Owner` instead.
