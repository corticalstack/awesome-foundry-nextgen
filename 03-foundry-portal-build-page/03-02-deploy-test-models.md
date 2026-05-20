# Deploy and test models

You can use the Foundry UI to deploy a model in a Foundry project for inference - models for text responses or image generation. After you deploy a Foundry Model, you can interact with it in the Foundry Playground and use it from code.

## Prerequisites

- The Cognitive Services Contributor role (or equivalent) on the Foundry resource, to create and manage deployments.
- For Foundry Models from partners and community (such as the Llama or Anthropic series), an Azure Marketplace subscription. Foundry Models sold directly by Azure (such as OpenAI gpt models) don't require this.

## Deployment options

When you deploy a model you can choose **default settings** for a global standard deployment with default quota, or customise the deployment to select your own SKU, quota, and guardrails.

Note: each model supports different deployment types, providing different data residency or throughput guarantees.

## Regional availability and quota

For Foundry Models, default quota varies by model and region. Certain models are only available in some regions - see [Models sold directly by Azure](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-models/concepts/models-sold-directly-by-azure).

## Model deployment tabs

Once deployed, a model has three tabs you can switch between.

### Playground Tab

The Playground lets you select the model from a drop-down and adjust parameters such as past messages included, max tokens, and temperature. You can also add a system prompt, for example:

> You are an AI assistant that helps people find information.

#### Adding tools

Connect tools to your model to extend what it can work with - retrieving information from SharePoint, adding a code interpreter to create a bar graph from Excel data, or web search to ground the model in the latest online information.

![alt text](../docs/screenshots/model-web-search-grounding-tool.png)

### Details Tab

- Shows the model target URI and API key (if enabled).
- Model name, deployment type, and provisioning state.
- TPM (tokens per minute) and RPM (requests per minute) rate limits.

### Monitor Tab

By time window (custom date range, last day, last 7 days, last month), shows metrics for:

- Total requests
- Total token count
- Estimated total cost
- Input token count
- Output token count
- Time to first byte

Note: you can use Ask AI for canned queries on these metrics.

## Resources

- [Deploy a Foundry model with code](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-models/how-to/create-model-deployments?view=foundry&pivots=programming-language-cli)

---

[Next: Foundry Control Plane →](../04-foundry-control-plane/04-00-control-plane.md)
