Subject: Congrats on YC! A sandbox pattern for work-app agents

Hey Jonny,

First of all, congrats on the batch! Very exciting!!

My name is Chris Fregly, and I'm on the Applied AI team here at Anthropic. I focus on helping AI startups like Tasklet get past the bottlenecks that show up once agents move from demo to product.

I saw Tasklet is building agents that call work-app APIs to get tasks done. From one former founder to an active founder, builder to builder, I wanted to share a Claude pattern for app-API agents that need to make many calls, inspect bulky intermediate results, and return one action.

Without a filter point, every API result flows into the model context. Claude programmatic tool calling gives you that filter point. Mark your tool as callable from code execution, then Claude can write a sandbox script that loops over the tool and returns only the answer the model needs.

```python
tools=[
    {"type": "code_execution_20260120", "name": "code_execution"},  # add this
    {"name": "fetch_workspace_task", "input_schema": {...},
     "allowed_callers": ["code_execution_20260120"]},               # app results run in the sandbox
]
```

Using my API key, the measured fan-out run went from 9,451 to 6,828 billed input tokens, with the exact winner returned from the sandbox. That is the shape: many tool calls, bulky results, one final answer.

Full brief, demo GIF, code, and sample output: https://github.com/cfregly/claude-feature-hits/tree/main/programmatic_tool_calling

Run it in about two minutes for about $0.08:

```bash
git clone https://github.com/cfregly/claude-feature-hits && cd claude-feature-hits
# Starter credits if you need an API key: https://claude.com/offers?offer_code=bdfcc786-eb41-44f3-9190-e29e6e38209c&signup_code=3a6e0453a611a2c4bd79968fa98e3471
export ANTHROPIC_API_KEY=your-api-key
make programmatic_tool_calling
```

To try it on Tasklet's shape, edit `programmatic_tool_calling/my_tool.py` with one of your work-app tools and the inputs it fans out over.

If I guessed the wrong bottleneck, reply with the real one and I can point you to the closest Claude pattern.

Happy building,

--Chris Fregly
Applied AI, Anthropic
fellow Claude builder and former AI startup founder
