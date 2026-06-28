# Find customer risk for the price of the decision, not every tool output

![demo](https://raw.githubusercontent.com/cfregly/claude-feature-hits/main/programmatic_tool_calling/demo.gif)

[![Claude proof: 74% fewer input tokens](https://img.shields.io/badge/Claude%20proof-74%25%20fewer%20input%20tokens-2F855A)](https://github.com/cfregly/claude-feature-hits/blob/main/programmatic_tool_calling/sample.txt)

When your agent decides which customers are at risk, it may need support tickets, logs, usage, CRM notes, and compliance docs. Direct tool use dumps every raw row into the model's context. Programmatic tool calling lets Claude write code in a sandbox that calls your tool, rejects malformed rows, joins evidence by account, and passes just the compact decision packet to the model. In this demo, that code calls `query_customer_evidence(source)` for five evidence sources, sums `risk_points` for each account, preserves evidence IDs and caveats, and returns the three accounts most likely to churn or block expansion.

## What you get

`allowed_callers` is the request field that presents your tool to Claude under the code-execution
caller path. It is routing guidance, not an authorization boundary, and it does not filter by itself.
The filtering is the Python code Claude writes in the sandbox.

```python
response = client.messages.create(
    model="claude-sonnet-4-6",
    messages=[...],
    tools=[
        {"type": "code_execution_20260120", "name": "code_execution"},   # add this
        { "name": "query_customer_evidence", "input_schema": {...},   # your tool, unchanged
          "allowed_callers": ["code_execution_20260120"] },        # add this line: tool outputs stay in the sandbox, not the model context
    ],
)
```

The measured run, same task and same model (Sonnet 4.6), the only change is the feature on or off: fan out across five evidence sources, then find three at-risk customer accounts. The reducer is deterministic Python: keep valid rows, reject malformed rows, group by `account_id`, sum `risk_points`, keep evidence IDs and caveats, then return the compact packet.

| your run | input tokens billed | what it means |
|---|---:|---|
| without programmatic tool calling | 54,989 | every raw evidence row lands in the model's context |
| **with programmatic tool calling** | **14,299** | only the compact decision packet reaches the model |

That is **74% fewer input tokens**, with the same three customer accounts returned from the sandbox. Every cell is read live off the API's own `usage` object, so re-running shifts the count a little. The saving grows with the size of the fan-out.

## Best-available comparison

This artifact is a Claude A/B receipt: same model, same fan-out task, with and without programmatic
tool calling. The fair OpenAI and Gemini paths are not a matching `allowed_callers` field. They are
tool or function calling plus Code Interpreter, code execution, or an app-owned reducer that consumes
the raw records before the model sees the final answer.

Those paths can compute the same account list if the app owns the reducer and dispatch. The measured Claude
claim here is narrower: Claude lets the model drive the fan-out while the custom-tool outputs stay
out of the model context. Do not describe this as an all-provider cost win without a same-workload
OpenAI and Gemini receipt.

## Dimension matrix

| Dimension | Status | Receipt |
| --- | --- | --- |
| Cost | Measured | 74% fewer billed input tokens on the same fan-out task. |
| Speed | Not claimed | The programmatic path uses more round trips in this sample. No latency win is claimed. |
| Accuracy | Guarded, not promoted | The reducer eval and trace gate check the same three accounts, but this is not an accuracy artifact. |
| Reliability | Guarded, not promoted | The trace gate checks caller path, fallback, container, and correctness before trusting the cost receipt. |
| Operations | Not claimed | The artifact shows the two request-field edits, but does not quantify app code removed. |
| Security | Not claimed | `allowed_callers` is routing guidance, not an authorization boundary. |

## Reducer eval gate

The repo treats this as a reducer, not a slide claim. `programmatic_tool_calling/tool_result_reducer.py` validates
each row, rejects malformed input, joins rows by account ID, ranks accounts, and returns compact evidence:
account IDs, risk labels, reasons, source IDs, caveats, fallback status, and data version. `make ci`
runs `scripts/check_reducer_contract.py`, which checks the exact account list, rejected-row count,
schema, malformed rows, duplicate evidence IDs, unexpected fields, missing fields, bad account IDs,
and whether the compact output keeps enough evidence to audit the decision. The same gate pins the
deterministic customer-evidence fixture with SHA-256
`e0bd6424352c512e2c8529fe44d69a9aa9924e2ec329dd5c25d8f804291fa7b7`, so tool-result drift fails CI
before a token receipt is trusted.

The runner emits a per-run trace with schema versions, caller path, observed server-tool blocks,
caller-path drift, snapshot hooks, budget gates, input token buckets, raw tool-output size, final
result size, latency, correctness, row counts, partial-result state, abstain reason, fallback path,
policy denials, and cost per successful task.
`make ci` also runs `scripts/check_trace_contract.py`, which checks the trace contract without an API key.
The live `--check` gate promotes the programmatic tool calling receipt only when Mode B has fewer input tokens, the
expected account list, the expected caller path, an observed server-tool block, a code-execution container
id, and no fallback reason.
Trace-only metadata can live under `_trace_metadata` on `TOOL_SPEC`. The runner records it in the
trace and strips it before sending the tool schema to the API.
For the A/B comparison, the runner also strips any stale `allowed_callers` from the direct baseline
and adds it only to the programmatic arm.

The rollout should be staged: run offline against fixtures and production-like traces, shadow beside
the direct path and compare account list, evidence IDs, rejected rows, latency, and cost, canary only for the
fan-out workload shape where it wins, then default only with a direct-tool fallback and alerts on
fallback rate, container failures, caller-path drift, and cost per successful task.

Before calling this path production-ready, define the claim, the eval, the rollout gate, and the
stop-or-slow trigger. For this sample, stop or slow down on wrong account lists, evidence mismatches,
latency regression, fallback spikes, container failures, caller-path drift, policy-denial spikes,
rate-limit saturation, or all-in cost per successful task losing to direct tool use.

## Cost scope

The printed dollar figure is token/API cost from the API usage object. It includes the weighted token
buckets the API reports: uncached input, cache reads, cache writes, output, and knowable server-tool
charges. Cached tokens are not ignored. Cache reads price lower than fresh input, and cache writes
price higher than fresh input, so the code prices each bucket separately instead of treating every
token as the same dollar.

Programmatic tool calling uses code execution. Code-execution runtime is not part of the token/API
usage bucket. It can bill separately after the monthly free allowance when it is not paired with newer
web search or web fetch tools. Anthropic's current code-execution pricing says execution time has a
5-minute minimum, each org receives 1,550 free hours per month, and additional usage is billed at
$0.05 per hour per container. That means one new billed programmatic tool calling container has a post-free-allowance
5-minute floor exposure of $0.0042 before container reuse, longer runtime, or free allowance
effects.

So in production, factor this in as separate line items: token/API cost + code-execution runtime +
backend cost + correctness + latency + failure rate. The claim here is narrower and measured: fewer
billed input tokens on this fan-out workload, with the same answer.

## Why I built this on Claude

`allowed_callers` guides Claude to call your own tool from the code sandbox, where code can
aggregate raw tool outputs before the model sees the final answer. Your app still decides whether
the backend call is authorized. For customer-risk work, that routing path is the difference between
paying for every evidence row and paying for the compact decision.

## Run it (estimated $0.08 token/API cost)

```
export ANTHROPIC_API_KEY=your-api-key   # https://console.anthropic.com/
make programmatic_tool_calling      # builds the venv, installs anthropic, runs the measured customer-evidence example
```

`make programmatic_tool_calling` is self-bootstrapping: it creates `.venv`, installs `anthropic`, and runs the comparison. It takes about two minutes. The estimate excludes any separate code-execution runtime charge after the free allowance.

The terminal also prints the code-execution floor exposure for the programmatic arm. It is not folded into the
token/API table because the API usage object tracks token buckets and code-execution requests, not an
exact runtime invoice.

## Run it on your own data

Open `programmatic_tool_calling/founder_workload.py`, the one file you edit. Replace these, then run `make programmatic_tool_calling` again:

1. `TOOL_SPEC` with your own Messages-API tool dict (the same `{name, description, input_schema}` you already pass in `tools=[...]`). Add optional `_trace_metadata` when you want schema versions, reducer versions, or snapshot IDs in the run trace.
2. `call(...)` with your real backend (a database query, an API call, a file read) returning whatever the model normally gets back.
3. `QUESTION` and `EXAMPLE_INPUTS` with your fan-out task and the inputs it fans out over.

Keep the task fan-out shaped, where the agent calls your tool many times, because that is where the input-token saving shows up.

Founder runbook:

| Step | What to do |
|---|---|
| Build | Use one workload, one narrow tool, bounded fan-out, and a deterministic reducer. |
| Test | Compare direct and programmatic tool calling on the same expected answer, reducer eval, trace contract, latency, and cost per successful task. |
| Avoid | Do not ship broad database access, unsupported caller paths, raw customer payloads in logs, or default rollout without fallback. |
| Access | Stay offline until fixtures pass, shadow until traces agree, canary only on the won workload, and default only with alerts and rollback. |

## Learn more

- [Programmatic tool calling docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/programmatic-tool-calling)
- [Code execution pricing](https://platform.claude.com/docs/en/agents-and-tools/tool-use/code-execution-tool#usage-and-pricing)
- [Prompt caching pricing](https://platform.claude.com/docs/en/build-with-claude/prompt-caching#pricing)
