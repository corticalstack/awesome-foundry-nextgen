targetScope = 'resourceGroup'

param location string = resourceGroup().location
param deployerPrincipalId string
param apimUrl string
param chatModelName string = 'gpt-4.1-mini'
@secure()
param apimSubscriptionKey string
@description('Short unique suffix for resource names — computed from subscription ID in the notebook.')
param suffix string
@description('Team identifier — used to namespace resources and env vars for multi-spoke deployments.')
param teamName string

// aif = Foundry account, proj = Foundry account project (CAF abbreviations)
var spokeAccountName = 'aif-spoke-${teamName}-${suffix}'
var projectName = 'project-${teamName}-${suffix}'

// Spoke Foundry account — no model deployments, uses APIM gateway for all inference
resource spokeAccount 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' = {
  name: spokeAccountName
  location: location
  kind: 'AIServices'
  sku: { name: 'S0' }
  identity: { type: 'SystemAssigned' }
  properties: {
    allowProjectManagement: true
    customSubDomainName: spokeAccountName
    publicNetworkAccess: 'Enabled'
  }
}

// Project workspace for the team
resource project 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' = {
  parent: spokeAccount
  name: projectName
  location: location
  identity: { type: 'SystemAssigned' }
  properties: {
    description: 'Project team spoke connecting to Core Gateway'
    displayName: 'Team Spoke Project'
  }
}

// APIM gateway connection with API Key auth and static model list
resource apimConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview' = {
  parent: project
  name: 'core-alpha'
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
      models: '[{"name":"${chatModelName}","properties":{"model":{"name":"${chatModelName}","version":"","format":"OpenAI"}}}]'
    }
  }
}

// Grant deployer Cognitive Services User access to the spoke account
resource deployerCognitiveServicesUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(spokeAccount.id, deployerPrincipalId, 'CognitiveServicesUser')
  scope: spokeAccount
  properties: {
    principalId: deployerPrincipalId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908')
  }
}

output accountName string = spokeAccount.name
output accountEndpoint string = spokeAccount.properties.endpoint
output projectName string = project.name
output projectEndpoint string = 'https://${spokeAccountName}.services.ai.azure.com/api/projects/${projectName}'
output apimConnectionName string = apimConnection.name
