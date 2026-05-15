// ============================================================================
// Lab 15: Fine-Tuning (Knowledge Distillation) Infrastructure
// Deployed into the existing rg-foundry-multi-{suffix} resource group.
// Adds a Storage Account, ACA Environment (swedencentral for GPU availability),
// and a finetune-project to the existing shared AI Foundry account
// (aif-spoke-multi-{suffix}). No new Foundry account is created.
// All inference routes through the APIM gateway (no local model deployments).
// ============================================================================
targetScope = 'resourceGroup'

param location string = resourceGroup().location
param deployerPrincipalId string
param apimUrl string
param gatewayModelName string = 'gpt-4.1-mini'
@secure()
param apimSubscriptionKey string

@description('Name of the existing shared AI Foundry account (aif-spoke-multi-{suffix}).')
param existingAccountName string

// Suffix is derived from the resource group — keeps resource names consistent
// with other resources in this RG (e.g. aif-spoke-multi-gvwiex -> suffix gvwiex).
var suffix = substring(uniqueString(subscription().subscriptionId, resourceGroup().id), 0, 6)
var storageAccountName = 'issft${suffix}'
var acaEnvironmentName = 'acae-finetune-${suffix}'
var projectName = 'finetune-project'

// ─────────────────────────────────────────────────────────────────────────────
// Reference existing shared AI Foundry account
// ─────────────────────────────────────────────────────────────────────────────
resource aiAccount 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = {
  name: existingAccountName
}

// ─────────────────────────────────────────────────────────────────────────────
// Storage Account for training data, adapter weights, evaluation results
// ─────────────────────────────────────────────────────────────────────────────
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
  }
}

// Blob service (required to create containers)
resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' = {
  parent: storageAccount
  name: 'default'
}

// 'ft' container for training data, fine-tuned adapter and evaluation results
resource ftContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: blobService
  name: 'ft'
  properties: {
    publicAccess: 'None'
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// ACA Environment in swedencentral (required for GPU NC24-A100 availability)
// Note: ACA GPU workload profiles are only available in select regions.
// The ACA environment is always deployed to swedencentral regardless of the
// resource group's default location.
// ─────────────────────────────────────────────────────────────────────────────
resource acaEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: acaEnvironmentName
  location: 'swedencentral'
  properties: {
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
      {
        name: 'gpu-a100'
        workloadProfileType: 'Consumption-GPU-NC24-A100'
      }
    ]
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// finetune-project — child of the existing shared account
// ─────────────────────────────────────────────────────────────────────────────
resource project 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' = {
  parent: aiAccount
  name: projectName
  location: location
  identity: { type: 'SystemAssigned' }
  properties: {
    description: 'Fine-Tuning Lab 15 — knowledge distillation via ACA GPU + APIM gateway'
    displayName: 'Fine-Tune Project'
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// APIM connection on finetune-project
// ─────────────────────────────────────────────────────────────────────────────
resource apimConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview' = {
  parent: project
  name: 'finetune-apim-connection'
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

// Storage Blob Data Contributor — deployer can upload/download training data
resource deployerStorageContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, deployerPrincipalId, 'StorageBlobDataContributor')
  scope: storageAccount
  properties: {
    principalId: deployerPrincipalId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// RBAC: Project managed identity permissions
// ─────────────────────────────────────────────────────────────────────────────

// Azure AI User on the shared AI Account (required for inference via APIM connection)
resource projectAzureAIUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(aiAccount.id, project.id, 'FT-AzureAIUser')
  scope: aiAccount
  properties: {
    principalId: project.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '53ca6127-db72-4b80-b1b0-d745d6d5456d')
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Outputs
// ─────────────────────────────────────────────────────────────────────────────
output storageAccountName string = storageAccount.name
output acaEnvironmentName string = acaEnvironment.name
output projectEndpoint string = 'https://${existingAccountName}.services.ai.azure.com/api/projects/${projectName}'
output apimSubscriptionName string = apimConnection.name
