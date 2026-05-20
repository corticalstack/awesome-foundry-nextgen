# Region availability

Microsoft Foundry brings together Azure AI capabilities that were previously only available as standalone Azure services. Feature availability varies by region. This document lists the Azure regions where Foundry projects can be created, the features with region-specific constraints, and guidance for selecting a region.

---

## Regions supporting Foundry projects

The following Azure regions support the creation of Foundry projects (as of 2026-04):

| Region | Region |
|--------|--------|
| Australia East | Norway East |
| Brazil South | Qatar Central |
| Canada Central | South Africa North |
| Canada East | South Central US |
| Central India | South India |
| Central US | Southeast Asia |
| East Asia | Spain Central |
| East US | Sweden Central |
| East US 2 | Switzerland North |
| France Central | UAE North |
| Germany West Central | UK South |
| Italy North | US Gov Arizona † |
| Japan East | US Gov Virginia † |
| Korea Central | West Europe |
| North Central US | West US |
| North Europe | West US 3 |

† Sovereign cloud (Azure Government) - see [Sovereign cloud availability](#sovereign-cloud-availability) below.

> **Note:** Switzerland West is not listed as a supported Foundry region. Azure has a Switzerland West datacenter, but the Foundry region-support page only enumerates Switzerland North, so projects can't be created there. If data residency in Switzerland is the driver, Switzerland North is the only option for Foundry today.

This list reflects the documentation snapshot at the primary source URL above. Verify against the [Azure global infrastructure products by region](https://azure.microsoft.com/global-infrastructure/services/) page before production deployments.

---

## Feature availability by region

Not all Foundry features are available in every supported region. The following table links to the authoritative regional availability pages for each feature:

| Feature | Notes | Authoritative Regional Page |
|---------|-------|-----------------------------|
| Azure OpenAI | Some models may not be available in all regions via the Foundry model catalog | [Azure OpenAI Regional Quota Capacity Limits](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/quotas-limits#regional-quota-capacity-limits) |
| Speech capabilities | Custom neural voice varies by hardware availability | [Speech service supported regions](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/regions) |
| Azure AI Content Safety | Must create resource in a supported region | [Content Safety region availability](https://learn.microsoft.com/en-us/azure/ai-services/content-safety/overview#region-availability) |
| Foundry Agent Service | Supports Azure OpenAI model deployments; exact model and tool availability varies by region | [Agent Service region availability](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/concepts/limits-quotas-regions#supported-regions) |

---

## Global vs regional model deployments

Azure OpenAI offers two deployment types that affect regional availability:

| Deployment type | Description | Implications |
|-----------------|-------------|--------------|
| **Regional** | Traffic served from the specified Azure region only | Predictable data residency; quota allocated per region |
| **Global** | Traffic may be served from any region Microsoft determines optimal | Higher throughput potential; data may leave the selected region |

For workloads with data residency requirements, use regional deployments and select the appropriate region at deployment time. Global deployments do not guarantee data stays within a geographic boundary.

---

## Region selection guidance

Consider the following factors when selecting a region for a Foundry project:

### Model availability

Check the [Azure OpenAI model availability list](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-models/concepts/models-sold-directly-by-azure) for the target region before committing. Not all models are available in all regions. The Azure OpenAI quota and limits page is the authoritative source.

### Quota availability

Azure OpenAI quotas are allocated per region, per subscription, and per model or deployment type. A region that supports a model may still have insufficient quota for your expected token throughput. Submit an [Azure OpenAI quota increase request](https://aka.ms/oai/stuquotarequest) before production rollout.

### Dependent services

Ensure all services your Foundry project depends on are available in the selected region:

- Azure AI Content Safety resource must be in a supported region
- Azure Speech resources are region-specific; endpoints only serve requests in the same region as the resource
- Azure AI Search (if used for retrieval) has its own regional availability constraints

### Data residency and compliance

For regulatory requirements (GDPR, data sovereignty), use regional deployments in EU regions (e.g., Sweden Central, West Europe, Germany West Central, France Central). Review the [Azure compliance documentation](https://learn.microsoft.com/en-us/azure/compliance/) for sovereign cloud options.

### Latency

Select a region geographically close to your end users or compute workloads to minimise inference latency. For multi-region deployments, consider using AI Gateway (APIM) with a model router to distribute traffic.

---

## Sovereign cloud availability

Foundry is available in **Azure Government** for US government entities and their partners. The portal URL differs from the public cloud:

| Cloud | Portal URL | Regions |
|-------|------------|---------|
| Azure (public) | https://ai.azure.com/ | All regions in the table above except those marked † |
| Azure Government | https://ai.azure.us/ | US Gov Arizona, US Gov Virginia |

### Azure Government feature constraints

Several Foundry features are **not** supported in Azure Government regions:

- Serverless endpoints
- Content Understanding
- Agents playground, Images playground, Real-time audio playground, Healthcare playground
- Fine-tuning
- Azure AI Agents
- Batch jobs
- Azure OpenAI Evaluation
- Deploy Web App
- VS Code Extension

Supported features include Azure OpenAI in Foundry Models, Foundry Tools (Speech, Language, Translator, Vision, Document, Content Safety), the model catalog (subject to [machine learning cloud parity](https://learn.microsoft.com/en-us/azure/machine-learning/reference-machine-learning-cloud-parity)), Tracing, Guardrails, and Controls.

For a full comparison, see [Compare Azure Government and global Azure](https://learn.microsoft.com/en-us/azure/azure-government/compare-azure-government-global-azure).

---

## Pre-production checklist

Before deploying a Foundry project to production in a selected region:

- [ ] Required model is available in the target region (verified in Azure OpenAI quotas page)
- [ ] Sufficient token quota exists in that region for expected traffic volume
- [ ] All dependent services (Speech, Content Safety, Agent Service tools) are available in that region
- [ ] Data residency and compliance requirements are met by the selected region
- [ ] Foundry project creation has been validated in the portal for the subscription and tenant

---

## Troubleshooting region issues

| Issue | Resolution |
|-------|-----------|
| Model not available in selected region | Check the Azure OpenAI model availability list; consider a different region or global deployment |
| Insufficient quota | Request a quota increase via Azure portal; consider distributing load across regions |
| Content Safety resource creation fails | Verify the resource is created in a [supported Content Safety region](https://learn.microsoft.com/en-us/azure/ai-services/content-safety/overview#region-availability) |
| Speech endpoint returns errors | Confirm the app configuration uses the same region as the Speech resource |
| Agent Service feature missing | Verify Foundry Agent Service is available in the selected region via the linked availability page |

---

## Resources

- [Feature availability across cloud regions (Microsoft Foundry)](https://learn.microsoft.com/en-us/azure/ai-foundry/reference/region-support)
- [Azure global infrastructure products by region](https://azure.microsoft.com/global-infrastructure/services/)
- [Foundry Models sold by Azure (model availability list)](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-models/concepts/models-sold-directly-by-azure)
- [Azure OpenAI quotas and limits](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/quotas-limits)
- [Azure OpenAI quota increase request form](https://aka.ms/oai/stuquotarequest)
- [Foundry Agent Service limits and quotas](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/concepts/limits-quotas-regions)

---

[Next: Foundry API and SDKs →](04-03-foundry-api-and-sdks.md)
