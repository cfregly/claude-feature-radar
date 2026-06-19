# Know why your prompt cache missed with Claude cache diagnostics

![demo](demo.gif)

Your cached prefix stopped hitting and your bill jumped. The only signal is `cache_read_input_tokens` dropping to zero, with no clue what changed. A timestamp in the system prompt, a reordered tool, an edit to an earlier message: any one silently breaks the cache. Claude cache diagnostics compares two consecutive requests and tells you exactly where the prefix diverged, so you fix the root cause instead of guessing.

## What you get

Pass the previous response `id`, and Claude returns a typed `cache_miss_reason` that names the one surface that changed: the model, the system prompt, the tools, or the messages. On the 2026-06-19 run Claude named the changed surface as `system_changed` and estimated 6,827 missed input tokens, cutting the suspect list from 4 possible prefix surfaces down to 1. That turns a blind cache-miss hunt into a one-line answer.

```python
second = client.beta.messages.create(
    model="claude-haiku-4-5-20251001",
    system=changed_system,
    messages=[{"role": "user", "content": "Reply ok."}],
    cache_control={"type": "ephemeral"},
    diagnostics={"previous_message_id": first.id},  # add this
    betas=["cache-diagnosis-2026-04-07"],           # add this
)
print(second.diagnostics.cache_miss_reason.type)    # -> "system_changed"
```

## Run it (about $0.02)

```bash
make cache_diagnostics
```

## Run it on your own prompts

Edit `cache_diagnostics/run.py` (point the two calls at your own system prompt, tools, or messages), then run:

```bash
python cache_diagnostics/run.py --check
```

## Beta header

Cache diagnostics is in beta. Set the beta header `cache-diagnosis-2026-04-07` on the request, as shown above.

## Learn more

Claude cache diagnostics: https://platform.claude.com/docs/en/build-with-claude/cache-diagnostics
