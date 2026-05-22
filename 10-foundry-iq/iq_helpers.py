"""
Foundry IQ helpers
"""
import subprocess
import requests


def get_mgmt_token() -> str:
    """Get access token for Azure Management API."""
    result = subprocess.run(
        'az account get-access-token --resource https://management.azure.com --query accessToken -o tsv',
        shell=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def create_mcp_connection(subscription_id: str, resource_group: str, 
                          account_name: str, project_name: str,
                          connection_name: str, search_endpoint: str, 
                          kb_name: str) -> dict:
    """Create a RemoteTool (MCP) connection from Foundry project to knowledge base."""
    
    mcp_endpoint = f"{search_endpoint}/knowledgebases/{kb_name}/mcp?api-version=2025-11-01-preview"
    
    url = (f"https://management.azure.com/subscriptions/{subscription_id}"
           f"/resourceGroups/{resource_group}"
           f"/providers/Microsoft.CognitiveServices/accounts/{account_name}"
           f"/projects/{project_name}/connections/{connection_name}"
           f"?api-version=2025-04-01-preview")
    
    payload = {
        "properties": {
            "authType": "ProjectManagedIdentity",
            "category": "RemoteTool",
            "target": mcp_endpoint,
            "isSharedToAll": True,
            "audience": "https://search.azure.com/",
            "metadata": {"ApiType": "Azure"}
        }
    }
    
    resp = requests.put(
        url,
        headers={
            'Authorization': f'Bearer {get_mgmt_token()}',
            'Content-Type': 'application/json'
        },
        json=payload
    )
    
    return resp.json() if resp.status_code in [200, 201] else {"error": resp.text, "status": resp.status_code}
