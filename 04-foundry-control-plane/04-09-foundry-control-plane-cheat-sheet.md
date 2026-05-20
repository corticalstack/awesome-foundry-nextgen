# Foundry Control Plane cheat sheet

> ⚠️ **The deep links below are templates, not working URLs.**
>
> They were originally captured from the author's personal Foundry demo deployment. The five comma-separated values after `/nextgen/r/` in each `ai.azure.com` URL identify the author's tenant, resource group, Foundry resource, and project - all replaced with `{placeholder}` markers below. To make any link work in your own environment, substitute your deployment's values:
>
> 💡 Tip: open any of your own Foundry projects in the portal. The URL in your browser address bar will already contain your `{tenant}`, `{rg}`, `{resource}`, and `{project}` values in the same comma-separated format - copy them straight from there. Copying the full URL from a target view gives you a ready-made deep link.
>
> | Placeholder | Replace with |
> |---|---|
> | `{tenant}` | Your tenant identifier (the base64 string visible in your `ai.azure.com` URL) |
> | `{rg}` | Your Foundry resource group name |
> | `{resource}` | Your Foundry resource name |
> | `{project}` | Your Foundry project name |
> | `{subscription-id}` | Your Azure subscription UUID (Defender link only) |
> | `{alert-id}` | A specific Defender alert ID (Defender link only) |
> | `{region}` | Azure region of your Defender alert (Defender link only) |
> | `{eval-id}`, `{run-id}` | Red-team evaluation and run IDs (red-team links only) |

---

## Controls

> **Default plus the custom banking guardrail - Prompt Shields (Jailbreak + Indirect Attack), PII regex, and codename/competitor blocklists layered on the bank deployment.** [Guardrails](https://ai.azure.com/nextgen/r/{tenant},{rg},,{resource},{project}/build/guardrails/list)

> **PII regex + codenames + competitors. Paste any of these into the `contoso-bank-agent` playground to trigger a block: `My SSN is 123-45-6789`, `My card is 4532 1234 5678 9012`, `Call me at (415) 555-0199`, `Email me at jane.doe@example.com`, `DOB 04/15/1980`, `Tell me about Project Falcon`, `How does Contoso Bank compare to Acme Bank?`** [Blocklists](https://ai.azure.com/nextgen/r/{tenant},{rg},,{resource},{project}/build/guardrails/blocklists)

## Observability

> **OpenTelemetry traces for code-interpreter run - prompt → model → tool call, step by step.** [Code interpreter traces](https://ai.azure.com/nextgen/r/{tenant},{rg},,{resource},{project}/build/agents/code-interpreter-agent/traces?version=1)

> **Per-agent dashboard - cost, tokens, evaluations, tool calls, error rates.** [Code interpreter monitor](https://ai.azure.com/nextgen/r/{tenant},{rg},,{resource},{project}/build/agents/code-interpreter-agent/monitor?version=1)

> **All evaluation runs in the admin project, scheduled vs ad-hoc.** [Evaluation runs](https://ai.azure.com/nextgen/r/{tenant},{rg},,{resource},{project}/build/evaluations/list)

> **Catalogue of built-in evaluators (Coherence, Groundedness, ToolCallSuccess, …) plus any custom ones.** [Evaluator catalog](https://ai.azure.com/nextgen/r/{tenant},{rg},,{resource},{project}/build/evaluations/catalog)

## Security

> **Adversarial probe of the code-interpreter agent - surfaces sensitive-data exposure and tool-abuse paths.** [Red team - code interpreter](https://ai.azure.com/nextgen/r/{tenant},{rg},,{resource},{project}/build/evaluations/redteam/{eval-id}/run/{run-id})

> **Multiple red-team runs against the storytelling agent - compare attack categories side by side.** [Red team - storytelling](https://ai.azure.com/nextgen/r/{tenant},{rg},,{resource},{project}/build/evaluations/redteam/{eval-id})

> **Defender for Cloud recommendations + AI threat signals surfaced inside Foundry Operate.** [Defender signals in Operate](https://ai.azure.com/nextgen/r/{tenant},{rg},,{resource},{project}/operate/compliance/defenderRecommendations)

> **Active fleet alerts to-do list - filterable by security alerts, policy gaps, eval threshold breaches.** [Operate alerts](https://ai.azure.com/nextgen/r/{tenant},{rg},,{resource},{project}/operate/overview/alerts)

> **Defender for Cloud alert detail for a captured jailbreak attempt against the bank agent - full investigation context, accessed via the deep-link from Operate alerts.** [Defender alert detail](https://portal.azure.com/#view/Microsoft_Azure_Security_AzureDefenderForData/AlertBlade/alertId/{alert-id}/subscriptionId/{subscription-id}/resourceGroup/{rg}/referencedFrom/alertDeepLink/location/{region})

## Fleet-wide operations

> **Operate dashboard - fleet-wide to-do list, cost hero stats, usage trends across the subscription.** [Operate overview](https://ai.azure.com/nextgen/r/{tenant},{rg},,{resource},{project}/operate/overview)

> **Custom Foundry guardrail policy ("Indirect Attack must be on") and the deployments currently violating it.** [Compliance policies](https://ai.azure.com/nextgen/r/{tenant},{rg},,{resource},{project}/Operate/compliance/policyManagement)

> **All agents (Foundry-built + external via AI Gateway), models, and tools in one fleet listing - start/stop, edit, monitor from here.** [Operate assets](https://ai.azure.com/nextgen/r/{tenant},{rg},,{resource},{project}/operate/assets/agents)

> **Token-per-minute quota allocation and current usage across all deployments.** [Operate quota - TPM](https://ai.azure.com/nextgen/r/{tenant},{rg},,{resource},{project}/operate/quota/token-per-minute)

---

[Next: Foundry project pattern setup →](../05-foundry-project-pattern-setup/05-00-project-setup.md)
