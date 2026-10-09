// ============================================================================
// Deep research backend
// Deployed into the core resource group (same RG as the core gateway deployment).
// Idempotent - safe to run if the core gateway deployment has already deployed these resources.
//
// Creates (if not already present):
//   - aif-research-{suffix}  Norway East CognitiveServices account
//   - deep-research model deployment (gpt-5.6-sol)
//   - openai-research APIM backend
//   - chat-research APIM operation + routing policy
//   - responses operation policy (routes model "deep-research" to the research hub)
//   - dr-subscription APIM subscription (deep research workload key)
//   - RBAC: APIM MI → research hub (Cognitive Services User)
//   - RBAC: deployer → research hub (Cognitive Services User)
// ============================================================================
targetScope = 'resourceGroup'

param deployerPrincipalId string

@description('Name of the existing APIM service in this resource group.')
param existingApimName string

@description('Core gateway suffix (the tail of the APIM name) so this template targets the same research hub.')
param suffix string

var researchHubName = 'aif-research-${suffix}'

// ─────────────────────────────────────────────────────────────────────────────
// Reference existing APIM
// ─────────────────────────────────────────────────────────────────────────────
resource apim 'Microsoft.ApiManagement/service@2024-06-01-preview' existing = {
  name: existingApimName
}

resource api 'Microsoft.ApiManagement/service/apis@2024-06-01-preview' existing = {
  parent: apim
  name: 'openai'
}

resource responsesOp 'Microsoft.ApiManagement/service/apis/operations@2024-06-01-preview' existing = {
  parent: api
  name: 'responses'
}

// ─────────────────────────────────────────────────────────────────────────────
// Norway East research hub. It was placed there because o3-deep-research was only offered in
// norwayeast; gpt-5.6-sol is offered there too, so the hub stays where it is.
// ─────────────────────────────────────────────────────────────────────────────
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

// The deployment is named for its role, not its model, so APIM routing and DR_MODEL survive
// the next model swap. gpt-5.6-sol replaced o3-deep-research, which retires 2026-11-19.
resource researchModel 'Microsoft.CognitiveServices/accounts/deployments@2025-04-01-preview' = {
  parent: researchHub
  name: 'deep-research'
  // Capacity is K-TPM. 10 was too low - multi-step deep-research runs hit
  // 429 throttling before completing. 200 gives realistic headroom while
  // staying under the default gpt-5.6-sol GlobalStandard quota of 1000.
  sku: { name: 'GlobalStandard', capacity: 200 }
  properties: {
    model: {
      name: 'gpt-5.6-sol'
      format: 'OpenAI'
      version: '2026-07-09'
    }
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
    raiPolicyName: 'Microsoft.DefaultV2'
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// APIM backend - points to research hub
// ─────────────────────────────────────────────────────────────────────────────
resource researchBackend 'Microsoft.ApiManagement/service/backends@2024-06-01-preview' = {
  parent: apim
  name: 'openai-research'
  properties: {
    url: '${researchHub.properties.endpoint}openai'
    protocol: 'http'
    description: 'Research hub - reasoning and research models (Norway East)'
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// APIM operation - specific URL match for deep-research
// Routes before the catch-all chat operation
// ─────────────────────────────────────────────────────────────────────────────
resource chatResearchOp 'Microsoft.ApiManagement/service/apis/operations@2024-06-01-preview' = {
  parent: api
  name: 'chat-research'
  properties: {
    displayName: 'Chat Completions (Research)'
    method: 'POST'
    urlTemplate: '/deployments/deep-research/chat/completions'
  }
}

resource chatResearchPolicy 'Microsoft.ApiManagement/service/apis/operations/policies@2024-06-01-preview' = {
  parent: chatResearchOp
  name: 'policy'
  properties: {
    format: 'xml'
    value: '<policies><inbound><base /><set-backend-service backend-id="openai-research" /><authentication-managed-identity resource="https://cognitiveservices.azure.com" output-token-variable-name="msi-access-token" ignore-error="false" /><set-header name="Authorization" exists-action="override"><value>@("Bearer " + (string)context.Variables["msi-access-token"])</value></set-header></inbound><backend><base /></backend><outbound><base /></outbound></policies>'
  }
  dependsOn: [researchBackend]
}

// ─────────────────────────────────────────────────────────────────────────────
// Responses operation policy - Responses carries the model in the body, so a URL
// match cannot route it. Requests for deep-research go to the research hub; the
// API policy (<base />) has already set the managed identity token.
// rawxml because the expression contains As<JObject>, which is not valid XML.
// ─────────────────────────────────────────────────────────────────────────────
resource responsesPolicy 'Microsoft.ApiManagement/service/apis/operations/policies@2024-06-01-preview' = {
  parent: responsesOp
  name: 'policy'
  properties: {
    format: 'rawxml'
    value: '<policies><inbound><base /><choose><when condition="@((string)context.Request.Body.As<JObject>(preserveContent: true)["model"] == "deep-research")"><set-backend-service backend-id="openai-research" /></when></choose></inbound><backend><base /></backend><outbound><base /></outbound></policies>'
  }
  dependsOn: [researchBackend]
}

// ─────────────────────────────────────────────────────────────────────────────
// APIM subscription - dedicated key for deep research workload
// ─────────────────────────────────────────────────────────────────────────────
resource drSubscription 'Microsoft.ApiManagement/service/subscriptions@2024-06-01-preview' = {
  parent: apim
  name: 'foundry-gateway-dr'
  properties: {
    displayName: 'Foundry Gateway Access (Deep Research)'
    scope: '/apis/${api.name}'
    state: 'active'
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// RBAC: APIM managed identity → research hub
// ─────────────────────────────────────────────────────────────────────────────
resource apimResearchUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(researchHub.id, apim.id, 'CognitiveServicesUser')
  scope: researchHub
  properties: {
    principalId: apim.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908') // Cognitive Services User
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// RBAC: Deployer → research hub
// ─────────────────────────────────────────────────────────────────────────────
resource deployerResearchUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(researchHub.id, deployerPrincipalId, 'CognitiveServicesUser')
  scope: researchHub
  properties: {
    principalId: deployerPrincipalId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908') // Cognitive Services User
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Outputs
// ─────────────────────────────────────────────────────────────────────────────
output researchHubName string = researchHub.name
output researchHubEndpoint string = researchHub.properties.endpoint
output drModelName string = researchModel.name
output drSubscriptionName string = drSubscription.name
