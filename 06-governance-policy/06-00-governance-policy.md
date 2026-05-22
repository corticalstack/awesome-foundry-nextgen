# Governance policy

## Why

In the hub/spoke architecture, all AI models are deployed centrally in the core resource group (`rg-foundry-core-*`) and exposed via APIM. If spoke teams could deploy their own models, you'd get fragmented costs, inconsistent content filters, and no unified observability.

The sections below describe what the policy does, where it applies, and how to inspect it in the portal; the notebook listed here deploys it end-to-end.

## In this chapter

| File | Description |
|------|-------------|
| [06-01-deploy-governance-policy.ipynb](06-01-deploy-governance-policy.ipynb) | Defines and assigns the `deny-model-deployments` Azure Policy to spoke resource groups, blocking model deployment outside the hub |

---

## What it does

Applies an Azure Policy (`deny-model-deployments`) to spoke resource groups that blocks any `Microsoft.CognitiveServices/accounts/deployments` resource creation. Spoke accounts can still **use** models via the APIM gateway - they just can't **deploy** new ones.

## Scope

| Resource Group | Policy |
|---|---|
| `rg-foundry-core-*` | Exempt - models live here |
| `rg-foundry-spoke-alpha-*` | Blocked |
| `rg-foundry-multi-*` | Blocked |

## View in portal

- **Definition**: Policy → Authoring → Definitions → Custom → `deny-model-deployments`

![alt text](../docs/screenshots/policy-definition-1.png)

![alt text](../docs/screenshots/policy-definition-2.png)


- **Assignments**: Policy → Assignments, or navigate to a spoke RG → Policies

![alt text](../docs/screenshots/policy-assignment-to-spoke-rg.png)

---

[Next: Deploy governance policy →](06-01-deploy-governance-policy.ipynb)