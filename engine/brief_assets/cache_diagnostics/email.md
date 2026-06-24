Subject: Congrats on YC! Cache-miss debugging for long prompts

Hey {first_name},

Congrats on the batch. Quick builder tip from running on long cached prompts: keep any timestamp or request id out of the cached part of your prompt, because one changing byte resets the whole prefix and your cache quietly stops hitting.

That bug is brutal to chase. Your prompt cache stops hitting, your token bill climbs, and the only signal is `cache_read_input_tokens` dropping to zero. Nothing tells you what changed: the model, the system prompt, a reordered tool, or an edit to an earlier message.

Claude cache diagnostics closes that gap. Pass the id of your previous response and Claude returns one typed reason naming the exact part of the prompt that changed.

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

Using my API key (2026-06-19) Claude named the exact cause, `system_changed`, for the seeded system-prompt change. That cuts the suspect list from 4 possible prefix surfaces to 1, and it came with a missed-token estimate (6,827) so I could see how much cached prefix I lost.

One honest note from the same run: both OpenAI and Gemini expose cache token counters, but only Claude returned a typed per-request reason naming what broke. The counters tell you the cache missed. Claude tells you why.

Estimated $0.02 and a minute to reproduce using your own API key:

```bash
git clone https://github.com/cfregly/claude-feature-hits && cd claude-feature-hits
export ANTHROPIC_API_KEY=your-api-key
make cache_diagnostics
```

Full brief, demo GIF, code, and sample output: https://github.com/cfregly/claude-feature-hits/tree/main/cache_diagnostics

Docs: https://platform.claude.com/docs/en/build-with-claude/cache-diagnostics

To run it on your own prompts, edit `cache_diagnostics/run.py` to point the two calls at your own system prompt, tools, or messages, then run `.venv/bin/python -m cache_diagnostics.run --check`.

Beta note: set the beta header `cache-diagnosis-2026-04-07`, as shown above.

Hope it saves you a debugging afternoon.
{your_name}
Building with Claude
