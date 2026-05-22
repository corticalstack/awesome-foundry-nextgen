// ============================================================================
// Foundry IQ spoke
// Deployed into the existing rg-foundry-multi-{suffix} resource group.
// Adds an Azure AI Search service and iq-project to the existing shared
// AI Foundry account (aif-spoke-multi-{suffix}). No new Foundry account
// is created - the 1:N multi-project pattern absorbs this workload.
// All inference routes through the APIM gateway (no local model deployments).
// ============================================================================
targetScope = 'resourceGroup'

param location string = resourceGroup().location

@description('Region for the Azure AI Search service. Defaults to the RG location, but can be overridden if the RG region is out of Search capacity (InsufficientResourcesAvailable).')
param searchLocation string = location

param deployerPrincipalId string
param apimUrl string
param gatewayModelName string = 'gpt-4.1-mini'
@secure()
param apimSubscriptionKey string

@description('Name of the existing shared AI Foundry account (aif-spoke-multi-{suffix}).')
param existingAccountName string

// Suffix is derived from the resource group - keeps search service name consistent
// with other resources in this RG (e.g. aif-spoke-multi-gvwiex -> suffix gvwiex).
var suffix = substring(uniqueString(subscription().subscriptionId, resourceGroup().id), 0, 6)
var searchName = 'iq-search-${suffix}'
var projectName = 'iq-project'

// ─────────────────────────────────────────────────────────────────────────────
// Reference existing shared AI Foundry account
// ─────────────────────────────────────────────────────────────────────────────
resource aiAccount 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = {
  name: existingAccountName
}

// ─────────────────────────────────────────────────────────────────────────────
// Azure AI Search (the only new Azure resource in this lab)
// ─────────────────────────────────────────────────────────────────────────────
resource search 'Microsoft.Search/searchServices@2024-06-01-preview' = {
  name: searchName
  location: searchLocation
  sku: { name: 'basic' }
  identity: { type: 'SystemAssigned' }
  properties: {
    hostingMode: 'default'
    publicNetworkAccess: 'enabled'
    authOptions: {
      aadOrApiKey: { aadAuthFailureMode: 'http401WithBearerChallenge' }
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// iq-project - child of the existing shared account
// ─────────────────────────────────────────────────────────────────────────────
resource project 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' = {
  parent: aiAccount
  name: projectName
  location: location
  identity: { type: 'SystemAssigned' }
  properties: {
    description: 'Foundry IQ Lab - knowledge retrieval via APIM gateway'
    displayName: 'Foundry IQ Project'
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// APIM connection on iq-project
// ─────────────────────────────────────────────────────────────────────────────
resource apimConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview' = {
  parent: project
  name: 'iq-apim-connection'
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
      models: '[{"name":"${gatewayModelName}","properties":{"model":{"name":"${gatewayModelName}","version":"","format":"OpenAI"}}}]'
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// RBAC: Deployer permissions
// ─────────────────────────────────────────────────────────────────────────────

// NOTE: Cognitive Services User on the shared AI Account is intentionally omitted.
// The deployer already holds this role from earlier deployments (the multi-project deployment).
// ARM rejects duplicate role assignments (same principal + role + scope) even with
// a different GUID, so adding it here causes DeploymentFailed: RoleAssignmentExists.

// Search Index Data Contributor on AI Search
resource deployerSearchContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(search.id, deployerPrincipalId, 'SearchIndexDataContributor')
  scope: search
  properties: {
    principalId: deployerPrincipalId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '8ebe5a00-799e-43f5-93ac-243d3dce84a7')
  }
}

// Search Service Contributor on AI Search
resource deployerSearchServiceContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(search.id, deployerPrincipalId, 'SearchServiceContributor')
  scope: search
  properties: {
    principalId: deployerPrincipalId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7ca78c08-252a-4471-8644-bb5ff32d4ba0')
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// RBAC: Project managed identity permissions
// ─────────────────────────────────────────────────────────────────────────────

// Foundry User on the shared AI Account (required for agents)
resource projectAzureAIUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(aiAccount.id, project.id, 'IQ-AzureAIUser')
  scope: aiAccount
  properties: {
    principalId: project.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '53ca6127-db72-4b80-b1b0-d745d6d5456d')
  }
}

// Search Index Data Reader on AI Search (required for KB queries via MCP)
resource projectSearchReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(search.id, project.id, 'SearchIndexDataReader')
  scope: search
  properties: {
    principalId: project.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '1407120a-92aa-4202-b7e9-c0e197c71c8f')
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// RBAC: Search service managed identity → AI Account
// Required when the integrated vectorizer authenticates to the AI Account via
// managed identity rather than an API key (e.g. during index query-time embedding).
// ─────────────────────────────────────────────────────────────────────────────
resource searchCognitiveServicesUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(aiAccount.id, search.id, 'IQ-SearchCognitiveServicesUser')
  scope: aiAccount
  properties: {
    principalId: search.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908')
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Outputs
// ─────────────────────────────────────────────────────────────────────────────
output accountName string = aiAccount.name
output projectName string = project.name
output projectEndpoint string = 'https://${existingAccountName}.services.ai.azure.com/api/projects/${projectName}'
output projectManagedIdentityId string = project.identity.principalId
output apimConnectionName string = apimConnection.name
output gatewayModelName string = gatewayModelName
output searchEndpoint string = 'https://${search.name}.search.windows.net'
output searchName string = search.name
