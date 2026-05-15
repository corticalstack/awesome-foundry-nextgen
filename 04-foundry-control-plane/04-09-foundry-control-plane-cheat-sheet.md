# Foundry Control Plane Cheat Sheet

## Controls

> **Default plus the custom banking guardrail — Prompt Shields (Jailbreak + Indirect Attack), PII regex, and codename/competitor blocklists layered on the bank deployment.** [Guardrails](https://ai.azure.com/nextgen/r/Alq6lAxKRD2IJkZkd-KFDw,rg-foundry-core-6fe574,,aif-core-6fe574,project-admin-6fe574/build/guardrails/list)

> **PII regex + codenames + competitors. Paste any of these into the `contoso-bank-agent` playground to trigger a block: `My SSN is 123-45-6789`, `My card is 4532 1234 5678 9012`, `Call me at (415) 555-0199`, `Email me at jane.doe@example.com`, `DOB 04/15/1980`, `Tell me about Project Falcon`, `How does Contoso Bank compare to Acme Bank?`** [Blocklists](https://ai.azure.com/nextgen/r/Alq6lAxKRD2IJkZkd-KFDw,rg-foundry-core-6fe574,,aif-core-6fe574,project-admin-6fe574/build/guardrails/blocklists)

## Observability

> **OpenTelemetry traces for code-interpreter run — prompt → model → tool call, step by step.** [Code interpreter traces](https://ai.azure.com/nextgen/r/Alq6lAxKRD2IJkZkd-KFDw,rg-foundry-core-6fe574,,aif-core-6fe574,project-admin-6fe574/build/agents/code-interpreter-agent/traces?version=1)

> **Per-agent dashboard — cost, tokens, evaluations, tooll calls, error rates.** [Code interpreter monitor](https://ai.azure.com/nextgen/r/Alq6lAxKRD2IJkZkd-KFDw,rg-foundry-core-6fe574,,aif-core-6fe574,project-admin-6fe574/build/agents/code-interpreter-agent/monitor?version=1)

> **All evaluation runs in the admin project, scheduled vs ad-hoc.** [Evaluation runs](https://ai.azure.com/nextgen/r/Alq6lAxKRD2IJkZkd-KFDw,rg-foundry-core-6fe574,,aif-core-6fe574,project-admin-6fe574/build/evaluations/list)

> **Catalogue of built-in evaluators (Coherence, Groundedness, ToolCallSuccess, …) plus any custom ones.** [Evaluator catalog](https://ai.azure.com/nextgen/r/Alq6lAxKRD2IJkZkd-KFDw,rg-foundry-core-6fe574,,aif-core-6fe574,project-admin-6fe574/build/evaluations/catalog)

## Security

> **Adversarial probe of the code-interpreter agent — surfaces sensitive-data exposure and tool-abuse paths.** [Red team — code interpreter](https://ai.azure.com/nextgen/r/Alq6lAxKRD2IJkZkd-KFDw%2Crg-foundry-core-6fe574%2C%2Caif-core-6fe574%2Cproject-admin-6fe574/build/evaluations/redteam/eval_4f72ed245def4168bba805b3d18cc726/run/evalrun_1e36a2f6f34a4575b226592c53ec355e)

> **Multiple red-team runs against the storytelling agent — compare attack categories side by side.** [Red team — storytelling](https://ai.azure.com/nextgen/r/Alq6lAxKRD2IJkZkd-KFDw%2Crg-foundry-core-6fe574%2C%2Caif-core-6fe574%2Cproject-admin-6fe574/build/evaluations/redteam/eval_b970976886be483bb70e3150a690b20a)

> **Defender for Cloud recommendations + AI threat signals surfaced inside Foundry Operate.** [Defender signals in Operate](https://ai.azure.com/nextgen/r/Alq6lAxKRD2IJkZkd-KFDw,rg-foundry-core-6fe574,,aif-core-6fe574,project-admin-6fe574/operate/compliance/defenderRecommendations)

> **Active fleet alerts to-do list — filterable by security alerts, policy gaps, eval threshold breaches.** [Operate alerts](https://ai.azure.com/nextgen/r/Alq6lAxKRD2IJkZkd-KFDw,rg-foundry-core-6fe574,,aif-core-6fe574,project-admin-6fe574/operate/overview/alerts)

> **Defender for Cloud alert detail for a captured jailbreak attempt against the bank agent — full investigation context, accessed via the deep-link from Operate alerts.** [Defender alert detail](https://portal.azure.com/#view/Microsoft_Azure_Security_AzureDefenderForData/AlertBlade/alertId/4bdbf6b1-798a-b696-1606-d90dcf5667c7/subscriptionId/025aba94-0c4a-443d-8826-466477e2850f/resourceGroup/rg-foundry-core-6fe574/referencedFrom/alertDeepLink/location/centralus)

## Fleet-wide operations

> **Operate dashboard — fleet-wide to-do list, cost hero stats, usage trends across the subscription.** [Operate overview](https://ai.azure.com/nextgen/r/Alq6lAxKRD2IJkZkd-KFDw,rg-foundry-core-6fe574,,aif-core-6fe574,project-admin-6fe574/operate/overview)

> **Custom Foundry guardrail policy ("Indirect Attack must be on") and the deployments currently violating it.** [Compliance policies](https://ai.azure.com/nextgen/r/Alq6lAxKRD2IJkZkd-KFDw,rg-foundry-core-6fe574,,aif-core-6fe574,project-admin-6fe574/Operate/compliance/policyManagement)

> **All agents (Foundry-built + external via AI Gateway), models, and tools in one fleet listing — start/stop, edit, monitor from here.** [Operate assets](https://ai.azure.com/nextgen/r/Alq6lAxKRD2IJkZkd-KFDw,rg-foundry-core-6fe574,,aif-core-6fe574,project-admin-6fe574/operate/assets/agents)

> **Token-per-minute quota allocation and current usage across all deployments.** [Operate quota — TPM](https://ai.azure.com/nextgen/r/Alq6lAxKRD2IJkZkd-KFDw,rg-foundry-core-6fe574,,aif-core-6fe574,project-admin-6fe574/operate/quota/token-per-minute)
