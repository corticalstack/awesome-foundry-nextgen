# Foundry for Visual Studio Code Extension

The Foundry for VS Code extension integrates Azure AI Foundry capabilities directly into the Visual Studio Code editor. It provides access to the model catalog, model playground, agent builders, and Foundry project management without leaving the IDE.

**Primary source:** [Work with the Microsoft Foundry for Visual Studio Code extension](https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/develop/get-started-projects-vs-code)

---

## What the Extension Does

| Capability | Description |
|------------|-------------|
| Model catalog | Browse, filter, and deploy models from the Foundry model catalog |
| Model playground | Interact with deployed models via a chat interface inside VS Code |
| Agent builders | Build and test declarative and hosted agents |
| Project connection | Connect to an existing Foundry project and view its resources |
| Code generation | Generate SDK sample code for deployed models in multiple languages |
| Resource management | Create projects, deploy models, manage connections and vector stores |

The extension does not provide full parity with the Foundry portal. Features such as advanced evaluation configuration, fleet management (Control Plane), and policy administration require the full portal at [ai.azure.com](https://ai.azure.com).

---

## Prerequisites

- An Azure subscription (free account eligible)
- [Visual Studio Code](https://code.visualstudio.com/Download) installed
- Appropriate RBAC permissions:
  - **Azure AI User** — minimum for development (call models, work with agents)
  - **Azure AI Project Manager** — for creating and managing Foundry projects
- Quota headroom to deploy new models (or an existing deployed chat model)

---

## Installation

**Extension details:**
- Name: `Foundry for Visual Studio Code`
- Publisher ID: `TeamsDevApp.vscode-ai-foundry`
- Marketplace: [Foundry for Visual Studio Code](https://marketplace.visualstudio.com/items?itemName=TeamsDevApp.vscode-ai-foundry)

### Install from the VS Code Marketplace

1. Open the [Foundry for Visual Studio Code extension page](https://marketplace.visualstudio.com/items?itemName=TeamsDevApp.vscode-ai-foundry)
2. Select **Install**
3. Follow prompts to complete installation in VS Code
4. The Foundry icon appears in the primary navigation bar (left side)

### Install from within VS Code

1. Open VS Code
2. Select **Extensions** from the left activity bar
3. Select the **Settings** icon at the top-right of the extensions pane
4. Search for **Foundry** and select the extension
5. Select **Install**
6. The Foundry icon appears in the activity bar after installation

---

## Authentication

The extension uses the Azure account sign-in managed by the **Azure Resources** VS Code extension (installed as a dependency).

**Sign in steps:**

1. Select the Azure icon on the VS Code activity bar
2. Select **Sign in to Azure...** in the **Azure Resources** view
3. Complete browser-based authentication
4. Under **Resources**, select your Azure subscription and resource group
5. Navigate to **Foundry** and right-click your project
6. Select **Open in Foundry Extension**

Use the Command Palette (`F1`) and search "Foundry" for a full list of available commands.

---

## Extension Interface

The extension organises resources into three sections in the sidebar:

| Section | Contents | Primary use |
|---------|----------|-------------|
| **Resources** | Deployed models, declarative agents, hosted agents, connections, vector stores | View and manage existing project resources |
| **Tools** | Model Catalog, Model Playground, Agent Playgrounds (remote and local), Local Visualizer, Deploy Hosted Agents | Deploy new models, test prompts, interact with agents |
| **Help and Feedback** | Documentation links, GitHub repository, privacy statement, community links | Access support resources |

---

## Working with Models

### Browse the model catalog

Access paths:
- Command Palette (`F1`): `Foundry: Open Model Catalog`
- Plus icon next to **Models** in the Resources section
- **Model Catalog** link in the Tools section

Filter the catalog by: **Hosted by**, **Publisher**, **Feature**, **Model type**. Toggle **Fine-Tuning Support** to filter models that support fine-tuning. Providers include Microsoft, OpenAI, Meta, DeepSeek, and others.

### Deploy a model

1. Select **Deploy** next to the model name in the catalog
2. Enter a deployment name
3. Select the deployment type from the dropdown
4. Select the model version
5. (Optional) Adjust tokens per minute using the slider
6. Select **Deploy in Foundry** (bottom-left)
7. Confirm in the dialog
8. The model appears under **Models** in the Resources section after deployment

### View deployed model details

Expand the **Models** section and select a model to view its card:

- **Deployment Info:** name, provisioning state, deployment type, rate limit, version
- **Endpoint info:** target URI, authentication type, API key
- **Useful links:** code sample repository and tutorial links

### Generate SDK sample code

1. Right-click a deployed model → **Open code file**
2. Select the preferred SDK (Foundry SDK, OpenAI SDK, etc.)
3. Select the preferred language (Python, JavaScript, C#, Java)
4. Select the preferred authentication method
5. A sample code file opens in a new editor tab

### Use the model playground

Open the playground by double-clicking **Model Playground** in the Tools section, or by right-clicking a deployed model → **Open in playground**.

Features:
- Enter prompts and view responses
- **View code** button (top-right): displays the equivalent SDK code for the current exchange
- **History** link (top-left): displays previous chat sessions

---

## Creating a New Foundry Project

1. Select the plus icon next to **Resources** in the sidebar
2. Choose or create a resource group:
   - To create: select **Create new resource group**, enter a name, select a location
   - To use existing: select the resource group from the list
3. Enter a project name in the **Enter project name** field
4. After deployment, a confirmation popup appears
5. Optionally select **Deploy a model** in the popup to open the Model Catalog immediately

### Switch the default project

1. Right-click on a Foundry project → **Switch Default Project in Azure Extension**
2. Select the project from the list
3. The selected project displays **Default** after its name

Tip: Right-click a project name to copy the project endpoint or API key.

---

## Limitations vs Full Portal

| Capability | Extension | Portal (ai.azure.com) |
|------------|-----------|----------------------|
| Model catalog and deployment | Yes | Yes |
| Model playground | Yes | Yes |
| Agent builder (basic) | Yes | Yes |
| Control Plane (fleet management) | No | Yes |
| Guardrail policy management | No | Yes |
| Evaluation configuration | No | Yes |
| AI Red Teaming Agent | No | Yes |
| Security integrations (Defender, Purview) | No | Yes |
| Quota management | No | Yes |

---

## Troubleshooting

| Issue | Resolution |
|-------|-----------|
| Extension does not appear after installation | Restart VS Code; verify the extension is enabled under **Extensions** |
| Sign-in fails or subscriptions do not load | Verify Azure account permissions; sign out and sign in again from **Azure Resources** |
| Model deployment fails with a quota error | Check subscription quota in the Azure portal; request an increase or delete unused deployments |
| Extension commands not visible in Command Palette | Confirm the extension is installed and VS Code has reloaded |

---

## Cleaning Up Resources

### Delete a deployed model

1. Refresh the Foundry extension in the VS Code activity bar
2. Expand the **Models** section under Resources
3. Right-click the model → **Delete**

### Delete Azure resources

> **Warning:** Deleting a resource group permanently removes all resources within it, including the Foundry project and all deployed models. This action cannot be undone.

1. Open the [Azure portal](https://portal.azure.com)
2. Navigate to the resource group
3. Select **Delete resource group** and confirm

---

## Related Resources

- [Foundry for VS Code extension on the Marketplace](https://marketplace.visualstudio.com/items?itemName=TeamsDevApp.vscode-ai-foundry)
- [Foundry SDK overview](04-03-foundry-api-and-sdks.md)
- [Role-based access control for Foundry](https://learn.microsoft.com/en-us/azure/ai-foundry/concepts/rbac-foundry)
