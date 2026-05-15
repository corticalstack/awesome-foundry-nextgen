// Lab 08-04: Memory API Infrastructure
// Deploys a dedicated Foundry account with local model deployments into rg-foundry-memory-{suffix}.
//
// The Memory API requires direct (non-APIM) model access for internal summarisation and
// embedding operations. This is why a dedicated account with local deployments is required —
// the deny-model-deployments Azure Policy applied to spoke resource groups blocks local
// deployments there, and the Memory API's memory_search tool does not support BYO gateway models.
//
// Prerequisites: Labs 1A and 1B must be deployed first (core gateway + Team Alpha spoke).

targetScope = 'resourceGroup'

param location string = resourceGroup().location

@description('Short unique suffix — first 6 chars of SHA-256 of subscription ID, matching Lab 1A/1B naming.')
param suffix string

@description('Team name — identifies which team this memory project belongs to.')
param teamName string = 'alpha'

@description('Principal ID of the deployer for RBAC assignments.')
param deployerPrincipalId string

@description('Local chat model for Memory API internal processing (summarisation, fact extraction).')
param localChatModel string = 'gpt-4.1-mini'

@description('Local embedding model for Memory API semantic search and indexing.')
param embeddingModelName string = 'text-embedding-3-small'

// Resource names — follow architecture naming conventions
var aiAccountName = 'aif-memory-${suffix}'
var projectName   = 'project-${teamName}-memory-${suffix}'

// Foundry account — hosts local model deployments required by the Memory API.
// Deployed into rg-foundry-memory-{suffix}, which is intentionally excluded from the
// deny-model-deployments policy that blocks deployments in spoke resource groups.
resource aiAccount 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' = {
  name: aiAccountName
  location: location
  kind: 'AIServices'
  sku: { name: 'S0' }
  identity: { type: 'SystemAssigned' }
  properties: {
    allowProjectManagement: true
    customSubDomainName: aiAccountName
    publicNetworkAccess: 'Enabled'
  }
}

// Local chat model — used by Memory API for summarisation and fact extraction.
// Must be a direct deployment on this account; APIM-routed models are not supported by the Memory API.
resource chatModel 'Microsoft.CognitiveServices/accounts/deployments@2025-04-01-preview' = {
  parent: aiAccount
  name: localChatModel
  sku: { name: 'GlobalStandard', capacity: 30 }
  properties: {
    model: { name: localChatModel, format: 'OpenAI', version: '2025-04-14' }
  }
}

// Local embedding model — used by Memory API for semantic indexing and search.
resource embeddingModel 'Microsoft.CognitiveServices/accounts/deployments@2025-04-01-preview' = {
  parent: aiAccount
  name: embeddingModelName
  sku: { name: 'Standard', capacity: 30 }
  properties: {
    model: { name: embeddingModelName, format: 'OpenAI', version: '1' }
  }
  dependsOn: [chatModel]
}

// Team project — workspace for memory store management and agent registration
resource project 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' = {
  parent: aiAccount
  name: projectName
  location: location
  identity: { type: 'SystemAssigned' }
  properties: {
    description: 'Memory API project for Team ${teamName}'
    displayName: projectName
  }
}

// RBAC: Deployer — Cognitive Services User on the account
resource deployerCognitiveServicesUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(aiAccount.id, deployerPrincipalId, 'CognitiveServicesUser')
  scope: aiAccount
  properties: {
    principalId: deployerPrincipalId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908')
  }
}

// RBAC: Project MI — Azure AI User (required for Memory API)
resource projectAzureAIUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(aiAccount.id, project.id, 'AzureAIUser')
  scope: aiAccount
  properties: {
    principalId: project.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '53ca6127-db72-4b80-b1b0-d745d6d5456d')
  }
}

// RBAC: Project MI — Cognitive Services OpenAI User (required for Memory API)
resource projectOpenAIUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(aiAccount.id, project.id, 'CognitiveServicesOpenAIUser')
  scope: aiAccount
  properties: {
    principalId: project.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
  }
}

output accountName             string = aiAccount.name
output accountEndpoint         string = aiAccount.properties.endpoint
output projectName             string = project.name
output projectEndpoint         string = 'https://${aiAccountName}.services.ai.azure.com/api/projects/${projectName}'
output localChatModel          string = chatModel.name
output embeddingModelName      string = embeddingModel.name
output projectManagedIdentityId string = project.identity.principalId
