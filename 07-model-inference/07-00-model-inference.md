# Model Inference

Once Foundry is provisioned and models are deployed centrally in the core, the next question is how teams actually call them. The accompanying notebook walks through the inference paths available behind the APIM gateway — the direct Azure OpenAI client vs. the Foundry project client — and the API surfaces each path supports (chat completions, embeddings, the deep-research model, the server-side model router, the Responses API, server-side multi-turn, and token streaming).

## Directory Contents

| File | Description |
|------|-------------|
| [07-01-models-inference-examples.ipynb](07-01-models-inference-examples.ipynb) | End-to-end inference examples through the APIM gateway: direct client vs project client, chat completions, embeddings, deep-research model, model router, Responses API, multi-turn via `previous_response_id`, and streaming |
