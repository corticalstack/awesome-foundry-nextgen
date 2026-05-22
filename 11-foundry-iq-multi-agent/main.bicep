// ============================================================================
// Foundry IQ multi-agent spoke
// Deployed into the existing rg-foundry-multi-{suffix} resource group.
// Adds a Standard-SKU Azure AI Search service and contoso-project to the
// existing shared AI Foundry account (aif-spoke-multi-{suffix}). No new
// Foundry account is created - the 1:N multi-project pattern absorbs this
// workload. Standard SKU is required for semantic search (answerSynthesis mode).
// All inference routes through the APIM gateway (no local model deployments).
// NOTE: Deployer Cognitive Services User on the AI Account is intentionally
// omitted - already granted by an earlier deployment, duplicate would cause
// DeploymentFailed: RoleAssignmentExists.
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

// Suffix is derived from the resource group - keeps resource names consistent
// with other resources in this RG (e.g. aif-spoke-multi-gvwiex -> suffix gvwiex).
var suffix = substring(uniqueString(subscription().subscriptionId, resourceGroup().id), 0, 6)
var searchName = 'contoso-search-${suffix}'
var projectName = 'contoso-project'

// ─────────────────────────────────────────────────────────────────────────────
// Reference existing shared AI Foundry account
// ─────────────────────────────────────────────────────────────────────────────
resource aiAccount 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = {
  name: existingAccountName
}

// ─────────────────────────────────────────────────────────────────────────────
// Azure AI Search - Standard SKU for semantic search / answerSynthesis mode
// ─────────────────────────────────────────────────────────────────────────────
resource search 'Microsoft.Search/searchServices@2024-06-01-preview' = {
  name: searchName
  location: searchLocation
  sku: { name: 'standard' }
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
// contoso-project - child of the existing shared account
// ─────────────────────────────────────────────────────────────────────────────
resource project 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' = {
  parent: aiAccount
  name: projectName
  location: location
  identity: { type: 'SystemAssigned' }
  properties: {
    description: 'Foundry IQ Multi-Agent Lab - three specialist agents (HR, Marketing, Products)'
    displayName: 'Contoso Project'
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// APIM connection on contoso-project
// ─────────────────────────────────────────────────────────────────────────────
resource apimConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview' = {
  parent: project
  name: 'contoso-apim-connection'
  properties: {
    category: 'ApiManagement'
    target: apimUrl
    authType: 'ApiKey'
    // isDefault must be true - Foundry agent runtime resolves model_deployment_name
    // by searching local AI account deployments OR the default APIM connection on
    // the project. Without this, agents fail with "Failed to resolve model info for".
    isDefault: true
    isSharedToAll: true
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

// Search Index Data Contributor on AI Search (8ebe5a00...)
resource deployerSearchContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(search.id, deployerPrincipalId, 'ContosoSearchIndexDataContributor')
  scope: search
  properties: {
    principalId: deployerPrincipalId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '8ebe5a00-799e-43f5-93ac-243d3dce84a7')
  }
}

// Search Service Contributor on AI Search (7ca78c08...)
resource deployerSearchServiceContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(search.id, deployerPrincipalId, 'ContosoSearchServiceContributor')
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

// Foundry User on the shared AI Account (53ca6127...) - required for agents
resource projectAzureAIUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(aiAccount.id, project.id, 'Contoso-AzureAIUser')
  scope: aiAccount
  properties: {
    principalId: project.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '53ca6127-db72-4b80-b1b0-d745d6d5456d')
  }
}

// Search Index Data Reader on AI Search (1407120a...) - required for KB queries via MCP
resource projectSearchReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(search.id, project.id, 'ContosoSearchIndexDataReader')
  scope: search
  properties: {
    principalId: project.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '1407120a-92aa-4202-b7e9-c0e197c71c8f')
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// RBAC: Search service managed identity → AI Account
// Required for the integrated vectorizer to authenticate via managed identity
// when calling text-embedding-3-large via APIM at query time (a97b65f3...).
// ─────────────────────────────────────────────────────────────────────────────
resource searchCognitiveServicesUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(aiAccount.id, search.id, 'Contoso-SearchCognitiveServicesUser')
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
