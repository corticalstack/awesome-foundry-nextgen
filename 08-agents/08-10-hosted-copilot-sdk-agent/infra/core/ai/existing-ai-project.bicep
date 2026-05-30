targetScope = 'resourceGroup'

@description('Name of the existing AI Services account')
param aiServicesAccountName string

@description('Name of the existing AI Foundry project')
param aiFoundryProjectName string

@description('Existing ACR connection name (already set in the environment)')
param existingAcrConnectionName string = ''

@description('Existing container registry endpoint (already set in the environment)')
param existingContainerRegistryEndpoint string = ''

@description('Existing Application Insights connection string (already set in the environment)')
param existingApplicationInsightsConnectionString string = ''

@description('Existing Application Insights resource ID (already set in the environment)')
param existingApplicationInsightsResourceId string = ''

// Reference the existing account and project — read-only, no modifications
resource aiAccount 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: aiServicesAccountName

  resource project 'projects' existing = {
    name: aiFoundryProjectName
  }
}

// Outputs — same shape as ai-project.bicep so main.bicep can use either interchangeably
output AZURE_AI_PROJECT_ENDPOINT string = aiAccount::project.properties.endpoints['AI Foundry API']
output AZURE_OPENAI_ENDPOINT string = aiAccount.properties.endpoints['OpenAI Language Model Instance API']
output aiServicesEndpoint string = aiAccount.properties.endpoint
output accountId string = aiAccount.id
output projectId string = aiAccount::project.id
output aiServicesAccountName string = aiAccount.name
output aiServicesProjectName string = aiAccount::project.name
output aiServicesPrincipalId string = aiAccount.identity.principalId
output projectName string = aiAccount::project.name
output APPLICATIONINSIGHTS_CONNECTION_STRING string = existingApplicationInsightsConnectionString
output APPLICATIONINSIGHTS_RESOURCE_ID string = existingApplicationInsightsResourceId

// Empty connection outputs — these are already set in the azd environment from init
output connectionIds array = []

output dependentResources object = {
  registry: {
    name: ''
    loginServer: existingContainerRegistryEndpoint
    connectionName: existingAcrConnectionName
  }
  bing_grounding: {
    name: ''
    connectionName: ''
    connectionId: ''
  }
  bing_custom_grounding: {
    name: ''
    connectionName: ''
    connectionId: ''
  }
  search: {
    serviceName: ''
    connectionName: ''
  }
  storage: {
    accountName: ''
    connectionName: ''
  }
}
