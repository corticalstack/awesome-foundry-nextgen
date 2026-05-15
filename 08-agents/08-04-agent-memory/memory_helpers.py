"""
Memory API helpers for Lab 5: Agent Memory
"""
import subprocess
import time
import requests


def get_token() -> str:
    """Get access token with correct audience for Memory API."""
    result = subprocess.run(
        'az account get-access-token --resource https://ai.azure.com --query accessToken -o tsv',
        shell=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def get_headers() -> dict:
    """Get headers with fresh token for Memory API calls."""
    return {
        'Authorization': f'Bearer {get_token()}',
        'Content-Type': 'application/json'
    }


class MemoryClient:
    """Simple client for Memory API operations."""
    
    API_VERSION = "2025-11-15-preview"
    
    def __init__(self, account_name: str, project_name: str):
        self.base_url = f"https://{account_name}.services.ai.azure.com/api/projects/{project_name}"
    
    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path}?api-version={self.API_VERSION}"
    
    def create_store(self, name: str, chat_model: str, embedding_model: str, 
                     description: str = "", user_profile_details: str = "") -> dict:
        """Create a memory store with the specified models."""
        # Delete existing if any
        requests.delete(self._url(f"memory_stores/{name}"), headers=get_headers())
        
        payload = {
            "name": name,
            "description": description,
            "definition": {
                "kind": "default",
                "chat_model": chat_model,
                "embedding_model": embedding_model,
                "options": {
                    "user_profile_enabled": True,
                    "user_profile_details": user_profile_details,
                    "chat_summary_enabled": True
                }
            }
        }
        
        response = requests.post(self._url("memory_stores"), headers=get_headers(), json=payload)
        
        if response.status_code in [200, 201]:
            return response.json()
        else:
            return {"error": f"{response.status_code}: {response.text}"}
    
    def update_memories(self, store_name: str, scope: str, messages: list, timeout: int = 60) -> dict:
        """Update memories from a conversation with polling for completion."""
        payload = {"scope": scope, "items": messages, "update_delay": 0}
        
        response = requests.post(
            self._url(f"memory_stores/{store_name}:update_memories"),
            headers=get_headers(), json=payload
        )
        
        if response.status_code not in [200, 202]:
            return {"error": f"{response.status_code}: {response.text}"}
        
        result = response.json()
        update_id = result.get('update_id')
        
        # Poll for completion
        start = time.time()
        while time.time() - start < timeout:
            status_resp = requests.get(
                self._url(f"memory_stores/{store_name}/updates/{update_id}"),
                headers=get_headers()
            )
            if status_resp.status_code == 200:
                status = status_resp.json()
                if status.get('status') == 'completed':
                    return status
                elif status.get('status') == 'failed':
                    return {"error": status.get('error', 'Unknown error')}
            time.sleep(2)
        
        return {"error": "Timeout waiting for memory update"}
    
    def search_memories(self, store_name: str, scope: str, query: str, max_results: int = 5) -> dict:
        """Search memories by scope and query."""
        payload = {"scope": scope, "query": query, "max_num_results": max_results}
        response = requests.post(
            self._url(f"memory_stores/{store_name}:search_memories"),
            headers=get_headers(), json=payload
        )
        return response.json() if response.status_code == 200 else {"error": response.text}


def build_conversation(user_text: str, assistant_text: str) -> list:
    """Build a conversation in Memory API format."""
    return [
        {"type": "message", "role": "user", "content": [{"type": "input_text", "text": user_text}]},
        {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": assistant_text}]}
    ]
