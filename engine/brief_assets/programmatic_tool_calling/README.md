# Meter usage per cohort for the price of the answer, not every tool output

![demo](https://raw.githubusercontent.com/cfregly/claude-feature-hits/main/programmatic_tool_calling/demo.gif)

[![Claude proof: 27% fewer input tokens](https://img.shields.io/badge/Claude%20proof-27%25%20fewer%20input%20tokens-2F855A)](https://github.com/cfregly/claude-feature-hits/blob/main/programmatic_tool_calling/sample.txt)

When your agent meters usage per cohort or runs analytics across regions, it calls one of your own tools many times, then crunches what comes back. Every one of those calls dumps its outputs into the model's context, and you pay input tokens for all of them, even the outputs the agent never uses. Programmatic tool calling runs your tool inside a code sandbox (a server-side scratchpad that crunches the outputs for you), keeps only what matters, and passes just the answer to the model. The tool outputs stay in the sandbox, so they never reach the context.

## What you get

`allowed_callers` is the one line that does the work: it tells Claude your tool can be called from the sandbox instead of through the model.

```python
response = client.messages.create(
    model="claude-sonnet-4-6",
    messages=[...],
    tools=[
        {"type": "code_execution_20260120", "name": "code_execution"},   # add this
        { "name": "query_region_sales", "input_schema": {...},   # your tool, unchanged
          "allowed_callers": ["code_execution_20260120"] },        # add this line: tool outputs stay in the sandbox, not the model context
    ],
)
```

The measured run, same task and same model (Sonnet 4.6), the only change is the feature on or off: fan out across several regions of sample sales outputs (a fan-out is one agent calling one tool many times), then find the highest-revenue region.

| your run | input tokens billed | what it means |
|---|---:|---|
| without programmatic tool calling | 9,494 | every tool output lands in the model's context |
| **with programmatic tool calling** | **6,910** | only the answer reaches the model |

That is **27% fewer input tokens**, with the exact winner returned from the sandbox. Every cell is read live off the API's own `usage` object, so re-running shifts the count a little. The saving grows with the size of the fan-out.

## Why I built this on Claude

`allowed_callers` lets Claude call your own tool from the code sandbox and return only the computed answer to the model. For metering across many cohorts, that is the difference between paying for every tool output and paying for the answer.

## Run it ($0.08)

```
export ANTHROPIC_API_KEY=your-api-key   # https://console.anthropic.com/
make programmatic_tool_calling      # builds the venv, installs anthropic, runs the measured region_sales example
```

`make programmatic_tool_calling` is self-bootstrapping: it creates `.venv`, installs `anthropic`, and runs the comparison. It takes about two minutes.

## Run it on your own data

Open `programmatic_tool_calling/my_tool.py`, the one file you edit. Replace these, then run `make programmatic_tool_calling` again:

1. `TOOL_SPEC` with your own Messages-API tool dict (the same `{name, description, input_schema}` you already pass in `tools=[...]`).
2. `call(...)` with your real backend (a database query, an API call, a file read) returning whatever the model normally gets back.
3. `QUESTION` and `EXAMPLE_INPUTS` with your fan-out task and the inputs it fans out over.

Keep the task fan-out shaped, where the agent calls your tool many times, because that is where the input-token saving shows up.

## Learn more

- [Programmatic tool calling docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/programmatic-tool-calling)
