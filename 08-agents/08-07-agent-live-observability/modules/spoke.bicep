// ============================================================================
// Lab 07 spoke-side observability
// Deployed into the existing rg-foundry-multi-{suffix} resource group.
// Adds obs-project to the existing shared AI Foundry account
// (aif-spoke-multi-{suffix}). No new Foundry account is created — the
// 1:N multi-project pattern absorbs this workload.
// All inference routes through the APIM gateway (no local model deployments).
// ============================================================================
targetScope = 'resourceGroup'

param location string = resourceGroup().location

@description('Principal ID of the deployer for RBAC assignments')
param deployerPrincipalId string

@description('Name of the existing shared AI Foundry account (aif-spoke-multi-{suffix})')
param multiAccountName string

@description('Name of the APIM service (e.g. apim-foundry-{suffix}) — used in APIM connection metadata')
param apimName string

@secure()
@description('APIM subscription key for foundry-gateway-obs')
param apimSubscriptionKey string

var suffix           = substring(uniqueString(subscription().subscriptionId, resourceGroup().id), 0, 6)
var projectName      = 'obs-project'
var logAnalyticsName = 'log-obs-${suffix}'
var appInsightsName  = 'appi-obs-${suffix}'

// ─────────────────────────────────────────────────────────────────────────────
// Log Analytics Workspace (required by Application Insights)
// ─────────────────────────────────────────────────────────────────────────────
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalyticsName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 90
    features: {
      enableLogAccessUsingOnlyResourcePermissions: true
    }
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Application Insights (trace storage and visualization)
// ─────────────────────────────────────────────────────────────────────────────
resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Reference existing shared AI Foundry account
// ─────────────────────────────────────────────────────────────────────────────
resource aiAccount 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = {
  name: multiAccountName
}

// ─────────────────────────────────────────────────────────────────────────────
// AppInsights connection — account-scoped so all projects can use it
// isSharedToAll: true makes it visible across all projects on this account
// ─────────────────────────────────────────────────────────────────────────────
resource appInsightsConnection 'Microsoft.CognitiveServices/accounts/connections@2025-04-01-preview' = {
  name: 'appinsights-connection'
  parent: aiAccount
  properties: {
    category: 'AppInsights'
    target: appInsights.id
    isSharedToAll: true
    authType: 'ApiKey'
    credentials: {
      key: appInsights.properties.ConnectionString
    }
    metadata: {
      ApiType: 'Azure'
      ResourceId: appInsights.id
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// obs-project — child of the existing shared account
// ─────────────────────────────────────────────────────────────────────────────
resource project 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' = {
  parent: aiAccount
  name: projectName
  location: location
  identity: { type: 'SystemAssigned' }
  properties: {
    description: 'Agent Observability Lab — OpenTelemetry tracing with Application Insights'
    displayName: 'Agent Observability Project'
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// APIM connection on obs-project
// ─────────────────────────────────────────────────────────────────────────────
resource apimConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview' = {
  parent: project
  name: 'landing-zone-apim'
  properties: {
    category: 'ApiManagement'
    target: 'https://${apimName}.azure-api.net/openai'
    authType: 'ApiKey'
    credentials: {
      key: apimSubscriptionKey
    }
    metadata: {
      deploymentInPath: 'true'
      inferenceAPIVersion: '2024-10-21'
      models: '[{"name":"gpt-4.1-mini","properties":{"model":{"name":"gpt-4.1-mini","version":"","format":"OpenAI"}}}]'
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// RBAC Assignments
// ─────────────────────────────────────────────────────────────────────────────
// Note: deployer role assignments on the shared account (Cognitive Services User,
// Azure AI User) are omitted — they are assigned as prerequisites by Lab 1C
// (04-05-deploy-foundry-multi-project) and must already exist before this deploys.

// 1. obs-project MI — Azure AI User on the shared account (required for agents)
resource projectAzureAIUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(aiAccount.id, project.id, 'Obs-ProjectAzureAIUser')
  scope: aiAccount
  properties: {
    principalId: project.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '53ca6127-db72-4b80-b1b0-d745d6d5456d')
  }
}

// 2. obs-project MI — Cognitive Services OpenAI User on the shared account
resource projectOpenAIUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(aiAccount.id, project.id, 'Obs-ProjectOpenAIUser')
  scope: aiAccount
  properties: {
    principalId: project.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
  }
}

// 3. Deployer — Log Analytics Reader on the LAW
resource deployerLogAnalyticsReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(logAnalytics.id, deployerPrincipalId, 'Obs-LogAnalyticsReader')
  scope: logAnalytics
  properties: {
    principalId: deployerPrincipalId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '73c42c96-874c-492b-b04d-ab87d138a893')
  }
}

// 4. Deployer — Application Insights Component Contributor on App Insights
resource deployerAppInsightsContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(appInsights.id, deployerPrincipalId, 'Obs-AppInsightsContributor')
  scope: appInsights
  properties: {
    principalId: deployerPrincipalId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ae349356-3a1b-4a5e-921d-050484c6347e')
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Outputs
// ─────────────────────────────────────────────────────────────────────────────
output projectName string = project.name
output projectEndpoint string = 'https://${multiAccountName}.services.ai.azure.com/api/projects/${projectName}'
output apimConnectionName string = apimConnection.name
output appInsightsName string = appInsights.name
output appInsightsId string = appInsights.id
output appInsightsConnectionString string = appInsights.properties.ConnectionString
output logAnalyticsName string = logAnalytics.name
