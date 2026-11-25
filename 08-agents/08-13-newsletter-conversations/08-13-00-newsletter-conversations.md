# Long-running conversations for a newsletter

A reader of a daily newsletter starts a chat about one edition and comes back to it days or weeks
later. This lab keeps that chat in Foundry: one conversation per edition, found again by the edition
id in its metadata and resumed by its conversation id. The application stores no chat history and no
conversation ids.

The lab runs the flow twice: on `newsletter-agent`, a prompt agent with no tools (08-13-01 and
08-13-02), and on `newsletter-hosted-agent`, a hosted agent that runs its own code (08-13-03). The
newsletter is the fictional Contoso Daily Brief, five editions kept in
[`assets/contoso-daily-brief-dataset/`](../../assets/contoso-daily-brief-dataset/).

## What the lab shows

| Need | Call | Where |
|---|---|---|
| Put an edition's articles in the chat | `conversations.create(items=[...])`: one `developer` message contains the edition, each article with its id | 08-13-01 Step 4 |
| Tie the chat to an edition | `conversations.create(metadata={"edition_id": ...})` | 08-13-01 Step 4 |
| Ask about the edition | `responses.create(conversation=<id>, input=...)` | 08-13-01 Step 5 |
| List the chats | `GET {agent endpoint}/conversations` | 08-13-02 Step 2 |
| Open the chat for one edition | match `edition_id` in the metadata of the listed rows | 08-13-02 Step 3 |
| Show the earlier messages | `conversations.items.list(<id>)` | 08-13-02 Step 4 |
| Continue the chat | `responses.create(conversation=<id>, input=...)` | 08-13-02 Step 5 |
| Record the last activity | `conversations.update(<id>, metadata=...)` | 08-13-02 Step 6 |

All calls go to the agent's own endpoint, `{project endpoint}/agents/{agent name}/endpoint/protocols/openai`,
through `client.get_openai_client(agent_name=...)`.

## Prompt agent and hosted agent

The conversation calls in the table are the same for both. 08-13-03 repeats them against the hosted
agent. Before them it runs two steps that a prompt agent does not need: it deploys the agent's code
(Step 2) and grants the agent's identity the Foundry User role on the project (Step 3).

| | Prompt agent (08-13-01, 08-13-02) | Hosted agent (08-13-03) |
|---|---|---|
| What runs | Foundry runs the model with the agent's instructions | Your code, [`newsletter-hosted-agent/main.py`](newsletter-hosted-agent/main.py), in a sandbox Foundry starts per session |
| Created with | `create_version` and a `PromptAgentDefinition` | `create_version_from_code` and a zip of the source, as in [08-12](../08-12-hosted-agent-sessions/08-12-00-hosted-agent-sessions.md) |
| Access to the model | Nothing to grant | The agent runs as its own identity, which needs Foundry User on the project |
| Who reads the history for a turn | Foundry | The agent's code. Agent Framework's `ResponsesHostServer` rebuilds the stored conversation for each request |
| First call | Answers at once | Starts a sandbox first, so it is slower and can need a retry |

**Where the history is kept.** For both agent types, Foundry stores the conversation in its own
conversation store. The hosted agent's sandbox, the container its code runs in, does not keep it.
The history is therefore still there after the sandbox stops on its idle timeout, and the agent's
code reads it from Foundry on the next call.

**Which hosted agents this applies to.** Those that serve the Responses protocol, as this lab's
agent does. Note a hosted agent can serve the Invocations protocol instead, in which case Foundry stores no
conversation history, and the agent's code has to keep it.

## How long a conversation lasts

- **Basic setup** (what this repo's projects use): Foundry deletes conversations, their items and
  stored responses after 60 days. An expired conversation returns 404 and cannot be recovered.
- **Standard setup**: the data is in the `run-state-v1` container of your own Cosmos DB account. The
  default TTL is also 60 days, and you can change it.
- The documentation does not say whether the 60 days count from creation or from the last activity.

Source: [How long is conversation data stored?](https://learn.microsoft.com/en-us/azure/foundry/agents/faq)

## Limits to design around

Each entry says what the limit is, what it means for a newsletter application, and what the lab does
about it.

1. **No filter by metadata**
   - **Limit:** the list call cannot be asked for "only conversations where `edition_id` is
     `ed-001`". It returns conversations in creation order, at most 100 per call, and each row has
     only `id`, `created_at` and `metadata`.
   - **Effect:** to find the chat for an edition, the application fetches the list and checks each
     row's metadata itself. Past 100 conversations it has to fetch page after page.
   - **Lab:** one list call, then a match in Python (08-13-02 Step 3). The lab has five
     conversations, so it never pages.

2. **No last-activity time**
   - **Limit:** a conversation records when it was created and nothing about when it was last used.
     In this lab's runs the items inside it came back without timestamps too.
   - **Effect:** the API alone cannot sort chats by "most recently used" or show "last opened".
   - **Lab:** writes today's date into the metadata as `last_resumed` when it resumes a conversation
     (08-13-02 Step 6). The application maintains that value; Foundry never updates it.

3. **Metadata size**
   - **Limit:** at most 16 key-value pairs per conversation, with keys up to 64 characters and
     values up to 512.
   - **Effect:** it fits ids, dates and a title, not article text.
   - **Lab:** uses three pairs, four after a resume.

4. **No `conversations.list()` in the Python `openai` SDK**
   - **Limit:** the REST API can list conversations, but the Python package (3.24.0 here) has no
     method for it. Other languages were not checked.
   - **Effect:** `client.conversations.list()` does not exist.
   - **Lab:** sends the GET request itself through the same client, which reuses its sign-in and
     address (the `list_conversations` function in each notebook).

5. **A hosted agent's code decides how much history the model sees**
   - **Limit:** this applies to hosted agents only. Foundry stores the whole conversation, but the
     agent's code fetches the history for each question and chooses how much.
   - **Effect:** [Microsoft's hand-written sample](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agent-contract#handler-examples)
     fetches the latest 20 items. In a longer chat the first item, the edition, would no longer be
     fetched, and the model would answer without it.
   - **Lab:** uses Agent Framework's `ResponsesHostServer`, which passes the stored conversation,
     and the answer cited the edition (08-13-03 Step 5). A very long chat was not tested.

6. **Agent endpoint and project endpoint keep separate conversations**
   - **Limit:** conversations can be created at two addresses, one for the project
     (`{project endpoint}/openai/v1/conversations`) and one per agent. A conversation exists only at
     the address that created it. Tested on 2026-11-25 as one signed-in administrator, on a prompt
     agent and on a hosted agent: a conversation created at one address returned 404 at the other
     and was missing from its list, in both directions. On the prompt agent, a question that named
     the conversation at the other address failed with 400 `conversation_not_found`. This is tested
     behaviour, not documented behaviour.
   - **Effect:** create, list, read and resume must all use the same address. A script that reads
     the project address will not see chats made through an agent's address.
   - **Lab:** uses the agent address throughout.

7. **One user**
   - **Limit:** the lab signs in as one identity, so every conversation belongs to that identity.
   - **Effect:** the lab is no evidence that one user cannot see another's chats. Microsoft
     documents that they cannot, on a page written for hosted agents
     ([Isolate hosted agent sessions per user](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/isolate-sessions-per-user)).
   - **Lab:** does not test it. Test with two users.

## The dataset

`assets/contoso-daily-brief-dataset/editions/` contains `ed-001.json` to `ed-005.json`, the editions of
16 to 20 November 2026. Companies and events are invented. Each edition has four articles:

```json
{
  "edition_id": "ed-001",
  "title": "Northwind buys into a port, Relecloud heats homes",
  "published": "2026-11-16",
  "articles": [
    {"article_id": "ed-001-01", "category": "Business", "headline": "...", "summary": "..."}
  ]
}
```

## Run the lab

**Prerequisites**

1. `uv sync` from the repository root, and the `.venv` kernel.
2. The 05 labs deployed the Team Alpha project: `ALPHA_FOUNDRY_PROJECT_ENDPOINT`,
   `ALPHA_FOUNDRY_CORE_CONNECTION` and `CHAT_MODEL` are in `.env`.
3. `az login`, with the Foundry User role on the project.
4. For 08-13-03 only: `ALPHA_FOUNDRY_ACCOUNT` in `.env`, Foundry Project Manager on the project to
   deploy the agent, and Owner or User Access Administrator on the spoke resource group to grant the
   agent identity its role.

**Notebooks**

| Notebook | What it does |
|---|---|
| [08-13-01](08-13-01-start-edition-conversations.ipynb) | Creates the prompt agent, loads the editions, creates one conversation per edition and asks a first question in each |
| [08-13-02](08-13-02-return-and-resume.ipynb) | From a fresh kernel: lists the conversations, finds the one for `ed-001`, reads its history back, resumes it and updates its metadata |
| [08-13-03](08-13-03-hosted-agent-conversations.ipynb) | Deploys the hosted agent from source, grants its identity Foundry User, then creates, finds, reads back and resumes a conversation on it |

Run 08-13-01 before 08-13-02. 08-13-03 stands alone.

Run 08-13-02 or 08-13-03 again on any later day within the 60 days: the conversation still answers
from its history. Both 08-13-01 and 08-13-03 skip editions that already have a conversation, so they
are safe to re-run.



## Resources

- [Build with runtime components: conversations and conversation items](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/runtime-components)
- [Foundry Agent Service FAQ](https://learn.microsoft.com/en-us/azure/foundry/agents/faq)
- [Foundry project REST reference: Conversations](https://learn.microsoft.com/en-us/rest/api/microsoft-foundry/aiproject)
- [Hosted agents: sessions, conversations and the state store](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents)
- [Agent Framework: Foundry hosted agents](https://learn.microsoft.com/en-us/agent-framework/hosting/foundry-hosted-agent)
- [Baseline Microsoft Foundry chat reference architecture](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/architecture/baseline-microsoft-foundry-chat)

---

[Next: Start a conversation for each newsletter edition →](08-13-01-start-edition-conversations.ipynb)
