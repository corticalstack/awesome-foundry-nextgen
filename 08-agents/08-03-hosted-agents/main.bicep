// Hosted agents infrastructure
// Deploys an Azure Container Registry (ACR) into the existing Spoke Alpha resource group
// (rg-foundry-spoke-alpha-{suffix}) and grants the existing spoke project identity AcrPull access.
//
// The capability host (Azure Container Apps) is provisioned via REST API in the notebook (Step 4).
// East US 2 is fully supported for Hosted Agents (confirmed March 2026).
//
// Prerequisites: core gateway + Team Alpha spoke must be deployed first.

targetScope = 'resourceGroup'

@description('Short unique suffix - first 6 chars of SHA-256 of subscription ID, matching the core gateway and project spoke naming.')
param suffix string

@description('Team name - must match the spoke deployed by the project spoke deployment (default: alpha).')
param teamName string = 'alpha'

@description('Location for ACR - matches the spoke resource group location.')
param location string = 'eastus2'

@description('Principal ID of the deployer for RBAC assignments.')
param deployerPrincipalId string

// Resource names - follow architecture naming conventions
var acrName     = 'acr${teamName}${suffix}'     // ACR: lowercase alphanumeric only, globally unique
var accountName = 'aif-spoke-${teamName}-${suffix}'
var projectName = 'project-${teamName}-${suffix}'

// Reference existing Spoke Alpha account and project (deployed by the project spoke deployment)
resource spokeAccount 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = {
  name: accountName
}

resource spokeProject 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' existing = {
  parent: spokeAccount
  name: projectName
}

// Azure Container Registry - stores hosted agent container images
resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: acrName
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Enabled'
  }
}

// RBAC: Foundry Project managed identity can pull agent images from ACR
resource acrPullRoleDefinition 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  name: '7f951dda-4ed3-4680-a7ca-43fe172d538d' // AcrPull
}

resource aiFoundryProjectCanPullFromAcr 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: acr
  name: guid(acr.id, spokeProject.id, acrPullRoleDefinition.id)
  properties: {
    roleDefinitionId: acrPullRoleDefinition.id
    principalId: spokeProject.identity.principalId
    principalType: 'ServicePrincipal'
    description: 'Allow AI Foundry Project to pull images from ACR'
  }
}

// RBAC: Deployer can push agent images to ACR
resource acrPushRoleDefinition 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  name: '8311e382-0749-4cb8-b61a-304f252e45ec' // AcrPush
}

resource currentUserCanPushToAcr 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: acr
  name: guid(acr.id, deployerPrincipalId, acrPushRoleDefinition.id)
  properties: {
    roleDefinitionId: acrPushRoleDefinition.id
    principalId: deployerPrincipalId
    principalType: 'User'
    description: 'Allow deployer to push images to ACR'
  }
}

// Outputs
output acrName        string = acr.name
output acrLoginServer string = acr.properties.loginServer
