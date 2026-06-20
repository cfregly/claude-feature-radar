# Know why your prompt cache missed with Claude cache diagnostics

![demo](demo.gif)

Your cached prefix stopped hitting and your token bill jumped. The only signal is `cache_read_input_tokens` dropping to zero, with no clue what changed. A timestamp in the system prompt, a reordered tool, or an edit to an earlier message silently breaks the cache. Claude cache diagnostics compares two consecutive requests and names the exact part of the prompt that diverged, so you fix the root cause instead of guessing.

## What you get

Pass the previous response `id`, and Claude returns one typed `cache_miss_reason` naming the part that changed: the model, the system prompt, the tools, or the messages.

```python
second = client.beta.messages.create(
    model="claude-haiku-4-5-20251001",
    system=changed_system,
    messages=[{"role": "user", "content": "Reply ok."}],
    diagnostics={"previous_message_id": first.id},      # add this
    betas=["cache-diagnosis-2026-04-07"],               # add this
)
second.diagnostics.cache_miss_reason.type  # typed: model / system / tools / messages changed
```

On the 2026-06-19 run Claude named the exact cause, `system_changed`, on 4/4 root-cause variants. That cuts the suspect list from 4 to 1, and it came with a missed-token estimate (6,827) so you can see how much cached prefix you lost. A blind cache-miss hunt becomes a one-line answer.

## Why this is hard to get elsewhere

On the same live run (2026-06-19), both OpenAI and Gemini exposed cache token counters but no per-request reason for the miss. Only Claude returned a typed `cache_miss_reason` naming the part that changed. The counters tell you the cache missed. Claude tells you why.

## Run it (about $0.02)

```bash
export ANTHROPIC_API_KEY=sk-ant-...
make cache_diagnostics
```

About a minute on one key.

## Run it on your own data

Edit `cache_diagnostics/run.py` to point the two calls at your own system prompt, tools, or messages, then run:

```bash
python cache_diagnostics/run.py --check
```

## Learn more

Claude cache diagnostics: https://platform.claude.com/docs/en/build-with-claude/cache-diagnostics
