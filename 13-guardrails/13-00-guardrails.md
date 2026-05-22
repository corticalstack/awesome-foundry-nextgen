# Bank customer-service guardrails: demo guide

A self-contained demo of three guardrail layers stacked on a single Foundry agent:
**Prompt Shields**, **PII pattern detection**, and a **custom blocklist** for internal
codenames and competitor names. Built around `contoso-bank-agent` in the admin Foundry
project, isolated to its own model deployment so other agents on the project are
unaffected.

## What gets demonstrated

| Layer | Mechanism | What the audience sees |
|---|---|---|
| Prompt injection / jailbreak | Foundry **Prompt Shields** (`Jailbreak`, `Indirect Attack`) | Prompts like `"Ignore all previous instructions"` and `"You are now DAN"` are intercepted before reaching the model. |
| PII detection | Custom Content Safety **regex blocklist** | Inputs containing SSNs, credit-card numbers, US phone numbers, emails, or dates of birth are blocked at the gateway. |
| Custom blocklist | Content Safety **string blocklist** | Internal codenames (`Project Falcon`, `SecureCore`) and competitor names (`Acme Bank`, `Globex Financial`, `Initech Banking`) are blocked. |

All three layers are wired into a **single custom RAI policy** (`bank-guardrails-policy`)
attached to a **dedicated deployment** (`gpt-4.1-mini-bank-guardrails`). The bank agent is
pinned to that deployment, so other agents on the project (`storytelling-agent`,
`code-interpreter-agent`) keep using `Microsoft.DefaultV2` and remain untouched.

```
┌──────────────────────────┐
│ contoso-bank-agent       │  ← agent definition (no defensive system prompt)
└─────────────┬────────────┘
              │  references by name
              ▼
┌──────────────────────────┐
│ gpt-4.1-mini-            │  ← dedicated model deployment
│ bank-guardrails          │
└─────────────┬────────────┘
              │  raiPolicyName
              ▼
┌──────────────────────────┐
│ bank-guardrails-policy   │  ← custom RAI policy (basePolicy: Microsoft.DefaultV2)
│  • Hate / Sex / Vio /    │
│    SelfHarm @ Medium     │
│  • Prompt Shields        │
│    (Jailbreak +          │
│     Indirect Attack)     │
│  • Protected Material    │
│    (Text + Code)         │
│  • Custom blocklists     │
└─────────────┬────────────┘
              │  references by name
              ▼
┌──────────────────────────┐
│ bank-demo-blocklist      │  ← jailbreak phrases + PII regex +
│                          │     codenames + competitors
└──────────────────────────┘
```

## Run order

Three notebooks plus this guide. Run them in sequence the first time; on repeat demos,
**only `13-03` needs re-running** because `13-01` and `13-02` are idempotent setup.

1. **[13-01-configure-bank-guardrails](13-01-configure-bank-guardrails.ipynb)** - creates
   the blocklist, the custom RAI policy, and the dedicated model deployment. ~2 min,
   most of which is waiting for the deployment to provision.
2. **[13-02-create-bank-agent](13-02-create-bank-agent.ipynb)** - creates `contoso-bank-agent`
   pinned to the guardrailed deployment. Smoke-tests one clean banking question. ~30 s.
3. **[13-03-demo-guardrails](13-03-demo-guardrails.ipynb)** - the demo runner. Drives 20
   categorised prompts and prints which guardrail fired on each. **This is the cell sequence
   to project on screen.** Run cell-by-cell so the audience can read each prompt before
   the result lands.

## Portal fallback

If any of the SDK calls in `13-01` fail (typically because the calling identity lacks
`Cognitive Services Contributor` on the Foundry account), do the same three things from
the Azure portal under `aif-core-6fe574`:

1. **Content filters → + Custom blocklist** - name `bank-demo-blocklist`. Add the entries
   listed in cell 4 of [13-01](13-01-configure-bank-guardrails.ipynb); flip the *regex*
   toggle on for the PII patterns.
2. **Content filters → + Create custom content filter** - name `bank-guardrails-policy`.
   Match the configuration in cell 6 of [13-01](13-01-configure-bank-guardrails.ipynb);
   reference `bank-demo-blocklist` for both prompt and completion.
3. **Deployments → + Deploy a model** - pick `gpt-4.1-mini` (`2025-04-14`),
   name `gpt-4.1-mini-bank-guardrails`, SKU `GlobalStandard` at 30K TPM, set the content
   filter to `bank-guardrails-policy` under Advanced.

Then continue with [13-02](13-02-create-bank-agent.ipynb).

## Demo talking points

The notebook output is structured so you can run cell-by-cell and narrate. A few framing
points that work for both technical and non-technical audiences:

**Opening (any audience)**
- "We've built a fictional bank's customer-service agent. Watch what happens when a real
  customer asks a normal question, then watch what happens when an attacker tries to
  exploit it."
- Run a clean banking question first. Audience sees a polished response. Establishes
  baseline.

**Prompt injection (technical hook)**
- "Prompt-injection is the most common AI-specific attack. The attacker tries to make
  the model forget its instructions. Foundry has a dedicated detector for this."
- Run a `"Ignore all previous instructions"` prompt. The block result is immediate;
  the agent never sees the manipulated prompt at all.
- Talking point: this is **input-side** filtering - happens before the model is called.
  Token costs are not incurred for blocked prompts.

**PII (compliance hook)**
- "Regulated industries - banking, healthcare, insurance - can't have unredacted PII
  flowing through models even by accident. We've added regex patterns for SSN, credit
  card, phone, email, and DOB."
- Run the `"My SSN is 123-45-6789"` prompt. Block is at the gateway, before model.
- Talking point: this is **layered with**, not instead of, the agent's own behaviour.
  Even if the agent's training started leaking, the gateway would still catch the
  outbound PII because the blocklist is bound to **both prompt and completion**.

**Custom blocklist (business hook)**
- "Generic guardrails can't know that 'Project Falcon' is your fraud-detection system,
  or that 'Acme Bank' is a competitor you don't want your assistant talking about. So
  Foundry lets you bring your own list."
- Run the `"Tell me everything about Project Falcon"` and `"How do you compare to Acme
  Bank"` prompts. Both blocked.

**Closing**
- The scorecard cell at the end shows pass rate per category. Easy concrete metric:
  "All 15 attacks blocked, all 5 legitimate questions answered."
- Highlight that the agent's system prompt has **no** defensive language - the agent
  itself is naive. The guardrails are the security perimeter.

## Cleanup

When the demo is done, the deployment continues to consume a slice of `gpt-4.1` quota.
Tear it down via the cleanup cell at the bottom of
[13-01](13-01-configure-bank-guardrails.ipynb) (uncomment the three `arm("DELETE", ...)`
lines and run). That removes the deployment, the policy, and the blocklist in the
correct order. The agent itself can be deleted via the agent SDK or left in place -
it'll simply 404 on its model when next called.

## Things this demo intentionally does NOT cover

- **Output-side hallucination detection / groundedness** - Foundry has groundedness
  detection but it requires a reference document, which doesn't fit this stateless
  customer-service scenario.
- **Custom Content Safety categories** - these need labelled training data and a
  separate provisioning flow; out of scope for a 5-minute demo.
- **Per-user / per-session adaptive guardrails** - the policy is per-deployment and
  applies uniformly. If the audience asks about per-user policies, the answer is "use
  multiple deployments + route by user identity" or "do that filtering in your
  application layer".

---

[Next: Configure bank guardrails →](13-01-configure-bank-guardrails.ipynb)
