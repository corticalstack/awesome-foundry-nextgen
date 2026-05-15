// ============================================================================
// Lab 07 admin-side observability
// Deployed into rg-foundry-core-{suffix}.
// Wires the existing App Insights (deployed by spoke.bicep into the spoke RG)
// onto the core account (aif-core-{suffix}) so the Foundry Portal Monitor tab
// for admin-project agents (e.g. aria-rm-briefing-agent) has an App Insights
// backing. Also grants the admin project's managed identity the Azure AI User
// role on itself — required by continuous-evaluation rules and several Monitor
// tab features.
// ============================================================================
targetScope = 'resourceGroup'

@description('Name of the existing core AI Foundry account (aif-core-{suffix})')
param coreAccountName string

@description('Name of the existing admin project on the core account (project-admin-{suffix})')
param adminProjectName string

@description('Resource ID of the App Insights instance (deployed by spoke.bicep, lives in the spoke RG)')
param appInsightsResourceId string

@secure()
@description('Connection string of the App Insights instance')
param appInsightsConnectionString string

// ─────────────────────────────────────────────────────────────────────────────
// Reference existing core account and admin project
// ─────────────────────────────────────────────────────────────────────────────
resource coreAccount 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = {
  name: coreAccountName
}

resource adminProject 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' existing = {
  parent: coreAccount
  name: adminProjectName
}

// ─────────────────────────────────────────────────────────────────────────────
// AppInsights connection on the core account — account-scoped, shared to all
// projects. Pointed at the same App Insights resource the spoke side uses, so
// client-side OTel and Portal Monitor-tab traces converge in one workspace.
// ─────────────────────────────────────────────────────────────────────────────
resource appInsightsConnection 'Microsoft.CognitiveServices/accounts/connections@2025-04-01-preview' = {
  name: 'appinsights-connection'
  parent: coreAccount
  properties: {
    category: 'AppInsights'
    target: appInsightsResourceId
    isSharedToAll: true
    authType: 'ApiKey'
    credentials: {
      key: appInsightsConnectionString
    }
    metadata: {
      ApiType: 'Azure'
      ResourceId: appInsightsResourceId
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// IAM: admin project MI — Azure AI User on the admin project itself.
// Required by the Portal Monitor tab and continuous-eval rules; without it
// you get "Setup incomplete: assign the Foundry project's managed identity
// the Azure AI User role for this project."
// ─────────────────────────────────────────────────────────────────────────────
resource adminProjectAzureAIUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(adminProject.id, 'Obs-AdminProjectAzureAIUser')
  scope: adminProject
  properties: {
    principalId: adminProject.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '53ca6127-db72-4b80-b1b0-d745d6d5456d')
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// IAM: admin project MI — Cognitive Services OpenAI User on the core account.
// Required so the continuous-eval pipeline (which runs the LLM-as-judge under
// the project's MI) can POST to chat/completions on the core account's model
// deployments. Without it, eval runs fail with:
//   "FAILED_EXECUTION: (UserError) OpenAI API hits AuthenticationError:
//    PermissionDenied — lacks data action
//    Microsoft.CognitiveServices/accounts/OpenAI/deployments/chat/completions/action"
// Azure AI User (above) covers control-plane operations only; the OpenAI
// data plane is a separate, narrower role.
// ─────────────────────────────────────────────────────────────────────────────
resource adminProjectOpenAIUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(coreAccount.id, adminProject.id, 'Obs-AdminProjectOpenAIUser')
  scope: coreAccount
  properties: {
    principalId: adminProject.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
  }
}

output appInsightsConnectionName string = appInsightsConnection.name
