"""
Azure Infrastructure Utilities

Handles provisioning Azure resources (ACA, Storage, GPU) for fine-tuning.
"""
import subprocess
import json
import shlex
import time
import os
from typing import Tuple

def run_az(cmd: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run Azure CLI command."""
    print(f"Executing: az {cmd[:50]}...")
    result = subprocess.run(["az"] + shlex.split(cmd), capture_output=True, text=True)
    if check and result.returncode != 0:
        raise Exception(f"Azure CLI error: {result.stderr}")
    return result

def provision_infrastructure(
    resource_group: str,
    location: str,
    storage_account: str,
    container_name: str,
    aca_env_name: str,
    training_data_path: str
) -> str:
    """Provision Resource Group, Storage, and ACA Environment with GPU support."""
    
    # 1. Resource Group
    run_az(f"group create --name {resource_group} --location {location}")
    
    # 2. Storage Account
    run_az(f"storage account create --name {storage_account} --resource-group {resource_group} --sku Standard_LRS", check=False)
    
    # 3. Role Assignment (Storage Blob Data Contributor to User)
    user_id = json.loads(run_az("ad signed-in-user show -o json").stdout)["id"]
    storage_id = json.loads(run_az(f"storage account show --name {storage_account} --resource-group {resource_group} -o json").stdout)["id"]
    
    run_az(f"role assignment create --role 'Storage Blob Data Contributor' --assignee {user_id} --scope {storage_id}", check=False)
    
    # 4. Upload Data
    run_az(f"storage container create --name {container_name} --account-name {storage_account} --auth-mode login", check=False)
    run_az(f"storage blob upload --account-name {storage_account} --container-name {container_name} --file {training_data_path} --name train.jsonl --auth-mode login --overwrite", check=False)
    
    # 5. ACA Environment (with A100 GPU profile)
    run_az(f"containerapp env create --name {aca_env_name} --resource-group {resource_group} --location {location} --enable-workload-profiles", check=False)
    
    # Add GPU profile if not exists
    run_az(f"containerapp env workload-profile add --name {aca_env_name} --resource-group {resource_group} --workload-profile-name gpu-a100 --workload-profile-type Consumption-GPU-NC24-A100", check=False)
    
    env_id = json.loads(run_az(f"containerapp env show --name {aca_env_name} --resource-group {resource_group} -o json").stdout)["id"]
    return env_id

def submit_finetune_job(
    job_name: str,
    resource_group: str,
    env_id: str,
    storage_account: str,
    container_name: str,
    base_model: str,
    location: str
):
    """Submit the Olive fine-tuning job to ACA."""
    
    script = (
        "source /opt/conda/etc/profile.d/conda.sh && conda activate ptca && "
        "pip install --no-cache-dir transformers==4.53.3 accelerate datasets peft olive-ai[auto-opt] azure-storage-blob azure-cli && "
        "az login --identity && mkdir -p /data /output && "
        f"az storage blob download --account-name {storage_account} --container-name {container_name} --name train.jsonl --file /data/train.jsonl --auth-mode login && "
        f"olive finetune --method lora --model_name_or_path {base_model} --trust_remote_code "
        "--data_name json --data_files /data/train.jsonl "
        "--text_template '<|system|>{system}<|end|><|user|>{user}<|end|><|assistant|>{assistant}<|end|>' "
        "--max_steps 300 --learning_rate 2e-4 --output_path /output/ft "
        "--target_modules qkv_proj,o_proj,gate_up_proj,down_proj --log_level 1 && "
        f"az storage blob upload-batch --account-name {storage_account} --auth-mode login --destination {container_name} --source /output/ft --destination-path ft/"
    )

    run_az(f"containerapp job delete --name {job_name} --resource-group {resource_group} --yes", check=False)
    time.sleep(5)

    
    job_spec = {
        "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
        "contentVersion": "1.0.0.0",
        "resources": [{
            "type": "Microsoft.App/jobs",
            "apiVersion": "2024-03-01",
            "name": job_name,
            "location": location,
            "identity": {"type": "SystemAssigned"},
            "properties": {
                "environmentId": env_id,
                "workloadProfileName": "gpu-a100",
                "configuration": {"triggerType": "Manual", "replicaTimeout": 7200, "replicaRetryLimit": 0},
                "template": {
                    "containers": [{
                        "name": "finetune",
                        "image": "mcr.microsoft.com/azureml/curated/acpt-pytorch-2.2-cuda12.1:latest",
                        "resources": {"cpu": 12, "memory": "32Gi"},
                        "command": ["/bin/bash", "-c", script]
                    }]
                }
            }
        }]
    }
    
    with open("job.json", "w") as f:
        json.dump(job_spec, f, indent=2)
        
    run_az(f"deployment group create --resource-group {resource_group} --template-file job.json --name {job_name}-deploy")
    
    job_id = json.loads(run_az(f"containerapp job show --name {job_name} --resource-group {resource_group} -o json").stdout)
    principal_id = job_id["identity"]["principalId"]
    storage_id = json.loads(run_az(f"storage account show --name {storage_account} --resource-group {resource_group} -o json").stdout)["id"]
    
    run_az(f"role assignment create --role 'Storage Blob Data Contributor' --assignee-object-id {principal_id} --assignee-principal-type ServicePrincipal --scope {storage_id}", check=False)
    
    time.sleep(15)
    run_az(f"containerapp job start --name {job_name} --resource-group {resource_group}")
    print("Fine-tuning job started on ACA Serverless GPU.")

def monitor_job(job_name: str, resource_group: str) -> bool:
    """Poll job status until success or failure."""
    print("Monitoring job...")
    while True:
        status_json = run_az(f"containerapp job execution list --name {job_name} --resource-group {resource_group} -o json", check=False)
        if status_json.returncode == 0:
            executions = json.loads(status_json.stdout)
            if executions:
                status = executions[0]["properties"]["status"]
                print(f"Status: {status}")
                if status == "Succeeded": return True
                if status == "Failed": return False
        time.sleep(30)

def download_model(storage_account: str, container_name: str, output_path: str):
    """Download fine-tuned adapter."""
    os.makedirs(output_path, exist_ok=True)
    # Workaround for Azure CLI 2.77.0 + Python 3.13 bug with --pattern flag
    # List blobs first, then download individually
    list_result = run_az(f"storage blob list --account-name {storage_account} --container-name {container_name} --prefix ft/ --auth-mode login -o json", check=False)
    if list_result.returncode == 0:
        blobs = json.loads(list_result.stdout)
        for blob in blobs:
            blob_name = blob["name"]
            local_path = os.path.join(output_path, blob_name)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            run_az(f"storage blob download --account-name {storage_account} --container-name {container_name} --name {blob_name} --file {local_path} --auth-mode login")
        print(f"Downloaded {len(blobs)} files to {output_path}")
    else:
        raise Exception(f"Failed to list blobs: {list_result.stderr}")


def submit_evaluation_job(
    job_name: str,
    resource_group: str,
    env_id: str,
    storage_account: str,
    container_name: str,
    base_model: str,
    location: str
):
    """Submit evaluation job to ACA with GPU."""
    
    script = (
        "source /opt/conda/etc/profile.d/conda.sh && conda activate ptca && "
        "pip install --no-cache-dir transformers==4.53.3 accelerate peft azure-storage-blob azure-cli && "
        "az login --identity && mkdir -p /data/ft/adapter /output && "
        # Download adapter files individually (workaround for pattern issues)
        f"for blob in $(az storage blob list --account-name {storage_account} --container-name {container_name} --prefix ft/ --auth-mode login --query '[].name' -o tsv); do "
        f"mkdir -p /data/$(dirname $blob) && az storage blob download --account-name {storage_account} --container-name {container_name} --name $blob --file /data/$blob --auth-mode login; done && "
        f"ls -la /data/ft/adapter/ && "  # Debug: list adapter files
        # Download eval data and script
        f"az storage blob download --account-name {storage_account} --container-name {container_name} --name eval_data.json --file /data/eval_data.json --auth-mode login && "
        f"az storage blob download --account-name {storage_account} --container-name {container_name} --name eval_script.py --file /data/eval_script.py --auth-mode login && "
        # Run evaluation script
        "python3 /data/eval_script.py && "
        # Upload results
        f"az storage blob upload --account-name {storage_account} --container-name {container_name} --file /output/eval_results.json --name eval_results.json --auth-mode login --overwrite"
    )
    
    run_az(f"containerapp job delete --name {job_name} --resource-group {resource_group} --yes", check=False)
    time.sleep(5)
    
    job_spec = {
        "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
        "contentVersion": "1.0.0.0",
        "resources": [{
            "type": "Microsoft.App/jobs",
            "apiVersion": "2024-03-01",
            "name": job_name,
            "location": location,
            "identity": {"type": "SystemAssigned"},
            "properties": {
                "environmentId": env_id,
                "workloadProfileName": "gpu-a100",
                "configuration": {"triggerType": "Manual", "replicaTimeout": 3600, "replicaRetryLimit": 0},
                "template": {
                    "containers": [{
                        "name": "evaluate",
                        "image": "mcr.microsoft.com/azureml/curated/acpt-pytorch-2.2-cuda12.1:latest",
                        "resources": {"cpu": 12, "memory": "32Gi"},
                        "command": ["/bin/bash", "-c", script]
                    }]
                }
            }
        }]
    }
    
    with open("eval_job.json", "w") as f:
        json.dump(job_spec, f, indent=2)
        
    run_az(f"deployment group create --resource-group {resource_group} --template-file eval_job.json --name {job_name}-deploy")
    
    # Assign storage permissions
    job_id = json.loads(run_az(f"containerapp job show --name {job_name} --resource-group {resource_group} -o json").stdout)
    principal_id = job_id["identity"]["principalId"]
    storage_id = json.loads(run_az(f"storage account show --name {storage_account} --resource-group {resource_group} -o json").stdout)["id"]
    
    run_az(f"role assignment create --role 'Storage Blob Data Contributor' --assignee-object-id {principal_id} --assignee-principal-type ServicePrincipal --scope {storage_id}", check=False)
    
    time.sleep(15)
    run_az(f"containerapp job start --name {job_name} --resource-group {resource_group}")
    print("Evaluation job started on ACA GPU.")


def upload_eval_data(storage_account: str, container_name: str, eval_dataset: list, reports_data: dict, base_model: str):
    """Upload evaluation data and script to blob storage."""
    import tempfile
    
    # Create eval data bundle
    eval_bundle = {
        "eval_dataset": eval_dataset,
        "reports_data": reports_data,
        "base_model": base_model
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(eval_bundle, f)
        eval_data_path = f.name
    
    # Create eval script
    eval_script = '''
import json
import torch
import re
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

# Load data
with open("/data/eval_data.json") as f:
    data = json.load(f)

eval_dataset = data["eval_dataset"]
reports_data = data["reports_data"]
base_model = data["base_model"]

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Using device: {device}")

# Load model
tokenizer = AutoTokenizer.from_pretrained(base_model, trust_remote_code=True)
base = AutoModelForCausalLM.from_pretrained(base_model, torch_dtype=torch.float16, trust_remote_code=True).to(device)
ft_model = PeftModel.from_pretrained(base, "/data/ft/adapter")
ft_model.eval()
print("Model loaded!")

# Classification prompt (same as iss_utils)
SYSTEM_PROMPT = """You are an expert ISS Flight Controller. Your primary job is to classify the daily station status report into exactly one severity level.

SEVERITY DEFINITIONS (Highest to Lowest):

1. CRITICAL - Immediate threat to Crew Safety or Vehicle Integrity.
2. WARNING - Loss of a critical system function or redundancy.
3. CAUTION - Degraded component performance or localized failure.
4. ADVISORY - Minor off-nominal condition with no impact.
5. NOMINAL - Normal operations.

Strict Output Format:
SEVERITY: <nominal, advisory, caution, warning, or critical>
CATEGORY: <eclss, power, thermal, structure, gnc, eva, comms, software, payload, or none>
SUMMARY: <1 sentence summary>
REASONING: <Explain clearly why this severity was chosen over others>"""

def query_model(report_text):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Analyze this ISS Daily Summary Report:\\n\\n{report_text[:6000]}"}
    ]
    inputs = tokenizer.apply_chat_template(messages, add_generation_prompt=True, return_tensors="pt").to(device)
    with torch.no_grad():
        outputs = ft_model.generate(inputs, max_new_tokens=300, do_sample=False)
    return tokenizer.decode(outputs[0][len(inputs[0]):], skip_special_tokens=True)

def parse_response(response):
    result = {"severity": "unknown", "category": "unknown"}
    m = re.search(r"SEVERITY:\\s*(\\w+)", response, re.IGNORECASE)
    if m: result["severity"] = m.group(1).lower()
    m = re.search(r"CATEGORY:\\s*(\\w+)", response, re.IGNORECASE)
    if m: result["category"] = m.group(1).lower()
    return result

# Run evaluation
results = []
for item in eval_dataset:
    date = item["date"]
    if date not in reports_data:
        continue
    
    report_text = reports_data[date]["report_text"]
    raw_response = query_model(report_text)
    prediction = parse_response(raw_response)
    
    exact_match = prediction["severity"] == item["expected_severity"]
    
    results.append({
        "date": date,
        "expected": item["expected_severity"],
        "predicted": prediction["severity"],
        "exact_match": exact_match,
        "raw_response": raw_response
    })
    print(f"{date}: {prediction['severity']} vs {item['expected_severity']} - {'OK' if exact_match else 'MISMATCH'}")

accuracy = sum(1 for r in results if r["exact_match"]) / len(results)
print(f"\\nAccuracy: {accuracy:.1%}")

# Save results
with open("/output/eval_results.json", "w") as f:
    json.dump({"accuracy": accuracy, "results": results}, f, indent=2)

print("Results saved to /output/eval_results.json")
'''
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(eval_script)
        script_path = f.name
    
    # Upload both files
    run_az(f"storage blob upload --account-name {storage_account} --container-name {container_name} --file {eval_data_path} --name eval_data.json --auth-mode login --overwrite")
    run_az(f"storage blob upload --account-name {storage_account} --container-name {container_name} --file {script_path} --name eval_script.py --auth-mode login --overwrite")
    
    print("Uploaded eval data and script to blob storage.")


def download_eval_results(storage_account: str, container_name: str) -> dict:
    """Download evaluation results from blob storage."""
    import tempfile
    
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
        output_path = f.name
    
    run_az(f"storage blob download --account-name {storage_account} --container-name {container_name} --name eval_results.json --file {output_path} --auth-mode login")
    
    with open(output_path) as f:
        results = json.load(f)
    
    return results
