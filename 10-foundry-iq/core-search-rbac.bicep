// ============================================================================
// Search service managed identity → core AI Foundry account
// Deployed as a module from main.bicep, scoped to rg-foundry-core-{suffix}.
// The knowledge base LLM (query planning) is called directly on the core account
// with the search service managed identity: knowledge base model configurations
// reject APIM and custom domain endpoints.
// ============================================================================
targetScope = 'resourceGroup'

@description('Name of the core AI Foundry account that hosts the chat model deployment (aif-core-{suffix}).')
param coreAccountName string

param searchServiceId string
param searchPrincipalId string

resource coreAccount 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = {
  name: coreAccountName
}

// Cognitive Services User on the core AI Account
resource searchCoreCognitiveServicesUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(coreAccount.id, searchServiceId, 'IQ-SearchCoreCognitiveServicesUser')
  scope: coreAccount
  properties: {
    principalId: searchPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908')
  }
}
