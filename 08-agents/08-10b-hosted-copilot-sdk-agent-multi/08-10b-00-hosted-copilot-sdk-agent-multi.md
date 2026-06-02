# Foundry-hosted Copilot SDK agent on the shared 1:N multi account (APIM gateway, direct)

This is the **"B" variant** of [`08-10-hosted-copilot-sdk-agent`](../08-10-hosted-copilot-sdk-agent/08-10-00-hosted-copilot-sdk-agent.md). The agent container is **identical** - the same GitHub Copilot SDK image, `system_prompt.md`, skills, and tracing. What changes is the **deployment topology and where inference comes from**:

| | 08-10 (standalone) | 08-10b (this lab) |
|---|---|---|
| Foundry account | New, dedicated (`aif-copilot-sdk-{suffix}`) | Existing shared `aif-spoke-multi-{suffix}` (1:N) from [`05-04`](../../05-foundry-project-pattern-setup/05-04-deploy-foundry-multi-project/05-04-01-deploy-foundry-multi-project.ipynb) |
| Resource group | New `rg-foundry-copilot-sdk-08-10` | Existing `rg-foundry-multi-{suffix}` |
| Where inference runs | **Local** `gpt-5.4-mini` deployment on the project's own account | **APIM core gateway** -> `gpt-5-mini` on `aif-core-{suffix}` |
| How the container reaches the model | Project endpoint (`<project>/openai/v1/`), Managed Identity (audience `ai.azure.com`) | **Directly at the APIM gateway** (`<apim>/openai`), subscription key in the `api-key` header |
| Model string | `gpt-5.4-mini` (a local deployment) | `gpt-5-mini` (a **bare** gateway deployment name) |
| `main.py` switch | Foundry-endpoint mode (default) | **APIM-direct mode** - set by `APIM_BASE_URL` + `APIM_KEY` env vars |
| Agent identity RBAC | AcrPull + Foundry User + Cognitive Services OpenAI User | **AcrPull + Foundry User only** (the gateway key, not the MI, pays for inference) |
| `deny-model-deployments` policy | n/a (own RG, excluded) | **Satisfied** - no model is deployed on the multi account |

## The one idea that matters: point the SDK directly at APIM - **not** at a Foundry connection

The intuitive 1:N move is to do what the team prompt agents (`iq`, `obs`, `contoso`) do: add an `ApiManagement` connection to the project and reference the model as `connection/deployment`, letting Foundry call the gateway on the agent's behalf. **That does not work for a hosted agent.** Foundry's "bring your own model" via a gateway connection is, per Microsoft's own docs, [**supported only for prompt agents**](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/ai-gateway) ("Only prompt agents in the Agent SDK support this feature"). A hosted agent calling the **Responses API** through a connection forwards the *connection-qualified* model string (`copilot-sdk-apim-connection/gpt-5-mini`) to the gateway body, which the upstream rejects with `DeploymentNotFound`. The connection path is a dead end here.

So this lab does the opposite of what 08-10b originally assumed: the container points its Copilot SDK provider **straight at the gateway**, and there is **no Foundry connection** at all.

- `base_url` = the APIM `/openai` endpoint (`https://apim-foundry-{suffix}.azure-api.net/openai`).
- Auth = the **gateway subscription key** in the **`api-key` header** (provider `type="azure"`), because APIM's `openai` API accepts only that header - it rejects `Authorization: Bearer` (whether a key or a managed-identity token).
- `model` = the **bare** deployment name (`gpt-5-mini`), and the request hits `/openai/responses?api-version=2025-03-01-preview` (the form APIM actually serves).

`main.py`'s `_byok_provider()` selects this mode whenever `APIM_BASE_URL` + `APIM_KEY` are present; otherwise it falls back to the Foundry-project-endpoint path (standalone 08-10). The model string is the only `main.py`-visible difference between the two labs - everything else is an env var.

```
+------------------------------------+        +----------------------------+
| Hosted agent container             |        | apim-foundry-{suffix}      |
|  (copilot-sdk-project on the       |  HTTPS |  /openai/responses         |
|   shared multi account)            | api-key|  ?api-version=2025-03-01-  |
|  CopilotClient(provider=azure)     |------->|     preview                |
|  base_url=<apim>/openai            |        |  (subscription-key auth)   |
|  model   = gpt-5-mini (bare)       |        +-------------|--------------+
+------------------------------------+                      v
   container egress is direct (the          aif-core-{suffix} : gpt-5-mini
   hosted agent's own outbound traffic                (reasoning model)
   leaves through its Micro VM NIC)
```

## Why the gateway model must be a *reasoning* model

The Copilot CLI drives the model over its **Responses wire protocol in stateless mode**, which always carries **encrypted reasoning content**. Only **reasoning models** support that. `gpt-4.1-mini` (the repo-wide gateway chat model used by the team prompt agents) is not a reasoning model and returns `400 Encrypted content is not supported with this model.` So this lab deploys **`gpt-5-mini`** on the gateway backend (`aif-core`) and routes to it. (This is the same reason standalone 08-10 uses `gpt-5.4-mini` rather than `gpt-4.1-mini`.)

## The container *can* reach APIM (egress)

A documented constraint from [`08-03`](../08-03-hosted-agents/08-03-00-hosted-agents.md) is that "Foundry's hosted compute network can't reach arbitrary `*.azure-api.net` hosts." In practice that's the *default-egress* posture for the **tool/data-proxy** path, not the agent's own outbound: per the [Agent Service networking deep dive](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/agents-networking-deep-dive), a hosted agent's **own outbound traffic is direct, through the Micro VM's dedicated NIC** (only tool-server calls route through the single-tenant data proxy). This lab's smoke test confirms the container reaches `apim-foundry-{suffix}.azure-api.net` and gets a reply. (If you run under full network isolation / BYO-VNet, ensure your egress rules or a private endpoint allow the gateway host.)

## The tradeoff this makes: the gateway key lives in the container env

Pointing the container directly at APIM means the **gateway subscription key is injected as the `APIM_KEY` environment variable** at registration. Foundry's [hosted-agent guidance](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents) explicitly says *don't put secrets in env vars*. For this lab it is the simplest thing that works and demonstrates the pattern; for production, harden it:

- **Key Vault connection** - fetch the gateway key at runtime instead of baking it into the version env.
- **Managed-identity-to-APIM** - add a `validate-azure-ad-token` policy on the gateway so the container authenticates with its **AgentIdentity** (bearer, audience you configure) and **no key is needed at all**. This is the production-grade path the BYOM docs describe; it also lets you drop `APIM_KEY` entirely.

## How it fits the 1:N governance model

`copilot-sdk-project` is a **capability workload**, not a new team, added to the existing shared `aif-spoke-multi` account. Three things keep it inside the architecture's guardrails:

- **No model deployment on the multi account** -> the `deny-model-deployments` policy on `rg-foundry-multi` is not triggered. The bicep creates only a project + an ACR. The reasoning model lives on the **core gateway account** (`aif-core`, in `rg-foundry-core`), where models are expected.
- **Dedicated APIM subscription** (`foundry-gateway-copilot-sdk`) -> the agent's inference quota is isolated from team traffic, exactly as `foundry-gateway-iq` / `-obs` / `-contoso-pmo` are.
- **Minimal agent RBAC** (AcrPull + Foundry User) -> the agent never calls the account's models with its identity, so no Cognitive Services OpenAI User grant is needed; the gateway key pays for inference.

> **Shared-account note:** This lab enables the hosted-agent **capability host on the shared account** (`aif-spoke-multi`) via a one-time idempotent REST `PUT`. That is an account-level enablement, required for any hosted agent on this account. If a later lab already created it, the call returns `409` and is a no-op.

## Validate this on first deploy

The decisive checks are (1) the container can **egress to the gateway** and (2) APIM authenticates the **`api-key`** request for the **reasoning** model. All three were proven before this lab was finalised: the provider config was validated locally against the live gateway, and the deployed hosted agent answered a smoke test plus ran shell tools end-to-end. The first smoke test in Step 8 re-proves it in your subscription. If a turn fails, see the troubleshooting cell (model not a reasoning model, missing `APIM_*` env, inactive gateway key, or egress blocked under network isolation).

## Files

| File | Purpose |
|---|---|
| [`08-10b-01-deploy-hosted-copilot-sdk-agent-multi.ipynb`](08-10b-01-deploy-hosted-copilot-sdk-agent-multi.ipynb) | Mints the gateway subscription, deploys `gpt-5-mini` on the gateway backend, deploys the project + ACR bicep, enables the capability host, builds **this lab's own container image**, registers + role-grants the hosted agent **in APIM-direct mode**, then runs the smoke tests and the M365 analytics demo |
| [`infra/main.bicep`](infra/main.bicep) | RG-scoped bicep: adds `copilot-sdk-project` + ACR to the existing shared account, with RBAC. **No connection, no local model deployment** |
| [`src/github-copilot-invocations/`](src/github-copilot-invocations/) | The agent container (Dockerfile, `main.py` with the env-driven APIM-direct branch, `system_prompt.md`, `skills/`, `tracing.py`). The image build context |
| [`data/`](data/) | M365 demo data (`m365-licenses.csv`, `m365-reference.json`) used by the analytics demo |

This lab is **self-contained**: it ships its own copy of the container source and demo data, so it has **no dependency on 08-10**. (The container code is the same as 08-10 plus the env-driven APIM-direct branch in `_byok_provider()`; if you change one lab's container, the other is unaffected.)

## Prerequisites

- The **core gateway** ([`05-02`](../../05-foundry-project-pattern-setup/05-02-deploy-foundry-core-gateway/05-02-01-deploy-foundry-core-gateway.ipynb)) and the **1:N multi account** ([`05-04`](../../05-foundry-project-pattern-setup/05-04-deploy-foundry-multi-project/05-04-01-deploy-foundry-multi-project.ipynb)) must be deployed. The repo `.env` therefore already has `GATEWAY_URL`, `MULTI_ACCOUNT`, and `MULTI_ACCOUNT_ENDPOINT`.
- `az` CLI signed in (`az login`), with **Owner** (or **Contributor + User Access Administrator**) on `rg-foundry-multi-{suffix}` **and** rights on `rg-foundry-core-{suffix}` (this lab mints a gateway subscription and deploys a reasoning model there).
- **Reasoning-model quota** for `gpt-5-mini` GlobalStandard in `eastus2` (the gateway region).
- `python>=3.11` with the repo `uv` environment (`azure-ai-projects>=2.1.0`, `azure-identity`, `requests`).
- No local Docker required - `az acr build` runs the build server-side.

---

[Next: Deploy the hosted Copilot SDK agent on the multi account →](08-10b-01-deploy-hosted-copilot-sdk-agent-multi.ipynb)
