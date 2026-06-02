// ============================================================================
// 08-10b - Hosted GitHub Copilot SDK agent on the shared 1:N multi account
//
// Deployed into the existing rg-foundry-multi-{suffix} resource group. Adds
// copilot-sdk-project to the existing shared AI Foundry account
// (aif-spoke-multi-{suffix}) plus an ACR for the agent image.
//
// Inference comes from the APIM core gateway, but - unlike the team prompt
// agents on this account - the hosted Copilot SDK container points DIRECTLY at
// the gateway (provider base_url = the APIM /openai endpoint, auth = the gateway
// subscription key in the `api-key` header), NOT through a Foundry project
// connection. Reason: Foundry's connection model-gateway ("bring your own model"
// via an ApiManagement connection) is supported only for *prompt* agents; a
// hosted agent calling the Responses API through a `connection/deployment` model
// string fails to resolve. So this bicep creates NO ApiManagement connection -
// the gateway URL + key are injected into the container as env vars at
// registration time (see the notebook's Step 6). The gateway-served model must
// be a *reasoning* model (e.g. gpt-5-mini) because the Copilot CLI's responses
// protocol carries encrypted reasoning content.
//
// NO local model deployment is created here, so the rg-foundry-multi
// `deny-model-deployments` policy is satisfied - the reasoning model lives on
// the core gateway account (aif-core), deployed by the notebook's Step 2.
//
// Model: 08-03 main.bicep (project + ACR for a hosted agent on an existing
// account), minus the local model deployment.
// ============================================================================
targetScope = 'resourceGroup'

@description('Location - must match the shared multi account region (East US 2 is supported for hosted agents).')
param location string = resourceGroup().location

@description('Principal ID of the deployer for RBAC assignments.')
param deployerPrincipalId string

@description('Name of the existing shared AI Foundry account (aif-spoke-multi-{suffix}), created by 05-04.')
param multiAccountName string

@description('Suffix for resource names - the repo-wide first 6 chars of sha256(subscriptionId + "v2").')
param suffix string

@description('Name of the capability project added to the shared account. A descriptive qualifier, not a Greek team name.')
param projectName string = 'copilot-sdk-project'

// ACR: lowercase alphanumeric only, globally unique. Stores the hosted agent image.
var acrName = 'acrcopilot${suffix}'

// Reference the existing shared AI Foundry account (created by 05-04). Read-only.
resource aiAccount 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = {
  name: multiAccountName
}

// copilot-sdk-project - child of the existing shared account. Hosts the agent;
// no connection is attached (the container reaches the gateway directly).
resource project 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' = {
  parent: aiAccount
  name: projectName
  location: location
  identity: { type: 'SystemAssigned' }
  properties: {
    description: 'Hosted GitHub Copilot SDK agent - inference via the APIM core gateway, direct (08-10b)'
    displayName: 'Copilot SDK Agent Project'
  }
}

// Azure Container Registry - stores the hosted agent container image
resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: acrName
  location: location
  sku: { name: 'Basic' }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Enabled'
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// RBAC
// The hosted agent authenticates to the APIM gateway with the subscription key
// (not its managed identity), so NO Cognitive Services OpenAI User grant is
// needed for inference. The per-agent runtime identity (AgentIdentity) does not
// exist until the agent is registered, so its grants (AcrPull + Foundry User on
// the project) are made in the notebook after create_version - see Step 7.
// ─────────────────────────────────────────────────────────────────────────────

// 1. project MI - Foundry User (Azure AI User) on the shared account
resource projectFoundryUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(aiAccount.id, project.id, 'CopilotSdk-FoundryUser')
  scope: aiAccount
  properties: {
    principalId: project.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '53ca6127-db72-4b80-b1b0-d745d6d5456d') // Foundry User (Azure AI User)
  }
}

// 2. project MI - AcrPull on the ACR (Foundry pulls the image as the project identity)
resource projectAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, project.id, 'CopilotSdk-AcrPull')
  scope: acr
  properties: {
    principalId: project.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d') // AcrPull
  }
}

// 3. deployer - AcrPush on the ACR (queue `az acr build`)
resource deployerAcrPush 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, deployerPrincipalId, 'CopilotSdk-AcrPush')
  scope: acr
  properties: {
    principalId: deployerPrincipalId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '8311e382-0749-4cb8-b61a-304f252e45ec') // AcrPush
  }
}

// 4. deployer - Foundry User on the new project (so the notebook can invoke the agent endpoint)
resource deployerFoundryUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(project.id, deployerPrincipalId, 'CopilotSdk-DeployerFoundryUser')
  scope: project
  properties: {
    principalId: deployerPrincipalId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '53ca6127-db72-4b80-b1b0-d745d6d5456d') // Foundry User (Azure AI User)
  }
}

output projectName string = project.name
output projectEndpoint string = 'https://${multiAccountName}.services.ai.azure.com/api/projects/${projectName}'
output acrName string = acr.name
output acrLoginServer string = acr.properties.loginServer
