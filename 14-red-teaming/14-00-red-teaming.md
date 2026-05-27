# AI red teaming

Proactively probe a Foundry-hosted agent or model for safety risks using the **Azure AI Red Teaming Agent** (powered by [PyRIT](https://github.com/Azure/PyRIT)). The scans here exercise the same `gpt-4.1-mini` deployment that the bank-guardrails demo uses, so you can compare attack success rates before and after the custom RAI policy is in place.

> ⚠️ **Region constraint.** The Red Teaming Agent is currently available in **East US 2**, **Sweden Central**, **France Central**, and **Switzerland West** only. The Alpha spoke this lab targets must be in one of those - see the spoke deployment.

## In this chapter

| File | What it does |
|------|-------------|
| [14-01-red-team-basics.ipynb](14-01-red-team-basics.ipynb) | Basic scan against the Alpha-spoke chat model: simple callback, all baseline risk categories, evaluates the model's default safety posture |
| [14-02-red-team-advanced.ipynb](14-02-red-team-advanced.ipynb) | Advanced attack strategies (Base64, ROT13, character-space, Unicode confusables, composite), multi-language prompts (Spanish, French), and custom attack objectives via JSON-seeded prompts |

Both notebooks call the model through the APIM gateway (`GATEWAY_URL` + `ALPHA_GATEWAY_KEY`) using an `AsyncAzureOpenAI` callback, which keeps red-team traffic routed through the same chargeback path as regular agent traffic.

## Architecture

```
PyRIT RedTeam scan
    │
    │  baseline + strategy-mutated objectives
    ▼
Async callback (advanced_callback)
    │
    │  AsyncAzureOpenAI → APIM gateway
    ▼
gpt-4.1-mini on aif-core-{suffix}
    │
    │  responses
    ▼
PyRIT scorer
    │
    │  pass/fail per attack-response pair
    ▼
redteam_*_output/<scan-name>/{results.json, evaluation_results.json}
```

## Resources

- [Run automated safety scans with AI Red Teaming Agent](https://learn.microsoft.com/en-us/azure/ai-foundry/concepts/ai-red-teaming-agent) - official Microsoft Foundry guide
- [`azure-ai-evaluation[redteam]` Python SDK](https://learn.microsoft.com/en-us/python/api/azure-ai-evaluation/azure.ai.evaluation.red_team) - API reference
- [PyRIT on GitHub](https://github.com/Azure/PyRIT) - the open-source toolkit underlying the agent
- [Attack strategy reference](https://learn.microsoft.com/en-us/python/api/azure-ai-evaluation/azure.ai.evaluation.red_team.attackstrategy) - complete list of `AttackStrategy` values

---

[Next: Basic scan →](14-01-red-team-basics.ipynb)
