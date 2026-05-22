targetScope = 'resourceGroup'

param location string = resourceGroup().location
param deployerPrincipalId string
param apimUrl string
param modelName string = 'gpt-4.1-mini'
@secure()
param apimSubscriptionKey string

@description('Number of team projects to create under the shared account.')
@minValue(1)
@maxValue(10)
param projectCount int = 3

@description('Team names for each project. Must have exactly projectCount entries.')
param teamNames array = ['alpha', 'beta', 'gamma']

@description('Suffix for resource names - passed from notebook to keep naming consistent across labs.')
param suffix string

var aiAccountName = 'aif-spoke-multi-${suffix}'

// =============================================================================
// SHARED AI FOUNDRY ACCOUNT (1)
// =============================================================================

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

// =============================================================================
// N PROJECTS (one per team)
// =============================================================================

resource projects 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' = [
  for i in range(0, projectCount): {
    parent: aiAccount
    name: 'project-${teamNames[i]}-${suffix}'
    location: location
    identity: { type: 'SystemAssigned' }
    properties: {
      description: 'Project for team ${teamNames[i]} connecting to core gateway via APIM'
      displayName: 'Team ${toUpper(first(teamNames[i]))}${substring(teamNames[i], 1, length(teamNames[i]) - 1)} Project'
    }
  }
]

// =============================================================================
// APIM CONNECTION PER PROJECT
// =============================================================================

resource apimConnections 'Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview' = [
  for i in range(0, projectCount): {
    parent: projects[i]
    name: 'core-${teamNames[i]}'
    properties: {
      category: 'ApiManagement'
      target: apimUrl
      authType: 'ApiKey'
      credentials: {
        key: apimSubscriptionKey
      }
      metadata: {
        deploymentInPath: 'true'
        inferenceAPIVersion: '2024-10-21'
        models: '[{"name":"${modelName}","properties":{"model":{"name":"${modelName}","version":"","format":"OpenAI"}}}]'
      }
    }
  }
]

// =============================================================================
// ROLE ASSIGNMENTS
// =============================================================================

// Grant deployer access to the shared account
resource deployerCognitiveServicesUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(aiAccount.id, deployerPrincipalId, 'CognitiveServicesUser')
  scope: aiAccount
  properties: {
    principalId: deployerPrincipalId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908') // Cognitive Services User
  }
}

// =============================================================================
// OUTPUTS
// =============================================================================

output accountName string = aiAccount.name
output accountEndpoint string = aiAccount.properties.endpoint
output projectNames array = [for i in range(0, projectCount): projects[i].name]
output projectEndpoints array = [
  for i in range(0, projectCount): 'https://${aiAccountName}.services.ai.azure.com/api/projects/${projects[i].name}'
]
output teamNames array = [for i in range(0, projectCount): teamNames[i]]
output apimConnectionNames array = [for i in range(0, projectCount): 'core-${teamNames[i]}']
