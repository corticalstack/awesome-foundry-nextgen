# Migrating from GPT-4o to the GPT-5 family (GPT-5 / GPT-5.1): research notes

> Working research notes, not finished lab content. Compiled June 2026 from primary
> sources (OpenAI developer docs, OpenAI cookbook, Azure AI Foundry / Azure OpenAI
> Learn docs) plus first-party announcements, intended as the basis for a future
> Azure AI Foundry migration lab in this repo.
>
> Volatility warning: by June 2026 the live OpenAI/Azure catalogs already extend past
> GPT-5.1 to GPT-5.2 through GPT-5.5. Model IDs, prices, GA-vs-preview status, and
> retirement dates move fast. Treat every date, price, and "GA" claim as
> verify-at-build-time. The named migration targets here are GPT-5 (2025-08-07) and
> GPT-5.1 (2025-11-13).

---

## 0. TL;DR - the migration is a model-class change, not a version bump

GPT-4o is a non-reasoning chat model. The GPT-5 API flagships are reasoning models.
Almost every migration headache flows from that single shift, plus OpenAI moving the
"recommended" surface from Chat Completions / Assistants to the Responses API. The six
challenges that bite hardest:

1. **Silent request breakage.** A naive swap fails fast: reasoning models reject
   `temperature`, `top_p`, `presence_penalty`, `frequency_penalty`, `logprobs`,
   `logit_bias`, `n`, and `max_tokens` with HTTP 400. `max_tokens` becomes
   `max_completion_tokens` (Chat Completions) or `max_output_tokens` (Responses).
2. **Hidden reasoning tokens reshape cost, latency, and throughput.** Reasoning tokens
   are billed as output tokens, are invisible, count against your `max_*_tokens`
   budget and against TPM rate limits, and can multiply effective output cost and
   latency by 5x to 20x depending on `reasoning_effort`.
3. **The empty-answer trap.** Because reasoning shares the output budget, too small a
   `max_*_tokens` can burn the entire budget on hidden reasoning and return empty
   content (`finish_reason: "length"` / status `incomplete`) while still billing you.
4. **API-surface migration.** OpenAI recommends Responses (not Chat Completions) for
   GPT-5, and the Assistants API is being retired (2026-08-26). Responses is stateful,
   reuses reasoning across turns, and has a different request/response/streaming shape.
5. **Prompts regress.** 4o-era prompts with chain-of-thought prose, "be thorough"
   padding, and buried contradictions actively hurt GPT-5, which is literal and wastes
   reasoning tokens reconciling conflicts. Prompts need rework, not a copy-paste.
6. **Lineup and lifecycle decisions.** You must choose the right GPT-5 variant
   (reasoning vs non-reasoning, full vs mini vs nano) and beat Azure's retirement
   clock for gpt-4o.

The clean default for a latency- and cost-sensitive 4o workload: **gpt-5.1 with
`reasoning_effort: "none"`** (OpenAI's stated natural fit for prior GPT-4.1/4o
low-latency use), on the Responses API, with caching enabled and `max_output_tokens`
sized with headroom. Dial reasoning up only on routes where quality demands it.

---

## 1. The mental-model shift

| Dimension | GPT-4o | GPT-5 / GPT-5.1 (reasoning) |
|---|---|---|
| Model class | Non-reasoning chat | Reasoning (thinks before answering) |
| Recommended API | Chat Completions / Assistants | **Responses** (Chat Completions still works) |
| Hidden reasoning tokens | None | Yes - billed as output, invisible, in context |
| Sampling controls | `temperature`, `top_p`, penalties | Removed; replaced by `reasoning_effort` + `verbosity` |
| Output cap param | `max_tokens` | `max_completion_tokens` / `max_output_tokens` |
| Instruction role | `system` | `developer` (`system` auto-mapped/accepted) |
| Context window | 128k total, 16,384 max output | 272k input / 128k output / 400k total |
| State | Stateless | Stateful (`previous_response_id`, `store`) |
| Audio modality | Via 4o-audio / Realtime SKUs | None (text + image in, text out) |
| Prompting | Benefits from explicit CoT, hand-holding | Literal; CoT and padding hurt |

---

## 2. API-surface migration: Chat Completions vs Assistants vs Responses

### The three surfaces

| Surface | Endpoint | Status (June 2026) |
|---|---|---|
| Chat Completions | `/v1/chat/completions` | Supported, works with GPT-5; "legacy" for new builds |
| Assistants (beta) | `/v1/assistants`, `/threads`, `/runs` | **Deprecated 2025-08-26, retires 2026-08-26** |
| Responses | `/v1/responses` | Recommended default, especially for reasoning/GPT-5 |

### Why Responses for GPT-5

- **Reasoning-item persistence.** Chat Completions is stateless and discards reasoning
  items between turns, causing "slightly degraded model performance and greater
  reasoning token usage in complex agentic cases involving many function calls."
  Responses preserves and reuses them via `previous_response_id`, by re-including
  output items as input, or via `store: true`.
- **Measured upside.** OpenAI cites roughly +3% on SWE-bench from reasoning-item reuse
  alone (cookbook / migration guide) and a separate +5% on TAUBench (Responses blog);
  cache utilization rose from ~40% to ~80% switching Completions to Responses.
- **Built-in server-side tools** (web search, file search, code interpreter, computer
  use, image gen, remote MCP), an item-based `input`/`output` model, a top-level
  `instructions` field, and **encrypted reasoning content** (`include:
  ["reasoning.encrypted_content"]`) for zero-data-retention orgs that run `store: false`.

### Porting `chat.completions.create` to `responses.create`

```python
# Chat Completions
client.chat.completions.create(
    model="gpt-5",
    messages=[
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hello!"},
    ],
)

# Responses
client.responses.create(
    model="gpt-5",
    instructions="You are helpful.",   # replaces the system message
    input="Hello!",                    # string OR an array of typed items
)
```

- Read output: `completion.choices[0].message.content` becomes `response.output_text`.
- Structured output: `response_format=...` becomes nested `text={"format": {...}}`.
- Tools: Chat Completions uses externally-tagged `{"type":"function","function":{...}}`;
  Responses flattens to `{"type":"function","name":...,"parameters":...}` with
  `strict` defaulting to **true** (lax schemas that passed before can now error). Tool
  calls and results are separate Items correlated by `call_id`.
- Streaming: Chat Completions emits data-only SSE chunks (`choices[].delta.content`,
  `[DONE]` sentinel). Responses emits typed semantic events
  (`response.output_text.delta`, `response.function_call_arguments.delta`,
  `response.completed`, etc.) - parsers must switch from chunk-diffing to event dispatch.
- `n` (multiple generations) is removed in Responses.
- `store` defaults to **true** in Responses (server-side persistence enabling
  `previous_response_id`); `store: false` is forced for ZDR orgs.

### Assistants to Responses concept map

| Assistants | Responses / Conversations |
|---|---|
| Assistants | Prompts (versioned model + instructions + tools) |
| Threads | Conversations |
| Runs | Responses |
| Run steps | Items |
| `file_search` + vector stores | `file_search` built-in tool |

---

## 3. Reasoning controls: the token / latency engine

### `reasoning_effort` (Chat Completions) / `reasoning.effort` (Responses)

| Value | Behavior | gpt-5 | gpt-5.1 |
|---|---|---|---|
| `none` | Zero reasoning tokens; behaves like 4o/4.1 | not supported | **default** |
| `minimal` | Very few (nonzero) reasoning tokens | **default** | not supported |
| `low` / `medium` / `high` | Increasing thinking depth, tokens, latency | yes | yes |

- **gpt-5 default = `medium`**; supports `minimal/low/medium/high` (no `none`).
- **gpt-5.1 default = `none`**; supports `none/low/medium/high` (no `minimal`).
- `none` vs `minimal`: `none` forces zero reasoning tokens (true non-reasoning,
  4o-like, still supports hosted web/file search and tool calling). `minimal` can emit
  a few. Note: with `minimal`, **parallel tool calls are disabled**.
- gpt-5-pro is fixed at `high`. gpt-5-codex does not support `minimal`. Later codex
  models add `xhigh` (out of scope for the 5/5.1 target).

### GPT-5.1 adaptive reasoning

GPT-5.1 dynamically calibrates thinking to task difficulty: fewer tokens on easy
inputs, more persistence on hard ones. This is calibration **within** a chosen effort
level (improves token efficiency at low/medium/high), distinct from the `none` switch
that turns reasoning off entirely. OpenAI claims GPT-5.1 uses about half the tokens of
comparable competitors at similar/better quality, and is much faster on easy tasks even
at high effort.

### `verbosity` (low / medium / high, default medium)

Controls the length of the **final visible answer**, not the amount of thinking.
Independent of `reasoning_effort`. In-prompt natural-language instructions override it
("a 5-paragraph essay" wins). Excess verbosity is a common 4o-to-5 regression; set
`verbosity: "low"` for terse outputs, with scoped overrides where you want detail.

### How reasoning tokens are billed and surfaced

- Generated before the visible answer, **billed as output tokens**, never returned
  (only opt-in `reasoning.summary` summaries; raw chain-of-thought is not extractable;
  gpt-5 series does not support `concise` summaries, only `auto`/`detailed`).
- Usage fields: `output_tokens_details.reasoning_tokens` (Responses) /
  `completion_tokens_details.reasoning_tokens` (Chat Completions). Both roll into the
  total output/completion token count.
- Real Azure example: a default gpt-5 call billed `completion_tokens: 2919` of which
  `reasoning_tokens: 1792` (~61% invisible). A tool-call turn billed 240 output tokens
  with 192 reasoning (~80% hidden).

### The empty-output gotcha (high priority for the lab)

`max_output_tokens` / `max_completion_tokens` caps **reasoning + visible output
combined**. If reasoning exhausts the cap first you get a truncated or empty result
(`status: incomplete`, `incomplete_details.reason: "max_output_tokens"`, or
`finish_reason: "length"`) and still pay for input + reasoning tokens. OpenAI guidance:
**reserve at least 25,000 tokens for reasoning and output** while experimenting.

### Latency

- Time-to-first-token stays roughly flat (~250-350 ms) across effort levels; reasoning
  shows up as **total completion latency** (slow inter-token / "thinking pause"), not a
  slow start. So streaming UIs feel pauses, not a delayed open.
- Indicative third-party benchmark (single harness, treat as relative not absolute):
  gpt-5 total time scaled ~5.6x from minimal (~7s) to high (~39s); **gpt-5.1's adaptive
  reasoning flattened the curve to ~1.2x** (~12 to ~15s). gpt-5-nano scaled ~8x.
- Mitigations: lower effort, `minimal` (gpt-5) / `none` (gpt-5.1), stream, use
  mini/nano, or use a non-reasoning chat variant.

### The naive-swap step change

Pointing 4o code at gpt-5 at default `medium` effort changes three things at once:
output tokens/cost jump (hidden reasoning), total latency jumps (thinking pauses), and
calls can break or return empty (rejected params, budget consumed by reasoning).
Preferred low-friction path: gpt-5 `minimal` or, better, **gpt-5.1 `none`**, then raise
effort only where quality needs it.

---

## 4. Breaking parameter and shape incompatibilities

### Rejected on reasoning models (hard HTTP 400)

`temperature`, `top_p`, `presence_penalty`, `frequency_penalty`, `logprobs`,
`top_logprobs`, `logit_bias`, `n`, and `max_tokens` are unsupported. Example:

```json
{"error":{"message":"Unsupported parameter: 'temperature' is not supported with this model.",
"type":"invalid_request_error","param":"temperature","code":"unsupported_parameter"}}
```

```json
{"error":{"message":"Unsupported parameter: 'max_tokens' is not supported with this model. Use 'max_completion_tokens' instead.",
"type":"invalid_request_error","param":"max_tokens","code":"unsupported_parameter"}}
```

The server internally pins `temperature` and `top_p` to 1.0. Replacement steering is
`reasoning_effort` + `verbosity`. `max_tokens` was first deprecated for reasoning models
with the o1 series (Dec 2024). A common trap: older SDK wrappers inject `max_tokens`
automatically, so the 400 fires even when you never set it.

### Reasoning vs non-reasoning split (critical nuance)

The non-reasoning **`gpt-5-chat`** variant still accepts `temperature` / `top_p` like
4o. But **`gpt-5.1-chat` became a reasoning model** and therefore drops `temperature`
and friends. So "migrate gpt-5-chat to gpt-5.1-chat" silently breaks param-compatible
code. Whether sampling params break depends entirely on the exact SKU you target.

### Other shape changes

- **System role**: latest reasoning models accept `system` and auto-map it to
  `developer`; do not send both in one request. (o-series treats `system` as
  `developer`.) Markdown can be suppressed by default - prepend `Formatting re-enabled`
  to restore code-block formatting if needed.
- **Structured Outputs**: 4o JSON mode (`response_format={"type":"json_object"}`) still
  works and is not deprecated. Schema-enforced Structured Outputs: Chat Completions uses
  `response_format.json_schema` (with `strict: true`, `additionalProperties: false`,
  all props required); Responses uses `text.format`. All GPT-5 reasoning models support
  Structured Outputs; migrating from `gpt-4o-2024-08-06`+ is largely compatible apart
  from the Responses rename.
- **Function / tool calling**: standard tools, `tool_choice`, `parallel_tool_calls`
  carry over (but parallel calls are disabled at `reasoning_effort: minimal`). New GPT-5
  capabilities: custom / freeform tools (`type: "custom"`, raw text payloads),
  CFG-constrained tools via Lark/Regex grammars, `allowed_tools` (expose N, restrict to
  M), and `preamble` (visible plan before a tool call).
- **Multimodal**: GPT-5 reasoning models are text + image in, text out. **No audio**
  (input or output) and no video. The "omni" audio capability lived in separate 4o
  SKUs (`gpt-4o-audio-preview`, Realtime/`gpt-audio`), not base 4o. Audio workloads
  cannot move to GPT-5; keep them on the 4o-audio/Realtime line or split into
  speech-to-text, then GPT-5, then text-to-speech. Vision/image input migrates cleanly.
- **Streaming**: Chat Completions streaming mechanics are unchanged on GPT-5. Responses
  uses typed events (see section 2) plus reasoning items in the output.

---

## 5. Cost, context, caching, rate limits

### Pricing and context (USD per 1M tokens; verify at build time)

| Model | Input | Cached input | Output | Context total | Max output | Reasoning |
|---|---|---|---|---|---|---|
| gpt-4o | $2.50 | $1.25 | $10.00 | 128,000 | 16,384 | No |
| gpt-4o-mini | $0.15 | $0.075 | $0.60 | 128,000 | 16,384 | No |
| gpt-5 | $1.25 | $0.125 | $10.00 | 400,000 | 128,000 | Yes |
| gpt-5-mini | $0.25 | $0.025 | $2.00 | 400,000 | 128,000 | Yes |
| gpt-5-nano | $0.05 | $0.005 | $0.40 | 400,000 | 128,000 | Yes |
| gpt-5.1 | $1.25 | $0.125 | $10.00 | 400,000 | 128,000 | Yes |
| gpt-5.1-chat-latest | $1.25 | $0.125 | $10.00 | 128,000 | 16,384 | **No** |
| gpt-5-pro | $15.00 | n/a | $120.00 | 400,000 | 272,000 | Yes (high only) |

Headlines:
- gpt-5 / gpt-5.1 are **half the input price of 4o** ($1.25 vs $2.50) at the **same
  output price** ($10) - before reasoning tokens enter.
- gpt-5-mini and gpt-5-nano are dramatically cheaper than 4o on both axes; gpt-5-mini is
  the natural bulk-traffic cost-down target.
- `gpt-5.1-chat-latest` is the non-reasoning ChatGPT snapshot at 4o-shaped limits (128k
  / 16k) but reasoning-model price. To get the 272k/128k window you need the reasoning
  `gpt-5.1`, not the chat alias.
- The 128k output budget on the reasoning models is **shared between hidden reasoning
  and visible output**.

### The reasoning cost multiplier

Same visible 500-token answer, 2k input prompt:
- gpt-4o: ~$0.0100
- gpt-5.1 `none`/`minimal` (R~=0): ~$0.0075 (~25% cheaper than 4o)
- gpt-5.1 `medium` (R~=3,000 hidden): ~$0.0375 (~3.75x 4o)
- gpt-5.1 `high` (R~=10,000 hidden): ~$0.1075 (~10x 4o)

The effort knob swings effective per-task cost by more than 10x. Reasoning token counts
are not published; measure `reasoning_tokens` on representative traffic.

### Prompt caching (a real GPT-5 advantage)

- **90% discount** on cached input (cached = 10% of input rate). The "50%" figure in
  the docs refers to Batch/Flex, not caching.
- Automatic, no code change. Kicks in at prompts >= 1,024 tokens, caches the longest
  matching prefix in 128-token increments. Put static content first, dynamic last; pin
  related requests with `prompt_cache_key`.
- **Extended retention**: gpt-5 / gpt-5.1 keep cache up to ~24 hours vs 4o's ~5-60 min,
  materially raising hit rates for long stable system / RAG prefixes.
- Responses + `previous_response_id` raises cache hits and avoids re-charging for
  reasoning across turns. ZDR/stateless: carry reasoning via
  `reasoning.encrypted_content`.

### Rate limits

TPM is consumed by **all** tokens, including hidden reasoning tokens. A response that
returns 500 visible tokens but generates 5,000 reasoning tokens counts as ~5,500 output
tokens against TPM. When sizing throughput for the migration, multiply expected
output-token TPM by the (effort-dependent, 5x-20x) reasoning multiplier or you will hit
TPM ceilings far earlier than the 4o baseline predicts. Exact per-tier/per-model TPM
numbers are console-only.

### Batch / Flex / Priority

- Batch API: 50% discount, 24h window, separate higher rate-limit pool. Best for offline
  eval / bulk work (this repo's 08-06 offline-eval lab is a candidate consumer).
- Flex: 50% discount, synchronous via `service_tier="flex"`, slower/variable latency.
- Priority: ~2.5x rate for lower, more consistent latency (latency-SLA paths).

### Net: when GPT-5/5.1 is cheaper vs pricier than 4o

Cheaper when you move to mini/nano, run low/none/minimal effort, exploit caching
(90% + 24h), cut retries/scaffolding, or reuse reasoning across turns. Pricier when you
run high/xhigh effort on the flagship, use short uncacheable prompts, pick gpt-5-pro
needlessly, or forget reasoning eats TPM. Outcome is dominated by **size tier** and
**reasoning effort**, far more than headline per-token rates.

---

## 6. Prompting and behavior migration

Why 4o prompts regress:
- GPT-5 follows instructions literally ("surgical precision"). 4o-era hedging,
  repetition, and instruction "sandwiching" are no longer free.
- **Contradictions are expensive.** Conflicting or vague instructions make GPT-5 spend
  reasoning tokens trying to reconcile them (latency + quality hit). 4o silently picked
  one. Hunting contradictions in long inherited system prompts is the highest-ROI step.
- **Drop chain-of-thought prose.** "Think step by step" / "reason carefully" competes
  with the model's own internal reasoning and can hurt. Use `reasoning_effort` instead,
  treating it as a last-mile knob rather than the primary quality lever.

Levers that replace prompt hacks:
- **Eagerness control**: a `<persistence>` block to push autonomy ("keep going until
  the query is fully resolved... do not hand back on uncertainty"), or a
  `<context_gathering>` block plus an explicit tool-call budget to restrain it.
- **Tool preambles** (`<tool_preambles>`) to steer how the agent narrates plan/progress.
- **`verbosity`** (usually `low`) plus concrete length budgets.
- **Prompt Optimizer**: OpenAI's Playground tool
  (`platform.openai.com/chat/edit?optimize=true`) rewrites a prompt to GPT-5 best
  practice, removing contradictions, fixing format specs, and reconciling prompt vs
  few-shot inconsistencies. Recommended first pass when porting a 4o prompt.
- **Metaprompting**: a two-step diagnose-then-surgically-patch loop against failure logs.

GPT-5.1-specific:
- The new `none` mode is the natural target for latency-sensitive 4o workloads. But with
  `none` the model will not plan on its own, so re-add explicit "plan before each tool
  call and reflect on outcomes" instructions for agentic flows.
- Persona/tone is more steerable; GPT-5.1 can be excessively concise, so persistence
  instructions matter again. Suppress filler acknowledgments ("Got it", "Thanks").

Note from the vault (corticalstack/knowledge-vault, AI/models/GPT.md): OpenAI's
guidance for later 5.x families is to treat them as a new model family and re-baseline
prompts from scratch rather than port - Simon Willison flags this as unusually strong
evidence of model-family discontinuity, i.e. prior prompt optimizations may mislead.

Common regression-to-fix map:
| Symptom | Cause | Fix |
|---|---|---|
| Over-thinking / slow on trivial tasks | Oversized effort, no stop rule | Lower effort; `<context_gathering>` early-stop + tool budget |
| Shallow answers | Too little effort | Raise effort; add self-reflection rubric (not CoT) |
| Too verbose | Default `verbosity: medium` | `verbosity: low` + scoped overrides |
| Too many tool calls | Fuzzy 4o tool specs, "be thorough" | Crisp specs + "don't use for..."; remove maximizing language |
| Stops early / over-deferential | Missing persistence | Add `<persistence>` |
| Wastes tokens, inconsistent | Contradictory instructions | Remove conflicts (manually or via optimizer) |

---

## 7. Model lineup and replacement mapping

| Model | Reasoning? | API | Context / max out | Best fit |
|---|---|---|---|---|
| gpt-5 | Yes (min/low/med/high) | Chat + Responses | 272k/128k | Heavy reasoning; not a latency-sensitive 4o swap |
| gpt-5-mini | Yes | Chat + Responses | 272k/128k | Cost-sensitive reasoning; cheap bulk |
| gpt-5-nano | Yes | Chat + Responses | 272k/128k | Cheapest, highest throughput |
| gpt-5-chat | **No** | Chat + Responses | 128k/16k | Closest behavioral 4o drop-in (Preview on Azure) |
| gpt-5-codex | Yes | Responses only | 272k/128k | Agentic coding |
| gpt-5-pro | Yes (high only) | Responses | 400k/272k | Hardest offline reasoning |
| gpt-5.1 | Yes, adaptive (default `none`) | Chat + Responses | 272k/128k | Versatile: reasoning OR fast non-reasoning in one model |
| gpt-5.1-chat | **Yes** (changed from 5-chat) | Chat + Responses | 128k/16k | Conversational; NOT param-compatible with 4o |
| gpt-5.1-codex / -mini | Yes | Responses only | 272k/128k | Coding agents |

Replacement mapping:
- **gpt-4o (latency-sensitive chat)** -> `gpt-5.1` with `reasoning_effort: "none"`
  (OpenAI's stated natural fit), or `gpt-5-chat` / `gpt-5.1-chat` (note 5.1-chat is now
  reasoning and drops `temperature`). Azure's auto-upgrade points gpt-4o at gpt-5.1.
  Microsoft still positions plain **gpt-4.1** as the best pure low-latency non-reasoning
  chat option where no reasoning is wanted.
- **gpt-4o-mini** -> Azure GA path maps to **gpt-4.1-mini**; cheap GPT-5 analogs are
  gpt-5-mini / gpt-5-nano (but those are reasoning models).

---

## 8. Deprecation and retirement timelines

### OpenAI platform

- gpt-4o and gpt-4o-mini have **no announced shutdown date** as of mid-2026 (not on the
  deprecations list). OpenAI keeps 4o alive in the API for now.
- For contrast, original `gpt-4` and `gpt-4-turbo` are slated to shut down 2026-10-23
  (replacement gpt-5.5). (OpenAI separately retired gpt-4o in ChatGPT, the product, but
  that is distinct from the API.)

### Azure (the hard clock - but dates are in flux, VERIFY)

This is the key migration driver and also the most contradictory area across sources:

- The Azure **model retirement schedule table** (read in full, mid-2026) shows
  **2026-10-01** for gpt-4o (2024-05-13, 2024-08-06, 2024-11-20) and gpt-4o-mini
  (2024-07-18), with suggested replacements gpt-5.1 (for 4o) and gpt-4.1-mini (for
  4o-mini).
- Community Q&A and an anchoring web search instead report **earlier 2026 dates** for
  older snapshots: gpt-4o 2024-05-13 / 2024-08-06 retiring 2026-03-31 (auto-upgraded to
  gpt-5.1), gpt-4o-mini around 2026-02-27, with the 2024-11-20 snapshot at 2026-10-01.
  Those earlier dates would already be in the past as of 2026-06-03.
- Microsoft's own pages are internally inconsistent (the retirements narrative uses a
  2026-03-31 example while the schedule table says 2026-10-01). The dates have been
  moved repeatedly.

Action: **treat the live model-retirement-schedule page as canonical and re-check at
build time.** Do not hardcode a date in the lab; show how to query lifecycle status.

Azure lifecycle mechanics worth teaching:
- GA models get an 18-month retirement set at launch; replacement declared ~90-120 days
  out. Standard / DataZone / Global Standard **auto-upgrade** region by region;
  **Provisioned does NOT auto-upgrade** (manual migration, ensure target quota first).
- Retired models return **HTTP 410 Gone**.
- Fine-tuned 4o / 4o-mini: training retires no earlier than 2027-04-01, deployment
  2027-10-01.

### Assistants API

Both OpenAI and Azure retire the Assistants API on **2026-08-26**. Azure path: migrate
to the GA **Foundry Agent Service** (Threads -> Conversations, Runs -> Responses,
Assistants -> Agents), `pip install "azure-ai-projects>=2.0.0"`, migration tool at
`aka.ms/agent/migrate/tool` (migrates code constructs, not state). Under the hood the
Agent Service is built on Responses + Conversations, so "migrate to Agents" and "migrate
to Responses" are the same modernization on Azure.

---

## 9. Azure AI Foundry specifics (most relevant to this repo's lab)

### v1 GA API surface

- The **v1 GA API** (`/openai/v1/*`, including `/openai/v1/responses`) went GA
  (announced ~Feb 2026). Core endpoints are production-ready; some advanced features are
  still preview at launch.
- With v1 GA, **`api-version` is no longer required**. Append `/openai/v1` to the
  endpoint and use the stock `OpenAI()` client (not `AzureOpenAI()`).
- Newest/preview Responses features are opted into via preview headers or `preview`/
  `alpha` in the path, not by swapping api-version. Latest preview value seen:
  `2026-05-28` (and `2025-11-15-preview` on the Foundry services route).
- Two endpoint surfaces exist: Azure OpenAI (`...openai.azure.com/openai/v1/`, no
  api-version) and Foundry services (`...services.ai.azure.com/openai/v1/`, reported to
  still need `api-version=2025-11-15-preview` - VERIFY).

### Auth (matches this repo's DefaultAzureCredential convention)

```python
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import OpenAI
token_provider = get_bearer_token_provider(
    DefaultAzureCredential(), "https://ai.azure.com/.default")  # NEW scope
client = OpenAI(base_url="https://<resource>.openai.azure.com/openai/v1/",
                api_key=token_provider)
```

Note the new `https://ai.azure.com/.default` scope (not the old cognitiveservices
scope). Needs the `Cognitive Services OpenAI User` role. This repo already standardizes
on `DefaultAzureCredential`, so the migration lab should stay key-free.

### Azure availability and gotchas

- GPT-5 / GPT-5.1 standard inference does **not** require registration (gated items are
  computer-use-preview, xAI Grok, and GPT-5 reinforcement fine-tuning). Region
  availability is per model/version/deployment-type.
- Deployment-type rollout order: Global Standard first, then Global Provisioned, Data
  Zone, then regional Standard/Provisioned.
- **`model=` takes your deployment name**, not the model name. A `responses.create`
  model error usually means a wrong or region-unavailable deployment name.
- `gpt-5.1-chat` is now a reasoning model on Azure -> remove `temperature` and friends.
- `reasoning_effort` default flipped to `none` on gpt-5.1 -> pass it explicitly if you
  want thinking. `minimal` disables parallel tool calls.
- Default Azure content filters still apply; Standard auto-upgrade preserves quota,
  Provisioned needs target quota ensured before manual migration.
- Azure Responses feature gaps vs OpenAI (mid-2026): image-gen multi-turn edit +
  streaming, image-as-file input reference, and PDF `purpose="user_data"` upload are not
  supported; background + streaming has perf issues.

### Microsoft migration docs (URLs)

- Model choice (4o/4.1 vs GPT-5): learn.microsoft.com/azure/foundry/foundry-models/how-to/model-choice-guide
- Backward-compatible param playbook: techcommunity.microsoft.com "Migrating to GPT-5.x Without Breaking GPT-4"
- Chat Completions -> Responses: learn.microsoft.com/azure/foundry/openai/how-to/responses
- v1 GA API: learn.microsoft.com/azure/foundry/openai/api-version-lifecycle
- Assistants -> Agent Service: learn.microsoft.com/azure/foundry/agents/how-to/migrate
- Lifecycle policy: learn.microsoft.com/azure/foundry/openai/concepts/model-retirements
- Retirement schedule (dates): learn.microsoft.com/azure/foundry/openai/concepts/model-retirement-schedule
- Models sold by Azure (capabilities): learn.microsoft.com/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure
- Reasoning models how-to: learn.microsoft.com/azure/foundry/openai/how-to/reasoning

---

## 10. Consolidated migration challenges -> mitigations

| # | Challenge | Mitigation |
|---|---|---|
| 1 | Rejected sampling params (400) | Strip `temperature`/`top_p`/penalties/`logprobs`/`logit_bias`/`n`; steer via `reasoning_effort` + `verbosity` |
| 2 | `max_tokens` rejected | Use `max_completion_tokens` / `max_output_tokens`; audit SDK wrappers that auto-inject `max_tokens` |
| 3 | Empty output (budget eaten by reasoning) | Reserve >= 25k output budget; monitor `finish_reason`/`status` |
| 4 | Cost spike from hidden reasoning | Lowest acceptable effort; mini/nano; caching; reuse reasoning via `previous_response_id` |
| 5 | Latency spike | `none`/`minimal` effort; stream; smaller models; non-reasoning chat variant |
| 6 | TPM exhaustion | Multiply output-TPM budget by reasoning multiplier; raise tier; batch/flex offline |
| 7 | API-surface move | Adopt Responses; port `messages`->`input`+`instructions`, output reader, tools, streaming events |
| 8 | Assistants retirement (2026-08-26) | Migrate to Foundry Agent Service (Responses + Conversations) |
| 9 | Prompt regressions | Prompt Optimizer first; remove CoT + contradictions + padding; set verbosity/eagerness; metaprompt loop |
| 10 | Wrong variant choice | Map 4o->gpt-5.1 `none` (or gpt-5-chat); 4o-mini->gpt-4.1-mini or gpt-5-mini/nano |
| 11 | Lost audio modality | Keep on 4o-audio/Realtime, or STT -> GPT-5 -> TTS |
| 12 | Azure date/GA uncertainty | Query live lifecycle; do not hardcode dates; v1 GA core vs preview features |
| 13 | Azure auth/endpoint shift | `OpenAI()` + `/openai/v1/` + Entra scope `https://ai.azure.com/.default`; deployment name as `model=` |

---

## 11. Open questions to resolve at lab-build time

- Exact Azure gpt-4o / gpt-4o-mini retirement dates (sources conflict; some Q1-2026
  dates may already be past). Confirm against the live schedule page.
- Whether the Foundry `services.ai.azure.com/openai/v1` route still mandates a preview
  api-version.
- Whether the lab should target GPT-5.1 (the named target) or the current Azure
  flagship (5.2-5.5 by mid-2026), which add `xhigh` effort and shift defaults.
- Measured reasoning-token volumes and latency on the repo's own Foundry deployment
  (run a small benchmark; the numbers here are indicative/third-party).
- Reconcile the +3% SWE-bench vs +5% TAUBench Responses-reuse figures (different
  benchmarks/models).

---

## 12. Sources (primary, captured June 2026)

OpenAI:
- Responses / migrate-to-responses, reasoning, reasoning-best-practices, prompt-guidance,
  prompt-caching, rate-limits, batch, structured-outputs guides:
  developers.openai.com/api/docs/...
- Cookbook: gpt-5_prompting_guide, gpt-5-1_prompting_guide, gpt-5_troubleshooting_guide,
  gpt-5_new_params_and_tools, prompt-optimization-cookbook, responses_api/reasoning_items:
  developers.openai.com/cookbook/examples/...
- Model pages: gpt-4o, gpt-4o-mini, gpt-5, gpt-5-mini, gpt-5-nano, gpt-5.1,
  gpt-5.1-chat-latest, gpt-5-pro: developers.openai.com/api/docs/models/...
- Deprecations: developers.openai.com/api/docs/deprecations
- Announcements: openai.com/index/gpt-5-1-for-developers, /gpt-5-1,
  /introducing-gpt-5-for-developers, /retiring-gpt-4o-and-older-models (some 403 to
  fetch; corroborated via cookbook + Simon Willison writeups)

Azure / Microsoft:
- learn.microsoft.com/azure/foundry/openai/how-to/reasoning
- learn.microsoft.com/azure/foundry/openai/how-to/responses
- learn.microsoft.com/azure/foundry/openai/api-version-lifecycle
- learn.microsoft.com/azure/foundry/openai/concepts/model-retirements
- learn.microsoft.com/azure/foundry/openai/concepts/model-retirement-schedule
- learn.microsoft.com/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure
- learn.microsoft.com/azure/foundry/foundry-models/how-to/model-choice-guide
- learn.microsoft.com/azure/foundry/agents/how-to/migrate
- learn.microsoft.com/azure/foundry-classic/openai/concepts/assistants
- techcommunity.microsoft.com "Migrating to GPT-5.x Without Breaking GPT-4"

Secondary / indicative:
- d4b.dev GPT-5 response-time benchmark (latency-vs-effort, single harness)
- simonwillison.net GPT-5.1 / GPT-5.5 writeups
- corticalstack/knowledge-vault AI/models/GPT.md
