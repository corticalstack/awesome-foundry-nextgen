# Per-user access to an MCP server you do not own

1. **The need.** One Foundry agent, `news-desk-agent`, serves several users from a general news service, GNews, through its MCP server and one API key shared by everyone. User A may read every news category; user B only sports, science and health.
2. **The gap.** The MCP server is third-party (GNews). It knows one API key and no users, so it cannot restrict anyone, and you cannot change it.
3. **The fix.** Foundry swaps the user's token for one that carries their Entra app roles. An **enforcement point** between the agent and GNews validates that token and checks each tool call against the roles: an allowed call goes on with the API key, and a refused call never reaches GNews. The lab builds two examples: a custom wrapper you own (Track A) and a policy on the APIM gateway (Track B), which could be a good choice if you want off-the-shelf and already have an APIM deployment.

[The ticket flow animation](https://htmlpreview.github.io/?https://github.com/corticalstack/awesome-foundry-nextgen/blob/main/docs/diagrams/08-05c-ticket-flow.html) walks through Track B step by step, from user B's sign-in to the policy's decision.

| | User A | User B |
|---|---|---|
| Who | the tenant admin who runs the notebooks | `news-sports-desk`, a test user 08-05c-01 creates |
| App roles on `news-mcp-{suffix}` | `News.Read.All` | `News.Read.Sports`, `News.Read.Science`, `News.Read.Health` |
| Business headlines | yes | no |

## Contents

1. [The requirement](#1-the-requirement)
2. [Why the agent and the third-party MCP server cannot enforce it](#2-why-the-agent-and-the-third-party-mcp-server-cannot-enforce-it)
3. [Two places to enforce it](#3-two-places-to-enforce-it)
4. [How a request carries the user](#4-how-a-request-carries-the-user)
5. [Implementation notes](#5-implementation-notes)
6. [Preview features](#6-preview-features)
7. [Run the lab](#7-run-the-lab)
8. [Teardown](#8-teardown)

## 1. The requirement

- A user's news categories are Entra **app roles** on a resource app, `news-mcp-{suffix}`: `News.Read.All` or one `News.Read.<Category>` role per category, for GNews's nine categories (general, world, nation, business, technology, entertainment, sports, science, health).
- The rule applies to the person calling the agent. Both users call the same agent, the same version and the same tool.
- The news comes from a third-party MCP server, GNews at `https://mcp.gnews.io/`. It has two tools, `top_headlines(category, ...)` and `search(q, ...)`, and authenticates with one `X-Api-Key`. You cannot change it.

## 2. Why the agent and the third-party MCP server cannot enforce it

- **`allowed_tools` restricts the agent, not the user.** It is part of the agent definition, the same for every caller. And GNews's `top_headlines` covers all nine categories through an argument, so no list of tool names can separate business from sports.
- **The MCP server knows one key.** Every request with that key may read every category.
- **Agent system intructions are not a control.** The model may follow them most of the time, but no guarantees.

So the check sits between Foundry and GNews, where each request carries both the user's identity and the category being asked for.

## 3. Two places to enforce it

| | Track A: a wrapper you own ([08-05c-02](08-05c-02-wrapper-container-app.ipynb)) | Track B: the APIM gateway ([08-05c-03](08-05c-03-apim-passthrough.ipynb)) |
|---|---|---|
| Enforcement point | a FastMCP server, [`news-mcp-wrapper/server.py`](news-mcp-wrapper/server.py), on Container Apps | an inbound policy, [`infra/news-mcp-policy.xml`](infra/news-mcp-policy.xml), on the existing `apim-foundry-{suffix}` |
| Tools the agent sees | one per category plus `search_news`; each user sees only theirs | GNews's own `top_headlines` and `search`, the same for everyone |
| `tools/list` per user | filtered from the token's roles | not filtered: a policy at MCP scope must not read the response body |
| A request outside the user's rights | the tool is not listed, so the agent calls nothing and says the user's access does not cover it | the policy answers the call with `isError: true` and the denial text; Foundry then fails the request with HTTP 400 |
| What the enforcement point logs | every claim and decision, per call | APIM's standard request telemetry |
| Moving parts | an image, a registry, a Container Apps environment, a log workspace | one API, one policy, one backend and the GNews API key (stored as a named value) on an APIM instance you already run (`apim-foundry-{suffix}`, from 05-02); without one, an APIM instance as well |
| Pick it when | you want per-user tool lists, a record of who called what, or rules beyond a category check | a gateway already fronts your tools and a check at call time is enough |

Both tracks deny with the same text, which names what the user may read: "Your access covers: sports, science, health. Do not retry other categories."

## 4. How a request carries the user

### From a question to a tool call

A user does not name a category or a tool. They ask a question, and the model in the agent works out which category it is about and turns it into a tool call. The enforcement point never sees the question, only that tool call. For user B, who may read sports, science and health:

| User B asks | The model reads it as | Track A | Track B |
|---|---|---|---|
| "What's happening in sport today?" | sports headlines | calls `get_sports_headlines`; user B gets headlines | calls `top_headlines` with `category: sports`; the policy lets it through, and user B gets headlines |
| "How are the markets doing this morning?" | business headlines | calls nothing, because user B's agent has no business tool; the agent replies that user B's access does not cover business | calls `top_headlines` with `category: business`; the policy refuses the call, and user B gets the denial text |

These questions are examples. The notebooks' test cases ask directly, for example "Give me three science headlines", and on Track B the model then called `top_headlines` with `{"category": "science", "lang": "en", "max": 3, "page": 1}`.

On Track A the category is in the tool's name, and each tool calls GNews with its own category. On Track B it is in the `category` argument, and the policy reads it from the request body. A question about a topic rather than a category, such as "Any news on the Champions League final?", may make the model call `search` instead, which on Track B needs `News.Read.All`, so user B is refused even though the topic is sports. Either way the check applies to the call the model made, so a model that picks the wrong category is still checked against the user's roles.

### The request, step by step

![Track A: the wrapper as the enforcement point](../../docs/diagrams/08-05c-track-a-wrapper.png)

![Track B: the APIM policy as the enforcement point](../../docs/diagrams/08-05c-track-b-apim.png)

1. The user signs in to the public client app `news-desk-client-{suffix}` with a device code and gets a token for the agent blueprint's `access_agent` scope. Foundry adds that delegated scope to the blueprint when the endpoint gets the `AgentBlueprint` scheme (08-05c-01 Step 7). A token for it lets an app call this one agent as the signed-in user.
2. The client calls the agent's Responses endpoint, `{project endpoint}/agents/news-desk-agent/endpoint/protocols/openai?api-version=v1`, with that token. The endpoint's `AgentBlueprint` authorization scheme accepts it: the token is for this agent's blueprint, and Entra issued it to `news-desk-client`, the one app in the scheme's `allowed_clients`.
3. Agent Service exchanges that token with Entra ID, as the agent's identity, for a token for `api://news-mcp-{suffix}/News.Read` on behalf of the user. The `AgentOnBehalfOfUser` connection on the tool tells it to. [The on-behalf-of exchange](#the-on-behalf-of-exchange) below explains how.
4. Entra ID issues a delegated token that carries the user's app roles as they are at that moment.
5. Agent Service sends the MCP requests (`initialize`, `tools/list`, `tools/call`) to the enforcement point with that token.
6. The enforcement point validates the token and maps `roles` to categories. The token is a JWT, a set of claims signed by Entra ID: the enforcement point checks the signature with the tenant's published signing keys, then the issuer, tenant, audience and expiry, requires the `News.Read` scope, and reads the claims.
7. Allowed calls go to GNews with the `X-Api-Key` the enforcement point holds. The user's token goes no further.

### The on-behalf-of exchange

Steps 3 and 4 are the OAuth 2.0 on-behalf-of (OBO) flow. Agent Service trades the token the user sent for a new one addressed to the news server, still about the same user.

**Why Foundry exchanges the token**

- **The user's token is for the agent.** Its audience is the agent blueprint, so the news server would reject it, and a server that received it could replay it against the agent.
- **The agent's own token is the same for every caller.** An app-only token names the agent, not the user, so the server could not tell user A from user B.
- **The exchanged token names both.** It carries the user (`oid`, `roles`) and the agent acting for them (`azp`), and it is valid for one API and one scope.

**How it works**

Microsoft Entra Agent ID documents the protocol; this lab observed only the tokens at each end.

1. **Agent Service signs in as the agent.** An agent identity has no credential of its own. Agent Service presents the blueprint's federated credential, which Foundry provisions and which Foundry projects, agent code and the project managed identity never hold, and Entra issues a token for the agent identity ([agent identity in Foundry](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/agent-identity), [the Entra protocol](https://learn.microsoft.com/en-us/entra/agent-id/agent-autonomous-app-oauth-flow)).
2. **It sends the on-behalf-of request.** A `jwt-bearer` grant to Entra's token endpoint: the user's token as the `assertion`, the agent identity as the client with the token from step 1 as its `client_assertion`, and `api://news-mcp-{suffix}/News.Read` as the scope ([on-behalf-of with an agent identity](https://learn.microsoft.com/en-us/entra/agent-id/sidecar-local-development)).
3. **Entra checks** the user's token, and that the agent identity may act for users on `News.Read`: the four settings under [Consent](#consent) below. Conditional Access for an on-behalf-of request targets the user ([Conditional Access for agents](https://learn.microsoft.com/en-us/entra/identity/conditional-access/agent-id)).
4. **Entra issues the token** with the user's app role assignments, as they are now, in `roles`.
5. **Agent Service reuses the token** for later MCP requests until it expires, so a role change applies at the next exchange.

### The token the enforcement point receives

The exchanged token's column comes from the wrapper's log (08-05c-02 Step 5). The notebooks do not decode the user's token, so its column gives what the [access token claims reference](https://learn.microsoft.com/en-us/entra/identity-platform/access-token-claims-reference) defines for a token the user gets through `news-desk-client`.

| Claim | What it says | The user's token, to the agent (steps 1 and 2) | The exchanged token, to the enforcement point (steps 3 to 5) |
|---|---|---|---|
| `aud` | audience: the service the token is addressed to ("to") | the agent blueprint | the client id of `news-mcp-{suffix}` (a v2 token) |
| `scp` | scope: what the app may do there as the user ("allows") | `access_agent` | `News.Read` |
| `azp` (`appid` in a v1 token) | authorized party: the app that asked for the token ("from") | the client id of `news-desk-client-{suffix}` | the client id of `news-desk-agent`'s agent identity, not the blueprint's and not the client app's |
| `oid` | object id: the person ("who") | the user's object id | the user's object id, the same |
| `roles` | app roles: the person's rights on the service the token is addressed to | none: the lab assigns no app roles on the blueprint | the user's app roles on `news-mcp-{suffix}` |
| `idtyp` | identity type: a user's token or an app's own | not recorded | `user`: a delegated token |

Foundry's MCP client calls itself `ToolServer` and speaks protocol `2025-11-25`.

### Client app and resource app

**`news-desk-client` stands in for the real application.** The lab has no app UI, so the notebook plays that part. The notebooks' sign-in cells call `checks.user_credential(TENANT_ID, CLIENT_APP_ID, device_code=True)`, which becomes `DeviceCodeCredential(client_id=...)` in [`news_mcp_checks.py`](news_mcp_checks.py). At that moment the notebook is signing the user in *as* `news-desk-client`. In production it could be a news-desk web app, a Teams app or a mobile app.

`news-mcp` isn't something anyone signs into. It is Entra's record of the news service and its permission levels.

#### Every token names a "from" and a "to"

A token Entra issues works like a ticket, and the table above says what each claim on it means. Two claims name the ticket's two ends: `azp` is the app the person used to get it, the **client**, and `aud` is where the ticket is valid, the **resource**.

So Entra needs both ends registered: the app doing the asking, and the thing being asked. Those are the two apps.

| | In this lab |
|---|---|
| Client: the app the person opens | `news-desk-client` (the notebook, in place of a real app) |
| Resource: owns the data and the rules | `news-mcp` (rules = the `News.Read.*` roles) |
| The program that checks the ticket | the wrapper (Track A) or the APIM policy (Track B) |

`news-mcp` has no code of its own. It is an entry in Entra that says "a news API exists, these are its permission levels, and this is who holds which". The wrapper and the APIM policy are the programs that read tokens addressed to it. GNews never sees any of this.

#### Why two apps and not one

1. **Rights belong to what you access, not to what you access it with.** "User B may read sports" is a fact about the news service. Add a Teams bot later as a second client and user B is still sports-only there, with no changes, because the rule is stored on `news-mcp`.
2. **The news server only accepts tickets addressed to itself.** The wrapper and the policy check that `aud` is `news-mcp`'s id. Tokens can only be addressed to it because it exists as an app.
3. **The client app decides which apps may call the agent.** The agent endpoint's `allowed_clients` lists only `news-desk-client`. That is a rule about which front-end apps are allowed, and it is separate from the news permissions.

#### Where the agent fits: "client" and "resource" are roles in each hop

The request makes two hops, and the agent plays a different role in each:

```
 User B
   | signs in through news-desk-client (the notebook)
   v
 Hop 1: ticket from news-desk-client  ->  to the agent     scp: access_agent
   |
   | Foundry trades the ticket in (on-behalf-of)
   v
 Hop 2: ticket from the agent  ->  to news-mcp            scp: News.Read
                                                           roles: B's categories
   v
 wrapper / APIM checks the ticket, then calls GNews with the one API key
```

In hop 1, `news-desk-client` is the client and the agent is the resource. In hop 2, the agent is the client and `news-mcp` is the resource. "Resource" describes the role an app plays in one hop, not a kind of app, so a resource app is not a third kind of Entra object. The user (`oid`) stays the same on both tickets. Only "from" and "to" change. Entra fills in `roles` from `news-mcp`'s assignments at the moment of the trade.

#### App registration vs enterprise app

Each app is stored in Entra as two parts:

- **App registration**: the definition. For `news-mcp` it lists the permission levels that exist (`News.Read.All`, `News.Read.Sports`, ...). Think of it as the menu.
- **Enterprise app**: the app's copy in your tenant, where tenant-specific facts live. For `news-mcp` it records that user A holds All and user B holds sports, science and health. Think of it as the guest list.

The split exists because an app is defined once but can be used in many tenants. Slack's registration lives in Slack's tenant. Your tenant has an enterprise app for Slack that records who in your company is assigned to it and what your admin consented to. In this lab both parts are in the same tenant, so they look like duplicates. The next subsection lists what each part holds for each of the lab's apps, and where to find it in the portal.

### App registrations and enterprise apps

In Graph and the Entra APIs, the app registration is the **application object**: its app id, the scopes and app roles it exposes, the permissions it asks for, redirect URIs and credentials. The enterprise app is the **service principal**: who holds which app role, admin consent grants, sign-in logs.

- **`news-mcp-{suffix}`, the resource app.**
  - Its app registration defines the `News.Read` scope and the ten `News.Read.*` roles (the **App roles** and **Expose an API** pages).
  - Its enterprise app holds the role assignments: user A has `News.Read.All`, user B has sports, science and health. 08-05c-01 Step 9 posts them to that service principal (`/servicePrincipals/{id}/appRoleAssignedTo`).
  - So the assignments are under **Enterprise applications** > `news-mcp-{suffix}` > **Users and groups**, not on a user's **Assigned roles** page, which lists directory roles. The default Enterprise applications filter hides the app, because the notebook creates its service principal through Graph without the `WindowsAzureActiveDirectoryIntegratedApp` tag: clear the **Application type** filter, or open the app registration's **Managed application in local directory** link.
  - When Entra issues a token for `news-mcp-{suffix}`, it sets `aud` to the app registration's client id and fills `roles` from the enterprise app's assignments.
- **`news-desk-client-{suffix}`, the client app.**
  - Its app registration says what it is (a public client with no secret) and which permissions it asks for (`access_agent`, `News.Read`, Graph).
  - Its enterprise app holds the admin consent that lets users sign in without a consent prompt.
- **The agent.**
  - The blueprint has both objects: an application of type `agentIdentityBlueprint`, which defines `access_agent`, and its own service principal.
  - The agent identity is a service principal only. It has no app registration and no credential; the blueprint signs in for it. Its `News.Read` consent grant (08-05c-01 Step 8) sits on that service principal.

### Consent

The client app carries admin consent (`AllPrincipals` grants) for what the users sign in to: `access_agent` on the blueprint, `News.Read`, and Graph `User.Read`. For the downstream `News.Read` token in step 3, 08-05c-01 Step 8 sets four things:

1. **Preauthorization**: the resource app's `api.preAuthorizedApplications` names the blueprint and the `News.Read` scope.
2. **The blueprint's permissions**: `requiredResourceAccess` declares `News.Read`, and `inheritablePermissions` is meant to pass consented scopes to the blueprint's agent identities.
3. **Admin consent on the blueprint**: an `AllPrincipals` grant for `News.Read`.
4. **Admin consent on the agent identity**: the same grant on `news-desk-agent`'s own service principal.

### The authentication method this lab uses: Entra user delegation

The MCP guide ([08-05-00, section 6](../08-05-contoso-pmo-mcp/08-05-00-mcp-guide.md#6-mcp-authentication-methods-in-azure-ai-foundry)) lists the ways a Foundry agent authenticates to an MCP server. This lab uses **Microsoft Entra user delegation**: the connection asks Foundry to exchange the caller's token for one addressed to the server, on the caller's behalf.

```json
{
  "properties": {
    "category": "RemoteTool",
    "target": "https://apim-foundry-{suffix}.azure-api.net/news-mcp/mcp",
    "authType": "AgentOnBehalfOfUser",
    "scopes": ["api://news-mcp-{suffix}/News.Read"],
    "metadata": {"type": "generic_mcp"}
  }
}
```

The published ARM schema lists neither `AgentOnBehalfOfUser` nor `scopes`; ARM accepted this JSON at `2025-04-01-preview`. The agent's endpoint keeps the `AzureRbac` scheme beside `AgentBlueprint`. A Foundry token from `az login` is the signed-in user's own token, so keeping the scheme opens no way around the per-user rules. Foundry either exchanges that token on the user's behalf in the same way, and the enforcement point applies that user's roles, or fails the call before it obtains any token for the news server. Runs of this lab have shown both.

## 5. Implementation notes

- **FastMCP is pinned to `>=3.4,<4`** (3.4.11). FastMCP 4 is a new major release. In 3.4.11, `auth=` on a tool hides it from `tools/list` and makes a direct call fail as "Unknown tool", which a model reads as a server fault and retries around. The wrapper's middleware filters `tools/list` and answers any other call with the denial text; `auth=` stays on each tool as a second layer that calls the same predicate.
- **`MCP-Protocol-Version` is logged.** The wrapper records the version Foundry asks for at `initialize` and the header on each `tools/call`, so a change in Foundry's MCP client shows in the logs before it shows as a failure.
- **The wrapper runs stateless** (`stateless_http=True`), so it needs no session affinity across replicas, and keeps one replica warm to avoid a cold start inside Foundry's 100-second tool timeout.
- **The policy reads the request body** with `preserveContent: true` and never the response body. Allowed calls returned articles, so the body still reached GNews.
- **Both enforcement points require the `News.Read` scope.** Any app in the tenant that has a credential can get an app-only token for `news-mcp-{suffix}`: its enterprise app does not require assignment, so Entra issues the token, with no `scp` and no `roles`. Without the scope check both tracks accepted such a token and denied every call only because it held no role. The wrapper's `required_scopes` and the policy's `required-claims` on `scp` refuse it with 401, so only a delegated user token gets in.

## 6. Preview features

User delegation (`AgentOnBehalfOfUser`), the `AgentBlueprint` endpoint scheme and agent identities are in preview, behaviour may change.

## 7. Run the lab

**Prerequisites**

1. `uv sync` from the repository root, and the `.venv` kernel.
2. [05-02](../../05-foundry-project-pattern-setup/05-02-deploy-foundry-core-gateway/05-02-01-deploy-foundry-core-gateway.ipynb) deployed `aif-core-{suffix}`, `project-admin-{suffix}` and `apim-foundry-{suffix}`.
3. `az login` as a **Global Administrator** of a tenant you are allowed to change. 08-05c-01 registers two apps, creates a user, grants tenant-wide consent and may turn on the Temporary Access Pass method.
4. A free GNews key from [gnews.io](https://gnews.io) (100 requests a day) as `GNEWS_API_KEY` in `.env`. A full run makes about 7 GNews requests; denied calls make none.
5. A private browser window for user B's sign-ins.

**Notebooks, in order**

| Notebook | What it does |
|---|---|
| [08-05c-01](08-05c-01-identity-and-agent.ipynb) | Apps, user B and their pass, the agent and its endpoint, consent, app roles, the `news-mcp-apim` connection |
| [08-05c-02](08-05c-02-wrapper-container-app.ipynb) | Track A: deploys the wrapper, runs the matrix, and revokes `News.Read.Science` |
| [08-05c-03](08-05c-03-apim-passthrough.ipynb) | Track B: adds the MCP API to the gateway and runs the matrix |
| [08-05c-04](08-05c-04-reset-for-another-run.ipynb) | Optional, after 08-05c-03: gives user B the science role back, and a new pass if needed, for another run of 08-05c-02 and 08-05c-03 |

08-05c-03 does not need 08-05c-02. For Track B alone, run 08-05c-01 and then 08-05c-03; user B then keeps the science role and 08-05c-03 expects that. For both tracks, run 08-05c-02 and then 08-05c-03; user B then lacks the science role and 08-05c-03 expects a denial.

**Sign-ins.** Each notebook signs in both users with a device code: the cell prints a code, you enter it at the address it prints, and the cell stops if the token belongs to someone else.

| User | Account | Method |
|---|---|---|
| A | your admin account, the one `az login` uses | your usual password and multifactor method |
| B | `news-sports-desk@{your tenant's default domain}`, in `.env` as `NEWS_TEST_USER_UPN` | Temporary Access Pass, in `.env` as `NEWS_TEST_USER_TAP` |

For user B, use a private window, choose **Use another account**, type user B's account, and when Entra asks for a password choose **Other ways to sign in**, then **Temporary Access Pass**. `grep -E 'NEWS_TEST_USER_(UPN|TAP)' .env` shows both values. In this lab's runs Entra asked user B for nothing beyond the pass, not even security-info registration. The pass lasts 8 hours; re-run Step 5 of 08-05c-01 for a new one.

**`.env` keys.** You set `GNEWS_API_KEY`, and optionally `NEWS_MCP_RESOURCE_GROUP`, `NEWS_MCP_LOCATION` and `NEWS_TEST_USER_UPN` (see `.env.example`). 08-05c-01 writes `NEWS_MCP_RESOURCE_APP_ID`, `NEWS_MCP_RESOURCE_SP_ID`, `NEWS_DESK_CLIENT_APP_ID`, `NEWS_TEST_USER_UPN`, `NEWS_TEST_USER_ID`, `NEWS_TEST_USER_TAP`, `NEWS_AGENT_BLUEPRINT_CLIENT_ID`, `NEWS_CONNECTION_AUTH_TYPE` and `NEWS_CONNECTION_API_VERSION`; 08-05c-02 writes `NEWS_MCP_WRAPPER_URL`.

## 8. Teardown

The Cleanup section of [08-05c-01](08-05c-01-identity-and-agent.ipynb) holds the full teardown. Run it after 08-05c-02 and 08-05c-03: uncomment the cell, and it deletes, in order, the agent and its agent identity, the two connections, the MCP API, backend and named value on the gateway, the Track A resource group, user B, and both app registrations with their service principals, consent grants and role assignments. User B and the apps are purged from the Entra recycle bin, and the keys the notebooks wrote are removed from `.env`; `GNEWS_API_KEY` and the other keys you set yourself stay, except `NEWS_TEST_USER_UPN`. 08-05c-02 and 08-05c-03 each have a smaller cleanup cell for their own track.

The Temporary Access Pass method stays on: whether it is on is a tenant setting, and it may have been on before. The cleanup cell ends with a commented line that turns it off.
