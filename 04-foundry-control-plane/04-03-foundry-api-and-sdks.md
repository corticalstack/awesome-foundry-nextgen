# Foundry API and SDKs

The Microsoft Foundry SDK provides language-specific client libraries for interacting with Foundry projects, running agents, executing evaluations, and managing connections. The SDK surface is built on top of Azure REST APIs and supports keyless authentication via `DefaultAzureCredential`.

---

## SDK selection

Choose the SDK based on your use case:

| SDK | Use when | Endpoint |
|-----|----------|----------|
| **Foundry SDK** | Building agents, evaluations, or Foundry-specific features | `https://<resource-name>.services.ai.azure.com/api/projects/<project-name>` |
| **OpenAI SDK** | Maximum OpenAI API compatibility; Chat Completions API against Foundry direct models | `https://<resource-name>.openai.azure.com/openai/v1` |
| **Foundry Tools SDKs** | Specific AI services (Speech, Vision, Content Safety, Language, etc.) | Tool-specific endpoints (varies by service) |
| **Agent Framework** | Multi-agent orchestration in code; cloud-agnostic local orchestration | Uses the Foundry project endpoint |

**Resource type note:** A Foundry resource provides all endpoints. An Azure OpenAI resource provides only the `/openai/v1` endpoint.

---

## Foundry SDK

### Project endpoint format

```
https://<resource-name>.services.ai.azure.com/api/projects/<project-name>
```

This matches the `ALPHA_FOUNDRY_PROJECT_ENDPOINT` pattern used in this repository.

### Package versions by language

**Python**

| SDK Version | Portal | Status | Package |
|-------------|--------|--------|---------|
| 2.1.0 | Foundry (new) | Stable | `azure-ai-projects>=2.0.0` |
| 1.x | Foundry (classic) | Stable | `azure-ai-projects==1.0.0` |

```bash
pip install "azure-ai-projects>=2.0.0"
```

**JavaScript / TypeScript**

| SDK Version | Portal | Status | Package |
|-------------|--------|--------|---------|
| 2.1.1 | Foundry (new) | Stable | `@azure/ai-projects` |
| 1.0.1 | Foundry classic | Stable | `@azure/ai-projects` |

```bash
npm install @azure/ai-projects @azure/identity dotenv
```

**.NET**

| SDK Version | Portal | Status | Package |
|-------------|--------|--------|---------|
| 2.0.1 | Foundry (new) | Stable | `Azure.AI.Projects` |
| 2.0.0-beta.1 | Foundry (new) | Preview | `Azure.AI.Projects.OpenAI` |
| 1.x (GA) | Foundry classic | Stable | `Azure.AI.Projects` |

```bash
dotnet add package Azure.AI.Projects
dotnet add package Azure.AI.Projects.OpenAI --prerelease
dotnet add package Azure.Identity
```

**Java**

| SDK Version | Portal | Status | Package |
|-------------|--------|--------|---------|
| 2.1.0-beta.1 | Foundry (new) | Preview | `azure-ai-projects`, `azure-ai-agents` |

---

### Authentication

All SDK samples use `DefaultAzureCredential`, which resolves credentials in this order: environment variables, workload identity, managed identity, Visual Studio Code, Azure CLI, Azure PowerShell.

The Entra auth scope for the project endpoint is `https://ai.azure.com/.default`.

API keys work on the `/openai/v1` endpoint (pass as `api_key`). The Foundry project endpoint requires token-based auth.

**Prerequisites (RBAC):**

| Role | Minimum permissions |
|------|---------------------|
| Foundry User | Development access; can call models and agents |
| Foundry Project Manager | Can manage Foundry projects |
| Contributor / Owner | Subscription-level provisioning |

See [Built-in Foundry roles](04-01-foundry-enterprise-provisioning.md#built-in-foundry-roles) for full role definitions and permissions.

---

### Client types

The Foundry SDK provides two client patterns:

- **Project client** (`AIProjectClient`) - for Foundry-native operations: listing connections, retrieving project properties, enabling tracing
- **OpenAI-compatible client**: for Foundry functionality built on OpenAI concepts (Responses API, agents, evaluations, fine-tuning). Served on the `/openai` route of the project endpoint.

---

### Python client initialisation

```python
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

project_client = AIProjectClient(
    endpoint="https://<resource-name>.services.ai.azure.com/api/projects/<project-name>",
    credential=DefaultAzureCredential()
)

with project_client.get_openai_client() as openai_client:
    response = openai_client.responses.create(
        model="gpt-4.1-mini",
        input="What is the capital of France?",
    )
    print(response.output_text)
```

### JavaScript client initialisation

```javascript
import { DefaultAzureCredential } from "@azure/identity";
import { AIProjectClient } from "@azure/ai-projects";

const projectEndpoint = "https://<resource-name>.services.ai.azure.com/api/projects/<project-name>";
const project = new AIProjectClient(projectEndpoint, new DefaultAzureCredential());

const openAIClient = await project.getOpenAIClient();
const response = await openAIClient.responses.create({
    model: "gpt-4.1-mini",
    input: "What is the capital of France?",
});
console.log(response.output_text);
```

### Java client initialisation

```java
import com.azure.ai.projects.ProjectsClient;
import com.azure.ai.projects.ProjectsClientBuilder;
import com.azure.identity.DefaultAzureCredentialBuilder;

ProjectsClient projectClient = new ProjectsClientBuilder()
    .credential(new DefaultAzureCredentialBuilder().build())
    .endpoint("https://<resource-name>.services.ai.azure.com/api/projects/<project-name>")
    .buildClient();
```

### C# client initialisation

```csharp
using Azure.AI.Projects.OpenAI;
using Azure.Identity;

AIProjectClient projectClient = new(
    endpoint: new Uri("https://<resource-name>.services.ai.azure.com/api/projects/<project-name>"),
    tokenProvider: new DefaultAzureCredential());
```

---

## What you can do with the Foundry SDK

- Call Foundry models and Azure OpenAI deployments via the Responses API
- Create and manage agents via the Foundry Agent Service
- Run batch evaluations against agent outputs
- Enable distributed tracing (Application Insights / OTel)
- Fine-tune models
- List connections and retrieve project configuration

---

## OpenAI SDK (OpenAI-compatible endpoint)

Use the OpenAI SDK when you need the full OpenAI API surface or maximum client compatibility. The Foundry-specific features (agents, evaluations) are not available via this endpoint.

**Endpoint:** `https://<resource-name>.openai.azure.com/openai/v1`

```python
from openai import OpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

token_provider = get_bearer_token_provider(
    DefaultAzureCredential(), "https://ai.azure.com/.default"
)

client = OpenAI(
    base_url="https://<resource-name>.openai.azure.com/openai/v1/",
    api_key=token_provider,
)

response = client.responses.create(
    model="gpt-4.1-mini",
    input="What is the capital of France?"
)
print(response.output_text)
```

---

## Agent Framework (local orchestration)

The Microsoft Agent Framework is an open-source SDK for building multi-agent systems in .NET and Python with a cloud-agnostic interface. It is paired with the Foundry SDK when agents need to run against Foundry models.

- Python package: `agent-framework-azure-ai`, `agent-framework-azure-ai-search`
- Minimum version: `>=1.0.0rc5`
- Reference: [Microsoft Agent Framework overview](https://learn.microsoft.com/en-us/agent-framework/overview/agent-framework-overview)

---

## Foundry Tools SDKs (AI Services)

Foundry Tools SDKs (formerly Azure AI Services / Cognitive Services) provide client libraries for specific AI capabilities. These use a different endpoint pattern: `https://<your-resource-name>.cognitiveservices.azure.com/`.

### Python packages

| Service | Package |
|---------|---------|
| Speech | `azure-cognitiveservices-speech` |
| Content Safety | `azure-ai-contentsafety==1.0.0` |
| Document Intelligence | `azure-ai-documentintelligence==1.0.0b1` |
| Azure AI Search | `azure-search-documents==11.6.0b1` |
| Language (text analysis) | `azure-cognitiveservices-language-textanalytics` |
| Vision | `azure-ai-vision-imageanalysis` |
| Translator | `azure-ai-translation-text==1.0.0b1` |

### JavaScript packages

| Service | Package |
|---------|---------|
| Speech | `microsoft-cognitiveservices-speech-sdk` |
| Content Safety | `@azure-rest/ai-content-safety@1.0.0-beta.1` |
| Document Intelligence | `@azure-rest/ai-document-intelligence@1.0.0-beta.1` |
| Azure AI Search | `@azure/search-documents@12.0.0` |
| Language (text analysis) | `@azure/ai-language-text` |
| Vision | `@azure-rest/ai-vision-image-analysis@1.0.0-beta.2` |

---

## Troubleshooting

| Issue | Resolution |
|-------|-----------|
| `DefaultAzureCredential failed to retrieve a token` | Run `az login`; confirm Foundry User role on the Foundry project |
| `Connection refused` or `404 Not Found` | Verify endpoint format matches `https://<resource-name>.services.ai.azure.com/api/projects/<project-name>` |
| `AttributeError` or `ModuleNotFoundError` | Run `pip show azure-ai-projects` to verify version; 2.x SDK requires the Foundry (new) portal; 1.x requires Foundry classic |
| Model not found | Confirm deployment name matches the model deployment in the Foundry portal |

---

## Resources

- [Azure AI Foundry REST API reference](https://learn.microsoft.com/en-us/rest/api/aifoundry/)
- [Foundry SDK overview](https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/develop/sdk-overview)
- [azure-ai-projects on PyPI](https://pypi.org/project/azure-ai-projects/)
- [Microsoft Agent Framework overview](https://learn.microsoft.com/en-us/agent-framework/overview/agent-framework-overview)

---

[Next: Foundry costs →](04-04-foundry-costs.md)
