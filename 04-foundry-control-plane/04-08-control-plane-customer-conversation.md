# Control Plane customer conversation

Picture this.

Developers can build an AI agent in minutes. Call centre support, document routing, customer queries. Things are running. The business wants more.

So a company can find itself with ten agents in production, across multiple hyperscalers including Azure and others, before anyone's really thought about what comes next. The difficult part is understanding what those agents are actually doing, how they're performing, and whether they're staying within company policies.


Then one day, one of those agents retrieves a document through a tool call. Buried inside that document is a hidden instruction. The agent doesn't know it's been manipulated. It starts weaving customer names and transaction history into its responses. No alarms. No alerts.

Nobody notices for three days.

That scenario plays out. Not often, but it does. And it's exactly the conversation that starts when someone walks up to my booth and says: "we're scaling up our agent programme - what should we be thinking about?"

And here's the thing - developers aren't just building one agent on one platform. They're building fleets, across clouds. AWS, Azure, third-party tools, different frameworks. Which is exactly why having one place to manage all of that matters.

Foundry Control Plane is what I point them to. It spans both the Build and Operate views in the Foundry UI, bringing controls, observability, security, and governance into one place - so whether you're creating an agent or monitoring it in production, you're not switching between different portals to do it.

Worth saying upfront: Foundry Control Plane is primarily a developer tool. That's the persona it's built for. There's a companion product called Agent 365, which takes the infrastructure Microsoft already uses to manage users and devices - Entra, Defender, Intune, Purview - and extends it to agents. That one is aimed more at IT and security admins. The two work together, but if you're a developer, Foundry Control Plane is where you live.

Let me take you through each one.

---

## Controls

When people hear "guardrails on AI agents", they think: filter the prompt, filter the response. That's been standard for a while.

What's new in Azure AI Foundry is that controls now extend to tool calls and tool responses. That matters a lot. In the scenario I just described, the attack didn't come through the user's message. It came through a document the agent retrieved. External content, untrusted source, hidden instruction. Foundry can detect and block that kind of indirect prompt injection at the tool response level, before it changes how the agent behaves.

That's just one piece of it. Foundry supports a full range of controls - sensitive data detection to stop PII leaving the system, groundedness to keep the agent from producing things that aren't backed by its data, task adherence to catch it going off script, and protected materials detection for anything touching copyright. The goal across all of them is the same: agents that stay focused, produce accurate results, and operate within the boundaries you've defined.

You build the guardrail configuration, pick the intervention points, and once you're happy with it, you apply it across all your agents in one go.

> Show: guardrails configuration UI - the list of control types and the intervention point selector

---

## Observability

One thing I end up explaining more than I expected.

With a traditional application, a human can review what happened. With agents, if you require a human to sign off on every step, you've already defeated the purpose. The whole point is that the agent handles a complex task, runs autonomously, and gets it done. You can't watch every move.

So what you do instead is build continuous evaluation into the system. In Foundry, you can run evaluators against your real production traffic - not a synthetic test suite you ran before you shipped, but actual runs from actual users. You set a threshold, and when something drops below it, you get an alert. You're not watching everything. You're watching for when something's wrong.

There's also OpenTelemetry-based tracing, so when something does go wrong, you can walk it back step by step - from the user prompt, through the model inference, to the specific tool call that caused the problem.

And I always bring up cost, because it catches people off guard. You can monitor what individual agents are spending, per agent, across your entire fleet. Agents can burn through tokens fast if nobody's paying attention.

> Show: operate dashboard - the cost view and an example of continuous eval alerts

---

## Security

The moment you publish an agent in Foundry, it gets a Microsoft Entra ID. Not a log entry, not a tag - an actual identity, both an application ID and an object ID.

Why does that matter? A few reasons.

First, access control. Because the agent has an identity, you can manage what it's allowed to do using exactly the same patterns you already use for users and service accounts. Assign it permissions, scope what data it can reach, apply conditional access policies. The agent becomes something IT can actually govern, not just something a developer deployed somewhere that nobody else can see.

Second, ownership. The Entra ID ties the agent to a named owner - a specific person or team who is accountable for it. As you scale to dozens or hundreds of agents, that matters a lot. When something goes wrong at 2am, you're not asking "which team built this and who do we call?" - the answer is already in the identity record.

And third, lineage. That identity follows the agent through its entire lifecycle. Who built it, when it was published, what it has access to, how it's been used. Three months from now, if an agent starts behaving unexpectedly, you have a starting point for the investigation.

> Show: navigate to the Azure portal and find the published agent - point out the Entra application ID and object ID. The key message: this agent now exists as a registered identity in the same directory as your users and devices, and it happened automatically at publish time - no extra steps required.

Defender extends its protection to agents built in Foundry. That means AI security posture management - visibility into your agents across the fleet, recommendations on where you have gaps, and attack path analysis to understand how risks connect. And it brings new threat detections built specifically for AI. A jailbreak attempt doesn't just get blocked. It shows up as a security alert in Defender, with full context for investigation, right alongside everything else your security team is already watching.

On the compliance side, Purview takes the agent interactions from Foundry and makes them available for audit - so your compliance team has a trail of what agents did and when. Security admins can also define org-wide AI content safety policies that apply natively inside Foundry. Things like: every agent in this subscription must have prompt injection protection switched on. Developers can see when their agents fall outside those policies and fix it directly, without the compliance team needing to chase them.

There's a compliance view inside Foundry Operate that pulls all of this together - a birds-eye picture of which guardrails are in place across your fleet, which aren't, and where your policy gaps are. And you can act on it directly from there.

> Show: the create policy screen in Foundry Operate compliance view

So what exactly is a policy here, and why does it matter?

Think of it this way. Controls are what each developer configures on their own agent - they decide what to turn on, what to leave off. Policies are different. A policy is an organisation-level decision that says: regardless of who built the agent, regardless of which team owns it, these controls must be active. It's the difference between making something available and actually mandating it.

In practice, a security admin or a lead architect comes into this screen and says: in our organisation, every agent in this subscription must have indirect prompt injection protection and spotlighting switched on. That becomes a policy. Foundry then scans every agent against it. The ones that don't meet the standard get flagged - you can see them in the compliance view and fix them directly from there. And if a new agent gets deployed without the required controls, it shows up as non-compliant immediately. No manual audit. No waiting for a quarterly review.

The reason this is important is that at scale, you cannot rely on every developer making the right choices every time. Policies give the organisation a way to set a baseline and enforce it - the same way you'd use device compliance policies in Intune to ensure every laptop meets your security standard before it gets access to company resources. Same principle, applied to agents.

---

## Fleet-wide operations

When you have ten agents, you can manage them by hand. When you have a hundred - and some teams already do - you need a different operating model.

The Operate view in Foundry is essentially a to-do list for your agent fleet. Jailbreak attempts that were detected and blocked. Evaluation scores that dropped below your threshold. Policy compliance gaps you didn't know existed. All of it in one place, across all your projects. You can sort by error rate, by token cost, by how much each agent is actually being used.

And when something needs fixing, you go straight from the alert into the build experience for that agent. Fix the prompt, update the guardrail, adjust the tool. No context switching. No rebuilding your understanding from scratch.

You can also bring in agents that weren't built in Foundry - LangChain, LangGraph, something running on AWS - by routing their traffic through the AI Gateway. Once they're in, they appear in the same fleet view. Same controls, same observability. One place.

> Show: fleet overview and the assets tab - agent list with external agents registered via AI Gateway

---

## Close

So when someone walks up and asks me whether they should be worried about scaling agents, my honest answer is: yes.

Not in a "this is broken" way. More in a "you need to be paying attention" way.

The teams I see doing this well aren't necessarily the ones building the most agents. They're the ones who can actually trust what their agents are doing. And when something goes wrong - because at some point, something will - they can find it fast.

That's the job Foundry Control Plane is built for.

---

[Next: Foundry Control Plane cheat sheet →](04-09-foundry-control-plane-cheat-sheet.md)