Subject: Congrats on YC! A Claude feature for silent prompt-cache misses

Hey {first_name},

Congrats on the batch. One quick tip from building on long cached prompts: keep any timestamp or request-id out of the cached system prefix, because a single changing byte resets the whole prefix and your cache stops hitting.

That bug is brutal to chase. Your prompt cache stops hitting, the bill climbs, and the only signal is `cache_read_input_tokens` dropping to zero. Nothing tells you what changed: the model, the system prompt, a reordered tool, or an edit to an earlier message.

Claude cache diagnostics closes that gap. Pass the previous response id and Claude returns a typed reason naming the one surface that changed.

```python
second = client.beta.messages.create(
    model="claude-haiku-4-5-20251001",
    system=changed_system,
    messages=[{"role": "user", "content": "Reply ok."}],
    diagnostics={"previous_message_id": first.id},  # add this
    betas=["cache-diagnosis-2026-04-07"],           # add this
)
print(second.diagnostics.cache_miss_reason.type)    # -> "system_changed"
```

On my key (2026-06-19) Claude named the changed surface as `system_changed` and estimated 6,827 missed input tokens, cutting the suspect list from 4 possible prefixes to 1.

Beta note: set the beta header `cache-diagnosis-2026-04-07`, as shown above.

A 1.5-second demo: https://github.com/cfregly/claude-feature-briefs/blob/main/cache_diagnostics/README.md

Run it (about $0.02): `make cache_diagnostics`

To run it on your own prompts, edit `cache_diagnostics/run.py` to point the two calls at your own system prompt, tools, or messages, then run `python cache_diagnostics/run.py --check`.

Happy building! 🚀
{your_name}
Building with Claude
