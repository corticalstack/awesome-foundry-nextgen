targetScope = 'resourceGroup'

param location string = resourceGroup().location
param deployerPrincipalId string
@description('Short unique suffix for resource names - computed from subscription ID in the notebook.')
param suffix string

@description('Location for OSS hub deployment.')
param ossLocation string = 'westus3'

// aif = Foundry account (CAF abbreviation for CognitiveServices/accounts kind:AIServices)
var sharedCoreName = 'aif-core-${suffix}'          // primary core: chat + embeddings
var storageName = 'stfoundry${suffix}'           // st = storage account (no hyphens allowed)
var apimName = 'apim-foundry-${suffix}'          // apim = API Management
var researchHubName = 'aif-research-${suffix}'   // research/reasoning models (o3-deep-research)
var ossHubName = 'aif-oss-${suffix}'             // open source models (e.g., Phi-4)

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageName
  location: location
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
}

resource sharedHub 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' = {
  name: sharedCoreName
  location: location
  kind: 'AIServices'
  sku: { name: 'S0' }
  identity: { type: 'SystemAssigned' }
  properties: {
    allowProjectManagement: true
    customSubDomainName: sharedCoreName
    publicNetworkAccess: 'Enabled'
  }
}

resource model 'Microsoft.CognitiveServices/accounts/deployments@2025-04-01-preview' = {
  parent: sharedHub
  name: 'gpt-4.1-mini'
  sku: { name: 'GlobalStandard', capacity: 30 }
  properties: {
    model: { name: 'gpt-4.1-mini', format: 'OpenAI', version: '2025-04-14' }
  }
}

resource embeddingModel 'Microsoft.CognitiveServices/accounts/deployments@2025-04-01-preview' = {
  parent: sharedHub
  name: 'text-embedding-3-large'
  sku: { name: 'Standard', capacity: 50 }
  properties: {
    model: { name: 'text-embedding-3-large', format: 'OpenAI', version: '1' }
  }
  dependsOn: [model]
}

// Admin project - hosts centrally-managed agents, evaluations, observability and load-gen
// workloads (08-05 MCP, 08-06 offline eval, 08-07 live obs, 20-* load gen, 04-09 cheat sheet).
// Lives natively on the core hub so it can use the gpt-4.1-mini and embedding deployments
// directly without going through APIM (keyless, RBAC-only).
resource adminProject 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' = {
  parent: sharedHub
  name: 'project-admin-${suffix}'
  location: location
  identity: { type: 'SystemAssigned' }
  properties: {
    description: 'Admin project for centrally-managed agents, evaluations, observability, and load-gen workloads'
    displayName: 'Admin Project'
  }
}

// =============================================================================
// OSS HUB - open source/community models (westus3/australiaeast/swedencentral)
// =============================================================================

resource ossHub 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: ossHubName
  location: ossLocation
  kind: 'AIServices'
  sku: { name: 'S0' }
  identity: { type: 'SystemAssigned' }
  properties: {
    customSubDomainName: ossHubName
    publicNetworkAccess: 'Enabled'
  }

  resource ossDeployment 'deployments' = {
    name: 'Phi-4'
    properties: {
      model: {
        name: 'Phi-4'
        format: 'Microsoft'
        version: '7'
      }
    }
    sku: {
      name: 'GlobalStandard'
      capacity: 1
    }
  }
}

// =============================================================================
// RESEARCH HUB - reasoning/research models (norwayeast)
// =============================================================================

resource researchHub 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' = {
  name: researchHubName
  location: 'norwayeast'
  kind: 'AIServices'
  sku: { name: 'S0' }
  identity: { type: 'SystemAssigned' }
  properties: {
    allowProjectManagement: true
    customSubDomainName: researchHubName
    publicNetworkAccess: 'Enabled'
  }
}

resource researchModel 'Microsoft.CognitiveServices/accounts/deployments@2025-04-01-preview' = {
  parent: researchHub
  name: 'o3-deep-research'
  sku: { name: 'GlobalStandard', capacity: 10 }
  properties: {
    model: {
      name: 'o3-deep-research'
      format: 'OpenAI'
      version: '2025-06-26'
    }
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
    raiPolicyName: 'Microsoft.DefaultV2'
  }
}

// v2 tier (BasicV2/StandardV2/PremiumV2) required for BYO AI Gateway feature with Foundry Agents.
// BasicV2 is sufficient for public Foundry resources. If the Foundry resource has public network
// access disabled, switch to StandardV2 or PremiumV2 - only those support the private endpoint
// (or VNet injection on PremiumV2) needed to reach a private Foundry resource.
// See: https://learn.microsoft.com/en-us/azure/foundry/configuration/enable-ai-api-management-gateway-portal
resource apim 'Microsoft.ApiManagement/service@2024-06-01-preview' = {
  name: apimName
  location: location
  sku: { name: 'BasicV2', capacity: 1 }
  identity: { type: 'SystemAssigned' }
  properties: {
    publisherEmail: 'admin@contoso.com'
    publisherName: 'Contoso AI'
  }
}

// Grant APIM managed identity access to shared core
resource apimCognitiveServicesUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(sharedHub.id, apim.id, 'CognitiveServicesUser')
  scope: sharedHub
  properties: {
    principalId: apim.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908') // Cognitive Services User
  }
}

// Grant APIM managed identity access to research hub
resource apimCognitiveServicesUserResearch 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(researchHub.id, apim.id, 'CognitiveServicesUser')
  scope: researchHub
  properties: {
    principalId: apim.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908') // Cognitive Services User
  }
}

// Grant APIM managed identity access to OSS hub
resource apimCognitiveServicesUserOss 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(ossHub.id, apim.id, 'CognitiveServicesUser')
  scope: ossHub
  properties: {
    principalId: apim.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908') // Cognitive Services User
  }
}

// Grant deploying user access to shared core
resource deployerCognitiveServicesUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(sharedHub.id, deployerPrincipalId, 'CognitiveServicesUser')
  scope: sharedHub
  properties: {
    principalId: deployerPrincipalId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908') // Cognitive Services User
  }
}

// Grant deploying user access to research hub
resource deployerCognitiveServicesUserResearch 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(researchHub.id, deployerPrincipalId, 'CognitiveServicesUser')
  scope: researchHub
  properties: {
    principalId: deployerPrincipalId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908') // Cognitive Services User
  }
}

// Grant deploying user access to OSS hub
resource deployerCognitiveServicesUserOss 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(ossHub.id, deployerPrincipalId, 'CognitiveServicesUser')
  scope: ossHub
  properties: {
    principalId: deployerPrincipalId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908') // Cognitive Services User
  }
}

resource backend 'Microsoft.ApiManagement/service/backends@2024-06-01-preview' = {
  parent: apim
  name: 'openai'
  properties: {
    url: '${sharedHub.properties.endpoint}openai'
    protocol: 'http'
  }
}

// Backend for research hub (reasoning/research models)
resource researchBackend 'Microsoft.ApiManagement/service/backends@2024-06-01-preview' = {
  parent: apim
  name: 'openai-research'
  properties: {
    url: '${researchHub.properties.endpoint}openai'
    protocol: 'http'
    description: 'Research hub - reasoning and research models'
  }
}

// Backend for OSS hub (open source/community models)
resource ossBackend 'Microsoft.ApiManagement/service/backends@2024-06-01-preview' = {
  parent: apim
  name: 'openai-oss'
  properties: {
    url: '${ossHub.properties.endpoint}openai'
    protocol: 'http'
    description: 'OSS hub - open source and community models'
  }
}

resource api 'Microsoft.ApiManagement/service/apis@2024-06-01-preview' = {
  parent: apim
  name: 'openai'
  properties: {
    displayName: 'OpenAI'
    path: 'openai'
    protocols: ['https']
    subscriptionRequired: true
    subscriptionKeyParameterNames: {
      header: 'api-key'
      query: 'api-key'
    }
  }
}

// Chat Completions operation
resource chatOp 'Microsoft.ApiManagement/service/apis/operations@2024-06-01-preview' = {
  parent: api
  name: 'chat'
  properties: {
    displayName: 'Chat Completions'
    method: 'POST'
    urlTemplate: '/deployments/{deployment-id}/chat/completions'
    templateParameters: [
      { name: 'deployment-id', required: true, type: 'string' }
    ]
  }
}

// Chat Completions - research hub (URL match on o3-deep-research routes here)
resource chatResearchOp 'Microsoft.ApiManagement/service/apis/operations@2024-06-01-preview' = {
  parent: api
  name: 'chat-research'
  properties: {
    displayName: 'Chat Completions (Research)'
    method: 'POST'
    urlTemplate: '/deployments/o3-deep-research/chat/completions'
  }
}

// Policy to route research model requests to research hub backend
resource chatResearchPolicy 'Microsoft.ApiManagement/service/apis/operations/policies@2024-06-01-preview' = {
  parent: chatResearchOp
  name: 'policy'
  properties: {
    format: 'xml'
    value: '<policies><inbound><base /><set-backend-service backend-id="openai-research" /><authentication-managed-identity resource="https://cognitiveservices.azure.com" output-token-variable-name="msi-access-token" ignore-error="false" /><set-header name="Authorization" exists-action="override"><value>@("Bearer " + (string)context.Variables["msi-access-token"])</value></set-header></inbound><backend><base /></backend><outbound><base /></outbound></policies>'
  }
}

// Chat Completions - OSS hub (URL match on Phi-4 routes here)
resource chatOssOp 'Microsoft.ApiManagement/service/apis/operations@2024-06-01-preview' = {
  parent: api
  name: 'chat-oss'
  properties: {
    displayName: 'Chat Completions (OSS)'
    method: 'POST'
    urlTemplate: '/deployments/Phi-4/chat/completions'
  }
}

// Policy to route OSS model requests to OSS hub backend
resource chatOssPolicy 'Microsoft.ApiManagement/service/apis/operations/policies@2024-06-01-preview' = {
  parent: chatOssOp
  name: 'policy'
  properties: {
    format: 'xml'
    value: '<policies><inbound><base /><set-backend-service backend-id="openai-oss" /><authentication-managed-identity resource="https://cognitiveservices.azure.com" output-token-variable-name="msi-access-token" ignore-error="false" /><set-header name="Authorization" exists-action="override"><value>@("Bearer " + (string)context.Variables["msi-access-token"])</value></set-header></inbound><backend><base /></backend><outbound><base /></outbound></policies>'
  }
}

// Responses API operation (for Agents)
resource responsesOp 'Microsoft.ApiManagement/service/apis/operations@2024-06-01-preview' = {
  parent: api
  name: 'responses'
  properties: {
    displayName: 'Responses'
    method: 'POST'
    urlTemplate: '/responses'
  }
}

// Embeddings operation (for vector search)
resource embeddingsOp 'Microsoft.ApiManagement/service/apis/operations@2024-06-01-preview' = {
  parent: api
  name: 'embeddings'
  properties: {
    displayName: 'Embeddings'
    method: 'POST'
    urlTemplate: '/deployments/{deployment-id}/embeddings'
    templateParameters: [
      { name: 'deployment-id', required: true, type: 'string' }
    ]
  }
}

// APIM Policy:
// - Sets backend service to use the defined backend resource
// - Adds default api-version (required for Azure AI Search knowledge base integration)
// - Uses managed identity to authenticate with Cognitive Services backend
// - Rate limits to 100 calls per 60 seconds
resource policy 'Microsoft.ApiManagement/service/apis/policies@2024-06-01-preview' = {
  parent: api
  name: 'policy'
  properties: {
    format: 'xml'
    value: '<policies><inbound><base /><set-backend-service backend-id="openai" /><set-query-parameter name="api-version" exists-action="skip"><value>2024-10-21</value></set-query-parameter><authentication-managed-identity resource="https://cognitiveservices.azure.com" output-token-variable-name="msi-access-token" ignore-error="false" /><set-header name="Authorization" exists-action="override"><value>@("Bearer " + (string)context.Variables["msi-access-token"])</value></set-header><rate-limit calls="100" renewal-period="60" /></inbound><backend><base /></backend><outbound><base /></outbound></policies>'
  }
}

// Create a subscription for API key access
resource apimSubscription 'Microsoft.ApiManagement/service/subscriptions@2024-06-01-preview' = {
  parent: apim
  name: 'foundry-gateway-alpha'
  properties: {
    displayName: 'Foundry Gateway Access (Alpha)'
    scope: '/apis/${api.name}'
    state: 'active'
  }
}

output aiEndpoint string = sharedHub.properties.endpoint
output apimUrl string = '${apim.properties.gatewayUrl}/openai'
output apimName string = apim.name
output apimSubscriptionName string = apimSubscription.name
output chatModelName string = model.name
output embeddingModelName string = embeddingModel.name
output researchModelName string = researchModel.name
output researchHubEndpoint string = researchHub.properties.endpoint
output ossModelName string = ossHub::ossDeployment.name
output ossHubEndpoint string = ossHub.properties.endpoint
output adminProjectName string = adminProject.name
output adminProjectEndpoint string = 'https://${sharedHub.name}.services.ai.azure.com/api/projects/${adminProject.name}'
