# Fine-tuning with knowledge distillation

## Learning objectives

By the end of this lab you will be able to:

- **Knowledge distillation**: Use a large teacher model (gpt-4.1-mini via APIM) to generate high-quality labelled training data for a smaller student model (Phi-4-mini)
- **LoRA fine-tuning with PEFT/Olive**: Apply parameter-efficient fine-tuning using the Olive AI toolkit and the PEFT library to adapt Phi-4-mini for a narrow domain classification task
- **ACA GPU job orchestration**: Submit, monitor, and retrieve results from serverless GPU workloads on Azure Container Apps (NC24-A100 profile) without managing dedicated GPU infrastructure
- **Evaluation pipeline**: Compare teacher, base, and fine-tuned model accuracies using an ACA evaluation job, then visualise results in a matplotlib chart

---

## Architecture

```
APIM Gateway
  └─ gpt-4.1-mini (teacher)          ← generates synthetic training labels
       │
       ▼
  Synthetic Training Data (JSONL)     ← stored in Azure Blob Storage (ft container)
       │
       ▼
  ACA GPU Job (NC24-A100)             ← Olive LoRA fine-tuning
    Base model: Phi-4-mini-instruct
    Method:     LoRA (PEFT)
    Targets:    qkv_proj, o_proj, gate_up_proj, down_proj
       │
       ▼
  LoRA Adapter (ft/adapter)           ← uploaded back to Blob Storage
       │
       ▼
  ACA Evaluation Job (NC24-A100)      ← loads adapter + runs classification
       │
       ▼
  Accuracy Comparison Chart           ← teacher vs base vs fine-tuned
       │
       ▼
  Local Inference Demo                ← adapter downloaded, runs offline (CPU/MPS/CUDA)
```

**Teacher model note**: The lab is designed around `gpt-4.1-mini` (already deployed via the shared APIM gateway) as the teacher. DeepSeek-V3.2 can be substituted as teacher if it is routed through the same APIM gateway - simply set `CHAT_MODEL=DeepSeek-V3.2` in `.env`. The notebooks reference `os.getenv('CHAT_MODEL', 'gpt-4.1-mini')` so no code changes are required.

**Regional note**: The ACA environment is always deployed to **Sweden Central** because GPU workload profiles (NC24-A100 `Consumption-GPU-NC24-A100`) are only available there. All other resources (storage account, Foundry project) use the resource group's default region.

---

## Lab structure

| Notebook | Description |
|---|---|
| [15-01-data-preparation.ipynb](15-01-data-preparation.ipynb) | Fetch ISS reports, evaluate teacher model, generate synthetic LoRA training data |
| [15-02-fine-tune.ipynb](15-02-fine-tune.ipynb) | Provision ACA/storage infrastructure, submit Olive LoRA fine-tuning job, monitor |
| [15-03-evaluate.ipynb](15-03-evaluate.ipynb) | Upload eval data, submit ACA evaluation job, download results, render accuracy chart |
| [15-04-local-inference.ipynb](15-04-local-inference.ipynb) | Download fine-tuned adapter, load model locally, run live classification demo |

---

## Prerequisites

1. **Core gateway deployed** - the shared APIM gateway and hub account must be provisioned. `GATEWAY_URL` must resolve to your APIM endpoint.

2. **`.env` populated** - add the following to your `.env` file (see [`.env.example`](../.env.example) for the full block):

   ```
   GATEWAY_URL=https://<apim-name>.azure-api.net/openai
   CHAT_MODEL=gpt-4.1-mini
   ALPHA_GATEWAY_KEY=<existing apim subscription key for alpha>
   FINETUNE_FOUNDRY_PROJECT_ENDPOINT=https://aif-spoke-multi-{suffix}.services.ai.azure.com/api/projects/finetune-project
   FINETUNE_APIM_CONNECTION=finetune-apim-connection
   FINETUNE_RESOURCE_GROUP=rg-foundry-multi-{suffix}
   FINETUNE_STORAGE_ACCOUNT=issft{suffix}
   FINETUNE_ACA_ENVIRONMENT=acae-finetune-{suffix}
   ```

   > **No dedicated finetune APIM key.** The teacher-model calls only need a valid APIM subscription key for the shared gateway, so the notebooks reuse `ALPHA_GATEWAY_KEY` (already in `.env` from the project-spoke deployment) rather than provisioning a separate `foundry-gateway-finetune` subscription. This removes one resource and one extra env variable. If you want isolated quotas later, you can create a dedicated APIM subscription and wire its key in - the call site is straightforward to swap.

3. **Azure CLI logged in** - run `az login` and ensure you have Contributor access to the resource group.

4. **`uv` installed** - install dependencies with:
   ```bash
   uv sync --group finetune
   ```

   This section needs heavy ML dependencies (PyTorch, Hugging Face Transformers, PEFT) that are not in the base install. They live in the `finetune` dependency group in `pyproject.toml`. Plain `uv sync` will leave `torch` / `transformers` / `peft` / `matplotlib` / `azure-storage-blob` / `azure-ai-inference` missing and the notebooks will fail with `ModuleNotFoundError`. The `--group finetune` flag pulls them in.

   > The base install was kept lean because the fine-tuning group adds ~3 GB (PyTorch + CUDA libs). Once you've synced the group it persists in `.venv`; you don't need the flag on subsequent `uv sync` calls.

5. **Bicep deployed** - deploy this lab's infrastructure into the existing multi-spoke resource group:
   ```bash
   az deployment group create \
     --resource-group rg-foundry-multi-{suffix} \
     --template-file 15-fine-tune/main.bicep \
     --parameters deployerPrincipalId=$(az ad signed-in-user show --query id -o tsv) \
                  apimUrl=$GATEWAY_URL \
                  apimSubscriptionKey=$ALPHA_GATEWAY_KEY \
                  existingAccountName=aif-spoke-multi-{suffix}
   ```

---

## Expected outcomes

| Model | Accuracy |
|---|---|
| gpt-4.1-mini (teacher) | ~75-85% |
| Phi-4-mini base | ~40-50% (reference: 45.7%) |
| Phi-4-mini fine-tuned | ~55-65% |

The fine-tuned model is expected to improve on the base model by 5-15 percentage points on the ISS incident severity classification task. This gap arises from LoRA adapting the model weights to the domain-specific instruction format and severity definitions.

---

## Out of scope

- **Quantization / Olive INT4 export** - post-training quantisation for edge deployment is not covered
- **Pipeline automation** - notebooks are run manually; orchestration (Azure ML pipelines, Prefect, etc.) is not included
- **ISS domain changes** - `iss_utils.py` is preserved as-is; adding new incident categories or changing the classification schema is outside scope
- **Adding DeepSeek-V3.2 to APIM** - configuring the APIM backend for DeepSeek is tracked as optional future work in GitHub issue #21

---

[Next: Data preparation →](15-01-data-preparation.ipynb)
