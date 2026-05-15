# Publish Agents to Microsoft Teams and Microsoft 365 Copilot

Publishing a Foundry agent makes it available via Microsoft Teams and Microsoft 365 Copilot. The publish flow creates an agent application backed by Azure Bot Service and an Entra app registration, assigns it a stable endpoint, and packages it for distribution to individuals or the entire organisation.

**Primary source:** [Publish agents to Microsoft 365 Copilot and Microsoft Teams — Microsoft Learn](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/how-to/publish-copilot)

---

## What Publishing Does

Publishing creates an **agent application** with a stable endpoint. The agent application:

- Has its own identity, separate from the Foundry project identity
- Can be invoked via the Responses API protocol
- Can be distributed to Microsoft Teams and Microsoft 365 Copilot
- Is backed by an Azure Bot Service resource and a Microsoft Entra app registration

After publishing, the agent uses the agent application identity for authentication to Azure resources. Any RBAC permissions previously granted to the project identity must be reassigned to the agent application identity.

---

## Prerequisites

- Access to the Microsoft Foundry portal ([ai.azure.com](https://ai.azure.com))
- A Foundry project with a tested agent version
- RBAC role assignments:
  - **Azure AI Project Manager** on the Foundry project scope — required to publish agents
  - **Azure AI User** on the agent application scope — required to invoke the published agent
- An Azure subscription where you can create Azure Bot Service resources and Microsoft Entra ID app registrations
- Agent thoroughly tested in the Foundry portal before publishing
- `Microsoft.BotService` resource provider registered in the subscription

**Register the BotService provider:**

```azurecli
az provider register --namespace Microsoft.BotService
```

---

## Step 1: Publish the Agent as an Agent Application

1. In the Foundry portal, select your agent version
2. Select **Publish** — a publishing dialog opens with distribution options
3. An agent application is created with a stable endpoint

---

## Step 2: Publish to Microsoft Teams and Microsoft 365 Copilot

1. Select **Publish** again → **Publish to Teams and Microsoft 365 Copilot**
2. Application ID and tenant ID are generated automatically (note these for troubleshooting)
3. In the Azure Bot Service dropdown, select **Create an Azure Bot Service**
4. Complete the required metadata fields:

**Table: Required metadata fields**

| Field | Description | Notes |
|-------|-------------|-------|
| **Name** | Display name for the agent in the agent store | Keep concise |
| **Short description** | One-sentence description of what the agent does | Visible in agent store listings |
| **Full description** | Longer description of responsibilities and actions | Used in detail views |
| **Publisher information** | Organisation name or developer name | 32 characters or fewer |
| **Website** | URL to the publisher's website | Must be HTTPS |
| **Privacy statement URL** | URL to the privacy policy | Must be HTTPS |
| **Terms of use URL** | URL to the terms of use | Must be HTTPS |

> **Warning:** Do not include secrets, API keys, or sensitive information in any metadata fields. These fields are visible to users.

Placeholder HTTPS URLs are acceptable for individual developers and testing purposes.

5. Select **Prepare Agent** — packaging typically takes **1–2 minutes**
6. When ready, choose either:
   - **Download the package** — test locally before publishing
   - **Continue the in-product publishing flow** — publish directly to Teams and M365 Copilot

---

## Step 3: Choose a Publish Scope

| Scope | Visibility | Admin approval required | Best for |
|-------|------------|------------------------|---------|
| **Individual** | Appears under **Your agents** in the agent store | No | Personal testing, small pilots |
| **Organisation** | Appears under **Built by your org** in the agent store | Yes | Organisation-wide distribution |

### Individual scope

- Agent is available immediately after publishing
- Only the publisher sees the agent initially
- Share with specific users by providing the agent link
- No admin approval or tenant configuration required

### Organisation scope

- Admin must approve the app in the [Microsoft 365 admin center](https://admin.cloud.microsoft/?#/agents/all/requested)
- After approval, appears under **Built by your org** for all tenant users
- App policies in the tenant control which users can access the agent
- Check approval status under **Requests** in the M365 admin center

---

## Testing the Package Locally

1. Download the `.zip` package
2. In Microsoft Teams:
   - Open Teams
   - Navigate to **Apps** → **Manage your apps** → **Upload an app**
   - Select **Upload a custom app** → choose the `.zip` file
3. Open the agent in Teams and send a test message

**Verification checklist:**
- Agent responds to messages in Teams
- Configured tools execute correctly
- Agent application identity has access to required Azure resources
- Response times are acceptable for the use case

---

## Current Limitations

All limitations listed below are temporary with fixes in progress per the documentation.

| Limitation | Description |
|------------|-------------|
| File uploads and image generation in Microsoft 365 | These features do not work for agents published to M365 Copilot. They work correctly in Microsoft Teams. |
| Private Link | Private Link is not supported for Teams or Azure Bot Service integrations. |
| Streaming and citations | Published agents do not support streaming responses or citations. |

---

## Troubleshooting

| Issue | Cause | Resolution |
|-------|-------|-----------|
| Error preparing the agent | Invalid agent version or metadata | Verify the agent version does not start with `0`. Confirm developer name is 32 characters or fewer. |
| Azure Bot Service creation fails | Missing permissions or unregistered resource provider | Confirm permission to create resources in the subscription. Register `Microsoft.BotService` provider. |
| Organisation scope agent does not appear | Admin approval pending or app policies block access | Confirm admin approved the app in the M365 admin center. Check app policies. |
| Agent works in Foundry but fails after publishing | Agent identity missing required role assignments | The published agent uses its own identity. Reassign RBAC permissions to the agent application identity. |
| Package upload fails in Teams | Invalid package or missing metadata | Verify all required metadata fields are complete. Redownload the package and retry. |
| Agent does not respond in Teams | Bot Service configuration issue | Verify the Azure Bot Service resource is running. Check Bot Service logs in the Azure portal. |
| Users cannot find the agent in the store | Wrong scope or approval pending | For individual scope, share the direct link. For organisation scope, confirm admin approval is complete. |

---

## Frequently Asked Questions

**Q: If I publish to Organisation (tenant) scope, where do I approve the agent?**
In the [Microsoft 365 admin center](https://admin.cloud.microsoft/?#/agents/all/requested). Once approved by an admin, the agent appears under **Built by your org** in the agent store.

**Q: If I publish to Individual Scope, how do I share it with others?**
The agent appears under **Your agents** in the agent store. Share by sending the agent link to specific users in your organisation.

**Q: Can I update an agent after publishing?**
Updating an agent version requires re-publishing. Each published version creates or updates the agent application. Do not reuse an existing agent version number when updating.

---

## Related Resources

- [Role-based access control in the Foundry portal](https://learn.microsoft.com/en-us/azure/ai-foundry/concepts/rbac-foundry)
- [Foundry Agent Service overview](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/overview)
- [Microsoft 365 admin center — Agents](https://admin.cloud.microsoft/?#/agents/all/requested)
