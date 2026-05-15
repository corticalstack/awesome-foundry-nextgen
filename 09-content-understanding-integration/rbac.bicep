// ============================================================================
// Lab 10: CU RBAC — APIM managed identity → Cognitive Services User
// Deployed separately to rg-foundry-cu-{suffix} by 10-00-deploy-setup.ipynb
// after the APIM principal ID is known.
// ============================================================================
targetScope = 'resourceGroup'

param cuAccountName string
param apimPrincipalId string

resource cuAccount 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = {
  name: cuAccountName
}

// Grant APIM managed identity Cognitive Services User on the CU account
// Required for the authentication-managed-identity policy in the /cu APIM API
resource apimCognitiveServicesUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(cuAccount.id, apimPrincipalId, 'CognitiveServicesUser')
  scope: cuAccount
  properties: {
    principalId: apimPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908')
  }
}
