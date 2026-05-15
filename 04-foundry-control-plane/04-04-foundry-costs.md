For example, the cost of using Agent Service is the costs incurred from the model you deploy and the Azure resources you use for your project (for example, logging and any customer-managed resources you connect).

When you create a Foundry resource, you pay for the Azure services you use, such as Azure OpenAI, Azure Speech in Foundry, Content Safety, Azure Vision in Foundry, Azure Document Intelligence, and Azure Language in Foundry. Costs vary by service and feature. For details, see the [Foundry Tools pricing page](https://azure.microsoft.com/pricing/details/cognitive-services/).

# Introduction
Microsoft Foundry is monetized through individual products customer access and consume in the platform, including API and models, complete AI toolchain, and responsible AI and enterprise grade production at scale products. Each product has its own billing model and price.

The platform is free to use and explore. Pricing occurs at deployment level.

---

# Cost Components

## Foundry Agent Service

Creating and running Foundry-native agents using prompts and workflows incurs **no additional charge** beyond the underlying resources consumed. Charges accrue for:

- **Model token consumption** — via Foundry Models (pay-per-token or provisioned throughput)
- **Knowledge tools** — Microsoft Fabric, Microsoft SharePoint, Grounding with Bing Search, Azure AI Search
- **Action tools** — Azure Logic Apps, Azure Functions (billed at their standard rates)

## Foundry Models (Azure OpenAI and Microsoft models)

Two billing models are available:

| Billing model | Description | Best for |
|---------------|-------------|---------|
| **Pay-as-you-go (Serverless API)** | Billed per token consumed; no upfront commitment | Variable or unpredictable workloads |
| **Provisioned throughput** | Commitment-based; fixed capacity reserved | Predictable, high-volume workloads |

**Indicative pay-as-you-go rates (subject to change; verify at [pricing page](https://azure.microsoft.com/en-us/pricing/details/ai-foundry-models/aoai/)):**

| Model | Input cost | Output cost |
|-------|-----------|-------------|
| GPT-4o | ~$2.50 / million tokens | ~$10.00 / million tokens |
| Phi-4-mini | ~$0.000075 / token | ~$0.0003 / token |

Always verify current rates on the official Azure pricing pages, as rates change.

## Fine-tuned Models

Fine-tuned model deployments incur three charge types:

| Charge type | Description |
|-------------|-------------|
| **Training** | Per-token or per-hour depending on the base model |
| **Hosting** | Hourly cost per deployed fine-tuned model endpoint (charged even when idle) |
| **Inference** | Per 1,000 tokens (input and output) |

> **Note:** Fine-tuned deployments inactive for more than 15 days may be automatically deleted.

## Foundry Tools (AI Services)

Foundry Tools (formerly Azure AI Services / Cognitive Services) use two billing models:

| Billing model | Description |
|---------------|-------------|
| **Serverless API** | Pay-as-you-go per unit of usage for each tool |
| **Commitment tiers** | Fixed monthly or annual fee; overage billed separately |

Commitment tiers can reduce costs by up to 70% compared to pay-as-you-go. Services billed under Foundry Tools include: Azure OpenAI, Azure Speech in Foundry, Content Safety, Azure Vision in Foundry, Azure Document Intelligence in Foundry, and Azure Language in Foundry.

## AI Gateway (API Management)

Setting up the AI Gateway is **free**. Standard Azure API Management request charges apply for traffic routed through the gateway. The gateway enables rate limiting, quota management, and observability at no additional platform cost beyond APIM usage.

## Storage and Compute

The following services accrue costs when used with Foundry projects:

| Service | When billed |
|---------|-------------|
| Azure Blob Storage | Project file storage (continuous) |
| Azure AI Search | Vector index storage and query operations |
| Azure Machine Learning compute | Prompt flow compute instances (billed per hour running) |
| Azure Container Registry | Docker image storage for custom containers |
| Key Vault | Required for customer-managed key (CMK) double encryption |
| Application Insights | Telemetry storage and query (billed by data volume) |
| Azure Private Link | Private endpoint network access |

**Costs that persist after deleting a Foundry core:**
- Azure Container Registry
- Azure Blob Storage
- Key Vault
- Application Insights (if enabled)

---

# Cost Management Tools

## Azure Cost Management + Billing

Use Azure Cost Management to track spending by resource group, subscription, or tag. Filter by resource group to isolate project-level costs from hub-level infrastructure costs.

**Example:** In a resource group `rg-contoso-ai`, total resource group cost might be $174.71 while costs scoped to a specific project (`contoso-proj`) total $8.40.

## Quota Dashboards

The Foundry portal exposes quota usage under **Operate** → **Quota**. Each deployment shows current token usage against the allocated tokens-per-minute (TPM) limit. Use this view to identify under- or over-provisioned deployments.

## Azure Cost Alerts

Azure OpenAI does not support hard spending limits. Use Azure Cost Management budget alerts with action groups to trigger notifications or automated responses when spending exceeds thresholds.

**Note:** Azure Prepayment (monetary commitment) credit can be used for models sold directly by Azure (including Azure OpenAI) but **cannot** be used for third-party Marketplace models.

---

# Cost Optimisation Recommendations

## Set token rate limits

Configure TPM rate limits per deployment in the AI Gateway to prevent runaway consumption. This is especially important during development when agents may run long loops unexpectedly.

## Right-size model selection

Use smaller, lower-cost models (e.g., Phi-4-mini, GPT-4o-mini) for tasks that do not require the capabilities of larger models. Reserve larger models for tasks where output quality is demonstrably better.

## Use provisioned throughput for predictable workloads

For steady-state production workloads with predictable token volume, provisioned throughput pricing is typically lower than pay-as-you-go at scale.

## Batch inference where possible

Use batch evaluation and batch inference endpoints instead of synchronous calls for offline processing tasks. Batch endpoints typically offer lower per-token costs.

## Clean up unused deployments

Fine-tuned model hosting is billed by the hour regardless of usage. Delete unused fine-tuned model deployments when they are not actively needed.

## Monitor with tags

Apply Azure resource tags to Foundry projects and associated resources to enable cost reporting by team, workload, or environment.

---

# Pricing Reference URLs

| Resource | URL |
|----------|-----|
| Microsoft Foundry platform | https://azure.microsoft.com/en-us/pricing/details/microsoft-foundry/ |
| Foundry Agent Service | https://azure.microsoft.com/en-us/pricing/details/foundry-agent-service/ |
| Foundry Models (Azure OpenAI) | https://azure.microsoft.com/en-us/pricing/details/ai-foundry-models/aoai/ |
| Foundry Tools | https://azure.microsoft.com/en-us/pricing/details/foundry-tools/ |
| Azure AI Search | https://azure.microsoft.com/pricing/details/search/ |
| Azure pricing calculator | https://azure.microsoft.com/pricing/calculator/ |

# Resources
https://learn.microsoft.com/en-us/azure/ai-foundry/concepts/manage-costs?view=foundry
