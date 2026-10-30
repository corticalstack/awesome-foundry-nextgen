// Track B of lab 08-05c: the GNews MCP server behind apim-foundry-{suffix}, the gateway 05-02 deployed.
//
// Adds a backend for the GNews MCP endpoint, an MCP API that passes through to it, the API's inbound
// policy and the GNews key as a secret named value to the existing gateway; 05-02's template does not
// change. The policy (news-mcp-policy.xml) validates the Entra token Foundry sends on the user's behalf,
// denies a tools/call for a category the token's roles do not allow with the same text as the Track A
// wrapper, and swaps the token for the GNews key. A policy at MCP scope must not read the response body,
// so tools/list passes through unfiltered.
//
// api-version 2024-06-01-preview, as in 05-02 and the AI-Gateway samples: at 2025-09-01-preview the
// service rejected mcpProperties as the published spec describes them (endpoints as an array).

@description('The lab suffix: first 6 hex chars of SHA-256 of the subscription id + "v2"')
param suffix string

@description('Entra tenant whose tokens the gateway accepts')
param tenantId string

@description('Accepted token audiences: the client id of news-mcp-{suffix} and its App ID URI')
param audiences array

@secure()
@description('GNews API key, held as a secret named value')
param gnewsApiKey string

resource apim 'Microsoft.ApiManagement/service@2024-06-01-preview' existing = {
  name: 'apim-foundry-${suffix}'
}

resource gnewsKey 'Microsoft.ApiManagement/service/namedValues@2024-06-01-preview' = {
  parent: apim
  name: 'gnews-api-key'
  properties: {
    displayName: 'gnews-api-key'
    secret: true
    value: gnewsApiKey
  }
}

// The MCP endpoint itself: GNews serves MCP at its root.
resource gnewsBackend 'Microsoft.ApiManagement/service/backends@2024-06-01-preview' = {
  parent: apim
  name: 'gnews-mcp'
  properties: {
    description: 'GNews MCP server (lab 08-05c)'
    protocol: 'http'
    url: 'https://mcp.gnews.io/'
  }
}

// An MCP API with a backendId proxies that MCP server. Without one, APIM answers initialize itself
// and lists the tools of the API's own operations, which here would be none.
resource api 'Microsoft.ApiManagement/service/apis@2024-06-01-preview' = {
  parent: apim
  name: 'news-mcp'
  properties: {
    displayName: 'GNews MCP (lab 08-05c)'
    type: 'mcp'
    path: 'news-mcp'
    protocols: ['https']
    subscriptionRequired: false
    // Bicep's type data for this api-version lacks the two MCP properties; the service accepts them.
    #disable-next-line BCP037
    backendId: gnewsBackend.name
    #disable-next-line BCP037
    mcpProperties: {
      transportType: 'streamable'
    }
  }
}

// rawxml because the policy expressions contain As<JObject> and quotes, which are not valid XML.
resource policy 'Microsoft.ApiManagement/service/apis/policies@2024-06-01-preview' = {
  parent: api
  name: 'policy'
  properties: {
    format: 'rawxml'
    value: replace(
      replace(loadTextContent('news-mcp-policy.xml'), '__TENANT_ID__', tenantId),
      '__AUDIENCES__',
      join(map(audiences, audience => '<audience>${audience}</audience>'), '')
    )
  }
  dependsOn: [gnewsKey] // the policy reads {{gnews-api-key}}
}

// APIM serves an MCP API's endpoint at /mcp under the API's path.
output mcpUrl string = '${apim.properties.gatewayUrl}/news-mcp/mcp'
