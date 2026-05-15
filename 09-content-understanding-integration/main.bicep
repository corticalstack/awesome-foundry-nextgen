// ============================================================================
// Lab 10: Content Understanding Spoke
// Deploys a dedicated AI Services account (aif-cu-{suffix}) with a cu-project
// Foundry project, an APIM connection, local model deployments for CU field
// extraction, and RBAC for the deployer and project managed identity.
//
// NOTE: rg-foundry-cu-{suffix} must NOT be assigned the deny-model-deployments
// policy — local model deployments are intentional for CU field extraction.
// ============================================================================
targetScope = 'resourceGroup'

param location string = resourceGroup().location
@secure()
param deployerPrincipalId string
param apimUrl string
@secure()
param apimSubscriptionKey string

var suffix = substring(uniqueString(subscription().subscriptionId, resourceGroup().id), 0, 6)
var accountName = 'aif-cu-${suffix}'
var projectName = 'cu-project'

// ─────────────────────────────────────────────────────────────────────────────
// AI Services account — dedicated CU account with local model deployments
// ─────────────────────────────────────────────────────────────────────────────
resource cuAccount 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' = {
  name: accountName
  location: location
  kind: 'AIServices'
  sku: { name: 'S0' }
  identity: { type: 'SystemAssigned' }
  properties: {
    customSubDomainName: accountName
    publicNetworkAccess: 'Enabled'
    allowProjectManagement: true
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Local model deployments (required for CU field extraction analyzers)
// Deploy sequentially — embedding depends on chat model completing first
// ─────────────────────────────────────────────────────────────────────────────
resource chatDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-04-01-preview' = {
  parent: cuAccount
  name: 'gpt-4.1-mini'
  sku: {
    name: 'GlobalStandard'
    capacity: 10
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-4.1-mini'
    }
  }
}

resource embeddingDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-04-01-preview' = {
  parent: cuAccount
  name: 'text-embedding-3-large'
  dependsOn: [chatDeployment]
  sku: {
    name: 'Standard'
    capacity: 50
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'text-embedding-3-large'
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Foundry project — cu-project
// ─────────────────────────────────────────────────────────────────────────────
resource cuProject 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' = {
  parent: cuAccount
  name: projectName
  location: location
  identity: { type: 'SystemAssigned' }
  properties: {
    description: 'Content Understanding Lab — governed CU access via APIM gateway'
    displayName: 'Content Understanding Project'
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// APIM connection on cu-project
// ─────────────────────────────────────────────────────────────────────────────
resource apimConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview' = {
  parent: cuProject
  name: 'landing-zone-apim'
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
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// RBAC: Deployer — Azure AI Developer on cuAccount
// ─────────────────────────────────────────────────────────────────────────────
resource deployerAzureAIDeveloper 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(cuAccount.id, deployerPrincipalId, 'CU-AzureAIDeveloper')
  scope: cuAccount
  properties: {
    principalId: deployerPrincipalId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '64702f94-c441-49e6-a78b-ef80e0188fee')
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// RBAC: cu-project managed identity — Azure AI Developer on cuAccount
// ─────────────────────────────────────────────────────────────────────────────
resource projectAzureAIDeveloper 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(cuAccount.id, cuProject.id, 'CU-ProjectAzureAIDeveloper')
  scope: cuAccount
  properties: {
    principalId: cuProject.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '64702f94-c441-49e6-a78b-ef80e0188fee')
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Outputs
// ─────────────────────────────────────────────────────────────────────────────
output accountName string = cuAccount.name
output accountEndpoint string = cuAccount.properties.endpoint
output projectName string = cuProject.name
output projectEndpoint string = 'https://${accountName}.services.ai.azure.com/api/projects/${projectName}'
output projectManagedIdentityId string = cuProject.identity.principalId
output apimConnectionName string = apimConnection.name
