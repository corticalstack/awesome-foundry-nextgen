// ============================================================================
// Lab 07-05: Agent Observability — subscription-scoped entry point.
//
// Deploys observability infrastructure in two places:
//   - spoke RG (rg-foundry-multi-{suffix}): Log Analytics, App Insights,
//     obs-project, AppInsights connection on the spoke account,
//     APIM connection, RBAC.
//   - admin RG (rg-foundry-core-{suffix}): AppInsights connection on the
//     core account pointing at the same App Insights resource, plus the
//     Azure AI User role assignment on the admin project's managed
//     identity (required by the Portal Monitor tab and continuous-eval).
//
// The split exists because Foundry account-level connections must be
// declared in the RG that hosts the account, so we need a second module
// scoped to the admin RG.
// ============================================================================
targetScope = 'subscription'

@description('Azure region for new resources in the spoke RG (App Insights, Log Analytics)')
param location string

@description('Spoke resource group (rg-foundry-multi-{suffix})')
param spokeResourceGroup string

@description('Admin/core resource group (rg-foundry-core-{suffix})')
param adminResourceGroup string

@description('Principal ID of the deployer for RBAC assignments')
param deployerPrincipalId string

@description('Existing shared spoke AI Foundry account (aif-spoke-multi-{suffix})')
param multiAccountName string

@description('Existing core AI Foundry account (aif-core-{suffix})')
param coreAccountName string

@description('Admin project on the core account (project-admin-{suffix})')
param adminProjectName string

@description('APIM service name (e.g. apim-foundry-{suffix})')
param apimName string

@secure()
@description('APIM subscription key for foundry-gateway-obs')
param apimSubscriptionKey string

// ─────────────────────────────────────────────────────────────────────────────
// Spoke module — App Insights, Log Analytics, obs-project, spoke connection
// ─────────────────────────────────────────────────────────────────────────────
module spoke 'modules/spoke.bicep' = {
  name: 'obs-spoke-deploy'
  scope: resourceGroup(spokeResourceGroup)
  params: {
    location: location
    deployerPrincipalId: deployerPrincipalId
    multiAccountName: multiAccountName
    apimName: apimName
    apimSubscriptionKey: apimSubscriptionKey
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Admin module — core-account AppInsights connection + admin-project IAM
// ─────────────────────────────────────────────────────────────────────────────
module admin 'modules/admin.bicep' = {
  name: 'obs-admin-deploy'
  scope: resourceGroup(adminResourceGroup)
  params: {
    coreAccountName: coreAccountName
    adminProjectName: adminProjectName
    appInsightsResourceId: spoke.outputs.appInsightsId
    appInsightsConnectionString: spoke.outputs.appInsightsConnectionString
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Outputs — re-expose what the notebook needs to write to .env
// ─────────────────────────────────────────────────────────────────────────────
output projectName string = spoke.outputs.projectName
output projectEndpoint string = spoke.outputs.projectEndpoint
output apimConnectionName string = spoke.outputs.apimConnectionName
output appInsightsName string = spoke.outputs.appInsightsName
output appInsightsConnectionString string = spoke.outputs.appInsightsConnectionString
output logAnalyticsName string = spoke.outputs.logAnalyticsName
output adminAppInsightsConnectionName string = admin.outputs.appInsightsConnectionName
