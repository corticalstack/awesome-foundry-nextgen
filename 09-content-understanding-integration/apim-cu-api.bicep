// ============================================================================
// Lab 10: Content Understanding API on existing core APIM
// Adds the /cu API with 7 operations and a governance policy to the APIM
// instance in rg-foundry-core-{suffix}.
// Deployed to the core resource group by 10-00-deploy-setup.ipynb.
// ============================================================================
targetScope = 'resourceGroup'

param apimName string
param cuEndpoint string  // e.g. https://aif-cu-{suffix}.cognitiveservices.azure.com

resource apim 'Microsoft.ApiManagement/service@2023-09-01-preview' existing = {
  name: apimName
}

// ─────────────────────────────────────────────────────────────────────────────
// Content Understanding API
// ─────────────────────────────────────────────────────────────────────────────
resource cuApi 'Microsoft.ApiManagement/service/apis@2023-09-01-preview' = {
  parent: apim
  name: 'content-understanding-api'
  properties: {
    displayName: 'Content Understanding API'
    description: 'Governed access to Azure AI Content Understanding'
    path: 'cu'
    protocols: ['https']
    serviceUrl: '${cuEndpoint}/contentunderstanding'
    subscriptionRequired: true
    subscriptionKeyParameterNames: {
      header: 'api-key'
      query: 'api-key'
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Operations (7 total — same set as the original Lab 10 APIM definition)
// ─────────────────────────────────────────────────────────────────────────────
resource analyzeOperation 'Microsoft.ApiManagement/service/apis/operations@2023-09-01-preview' = {
  parent: cuApi
  name: 'analyze'
  properties: {
    displayName: 'Analyze Content'
    method: 'POST'
    urlTemplate: '/analyzers/{analyzer}:analyze'
    description: 'Submit content for analysis using specified analyzer'
    templateParameters: [
      {
        name: 'analyzer'
        type: 'string'
        required: true
        description: 'Analyzer ID (e.g., prebuilt-layout, prebuilt-videoSearch)'
      }
    ]
  }
}

resource getResultOperation 'Microsoft.ApiManagement/service/apis/operations@2023-09-01-preview' = {
  parent: cuApi
  name: 'get-result'
  properties: {
    displayName: 'Get Analysis Result'
    method: 'GET'
    urlTemplate: '/analyzers/{analyzer}/results/{resultId}'
    description: 'Get the result of an analysis operation'
    templateParameters: [
      {
        name: 'analyzer'
        type: 'string'
        required: true
      }
      {
        name: 'resultId'
        type: 'string'
        required: true
      }
    ]
  }
}

resource catchAllGet 'Microsoft.ApiManagement/service/apis/operations@2023-09-01-preview' = {
  parent: cuApi
  name: 'catch-all-get'
  properties: {
    displayName: 'Catch-All GET'
    method: 'GET'
    urlTemplate: '/*'
    description: 'Catch-all for GET requests'
  }
}

resource catchAllPost 'Microsoft.ApiManagement/service/apis/operations@2023-09-01-preview' = {
  parent: cuApi
  name: 'catch-all-post'
  properties: {
    displayName: 'Catch-All POST'
    method: 'POST'
    urlTemplate: '/*'
    description: 'Catch-all for POST requests'
  }
}

resource listAnalyzersOperation 'Microsoft.ApiManagement/service/apis/operations@2023-09-01-preview' = {
  parent: cuApi
  name: 'list-analyzers'
  properties: {
    displayName: 'List Analyzers'
    method: 'GET'
    urlTemplate: '/analyzers'
    description: 'List available analyzers'
  }
}

resource getDefaultsOperation 'Microsoft.ApiManagement/service/apis/operations@2023-09-01-preview' = {
  parent: cuApi
  name: 'get-defaults'
  properties: {
    displayName: 'Get Defaults'
    method: 'GET'
    urlTemplate: '/defaults'
    description: 'Get CU default model configuration'
  }
}

resource patchDefaultsOperation 'Microsoft.ApiManagement/service/apis/operations@2023-09-01-preview' = {
  parent: cuApi
  name: 'patch-defaults'
  properties: {
    displayName: 'Update Defaults'
    method: 'PATCH'
    urlTemplate: '/defaults'
    description: 'Update CU default model configuration (admin)'
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// API-level policy — governance controls (preserved verbatim)
// ─────────────────────────────────────────────────────────────────────────────
resource cuApiPolicy 'Microsoft.ApiManagement/service/apis/policies@2023-09-01-preview' = {
  parent: cuApi
  name: 'policy'
  properties: {
    format: 'xml'
    value: '''<policies>
    <inbound>
        <base />

        <!-- Rate limiting: 30 calls per minute per subscription -->
        <rate-limit-by-key
            calls="30"
            renewal-period="60"
            counter-key="@(context.Subscription.Id)" />

        <!-- Quota: 1000 calls per day per subscription -->
        <quota-by-key
            calls="1000"
            renewal-period="86400"
            counter-key="@(context.Subscription.Id)" />

        <!-- Add correlation ID for tracing -->
        <set-header name="X-Correlation-Id" exists-action="override">
            <value>@(context.RequestId.ToString())</value>
        </set-header>

        <!-- Add api-version if not present -->
        <set-query-parameter name="api-version" exists-action="skip">
            <value>2025-11-01</value>
        </set-query-parameter>

        <!-- Authenticate with managed identity to CU backend -->
        <authentication-managed-identity resource="https://cognitiveservices.azure.com" />

        <!-- CORS for browser-based access -->
        <cors>
            <allowed-origins>
                <origin>*</origin>
            </allowed-origins>
            <allowed-methods>
                <method>GET</method>
                <method>POST</method>
                <method>PATCH</method>
                <method>OPTIONS</method>
            </allowed-methods>
            <allowed-headers>
                <header>*</header>
            </allowed-headers>
        </cors>
    </inbound>
    <backend>
        <base />
    </backend>
    <outbound>
        <base />
        <!-- Tag responses as coming through the AI Gateway -->
        <set-header name="X-AI-Gateway" exists-action="override">
            <value>foundry-landing-zone-cu-1.0</value>
        </set-header>
    </outbound>
    <on-error>
        <base />
    </on-error>
</policies>'''
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Outputs
// ─────────────────────────────────────────────────────────────────────────────
output apiPath string = 'cu'
