// Track A of lab 08-05c: the news MCP wrapper on Azure Container Apps.
//
// Deployed twice by 08-05c-02. The first pass (deployApp=false) creates the registry, the pull
// identity, the log workspace and the environment; the image is then built into the registry;
// the second pass (deployApp=true) adds the container app that runs it.

@description('Region for every resource')
param location string = resourceGroup().location

@description('The lab suffix: first 6 hex chars of SHA-256 of the subscription id + "v2"')
param suffix string

@description('Entra tenant whose tokens the wrapper accepts')
param tenantId string

@description('Accepted token audiences: the client id of news-mcp-{suffix} and its App ID URI')
param audiences array

@secure()
@description('GNews API key, held as a Container Apps secret')
param gnewsApiKey string

@description('Image to run, e.g. acrnewsmcpabc123.azurecr.io/news-mcp-wrapper:latest')
param image string = ''

@description('false: registry, identity, workspace and environment only. true: also the container app.')
param deployApp bool = false

@description('Log Analytics retention in days')
param logRetentionDays int = 30

resource workspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-news-mcp-${suffix}'
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: logRetentionDays
  }
}

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: 'acrnewsmcp${suffix}'
  location: location
  sku: { name: 'Basic' }
  properties: {
    adminUserEnabled: false
  }
}

// The container app pulls its image with this identity, so no registry password exists.
resource pullIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-news-mcp-${suffix}'
  location: location
}

resource acrPull 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  name: '7f951dda-4ed3-4680-a7ca-43fe172d538d' // AcrPull
}

resource identityCanPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: registry
  name: guid(registry.id, pullIdentity.id, acrPull.id)
  properties: {
    roleDefinitionId: acrPull.id
    principalId: pullIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource environment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: 'cae-news-mcp-${suffix}'
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: workspace.properties.customerId
        sharedKey: workspace.listKeys().primarySharedKey
      }
    }
    workloadProfiles: [
      { name: 'Consumption', workloadProfileType: 'Consumption' }
    ]
  }
}

resource app 'Microsoft.App/containerApps@2024-03-01' = if (deployApp) {
  name: 'ca-news-mcp-${suffix}'
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${pullIdentity.id}': {} }
  }
  dependsOn: [identityCanPull]
  properties: {
    environmentId: environment.id
    workloadProfileName: 'Consumption'
    configuration: {
      ingress: {
        external: true
        targetPort: 8080
        transport: 'http'
        allowInsecure: false
      }
      registries: [
        { server: registry.properties.loginServer, identity: pullIdentity.id }
      ]
      secrets: [
        { name: 'gnews-api-key', value: gnewsApiKey }
      ]
    }
    template: {
      containers: [
        {
          name: 'news-mcp-wrapper'
          image: image
          resources: { cpu: json('0.5'), memory: '1Gi' }
          env: [
            { name: 'ENTRA_TENANT_ID', value: tenantId }
            { name: 'NEWS_MCP_AUDIENCES', value: join(audiences, ',') }
            { name: 'GNEWS_API_KEY', secretRef: 'gnews-api-key' }
            { name: 'GNEWS_MCP_URL', value: 'https://mcp.gnews.io/' }
            { name: 'PORT', value: '8080' }
          ]
          probes: [
            { type: 'Liveness', httpGet: { path: '/health', port: 8080 }, periodSeconds: 30 }
            { type: 'Readiness', httpGet: { path: '/health', port: 8080 }, periodSeconds: 10 }
          ]
        }
      ]
      // One replica always on: a cold start takes 10 to 30 s, and Foundry gives an MCP call 100 s.
      scale: { minReplicas: 1, maxReplicas: 2 }
    }
  }
}

output registryName string = registry.name
output registryLoginServer string = registry.properties.loginServer
output appFqdn string = deployApp ? app!.properties.configuration.ingress.fqdn : ''
output wrapperMcpUrl string = deployApp ? 'https://${app!.properties.configuration.ingress.fqdn}/mcp' : ''
