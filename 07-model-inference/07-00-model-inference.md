# Model inference

Once Foundry is provisioned and models are deployed centrally in the core, the next question is how teams actually call them. The accompanying notebook walks through the inference paths available behind the APIM gateway - the direct Azure OpenAI client vs. the Foundry project client - and the API surfaces each path supports (chat completions, embeddings, the deep-research model, the server-side model router, the Responses API, server-side multi-turn, and token streaming). A second notebook migrates a GPT-4o workload to a GPT-5 reasoning model live through the same gateway, surfacing the parameter, reasoning-token, and API-surface gotchas the move introduces.

## In this chapter

| File | Description |
|------|-------------|
| [07-01-models-inference-examples.ipynb](07-01-models-inference-examples.ipynb) | End-to-end inference examples through the APIM gateway: direct client vs project client, chat completions, embeddings, deep-research model, model router, Responses API, multi-turn via `previous_response_id`, and streaming |
| [07-02-migrate-gpt-4o-to-gpt-5.ipynb](07-02-migrate-gpt-4o-to-gpt-5.ipynb) | Live migration of a GPT-4o workload to the `gpt-5-mini` reasoning model through the same gateway: deploy gpt-4o on the core account, then walk the parameter, reasoning-token, empty-output, effort/latency, and Chat Completions vs Responses gotchas |

---

[Next: Model inference examples →](07-01-models-inference-examples.ipynb)
