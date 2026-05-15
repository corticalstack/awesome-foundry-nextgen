targetScope = 'resourceGroup'

@description('Location for all resources')
param location string = resourceGroup().location

@description('Principal ID of the deployer (for RBAC)')
param deployerPrincipalId string

@description('Principal ID of the ALPHA project managed identity (for RBAC)')
param alphaProjectPrincipalId string

// Use subscription ID + RG ID for uniqueness across different users/subscriptions
var suffix = substring(uniqueString(subscription().subscriptionId, resourceGroup().id), 0, 6)
var storageAccountName = 'redteamstor${suffix}'

// Storage Account for evaluation results (required for red teaming)
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
}

// Blob service for evaluation result storage
resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' = {
  parent: storageAccount
  name: 'default'
}

// Container for red team results
resource redteamContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: blobService
  name: 'redteam-results'
  properties: {
    publicAccess: 'None'
  }
}

// Grant deployer Storage Blob Data Owner on storage account
resource deployerStorageBlobDataOwner 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, deployerPrincipalId, 'StorageBlobDataOwner')
  scope: storageAccount
  properties: {
    principalId: deployerPrincipalId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b')
  }
}

// Grant ALPHA project MI Storage Blob Data Owner for evaluation results
resource projectStorageBlobDataOwner 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, alphaProjectPrincipalId, 'StorageBlobDataOwner')
  scope: storageAccount
  properties: {
    principalId: alphaProjectPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b')
  }
}

// Outputs for use in notebooks
output storageAccountName string = storageAccount.name
output storageAccountId string = storageAccount.id
