Subject: Congrats on YC! 🎉 A cool Claude feature to help you build

Hey {first_name},

Congrats on getting into YC! Quick tip to trim your Claude token bill.

If your app searches your content to answer a question, every chunk it pulls back lands in the model's context, and you pay for all of them, even the ones that turn out irrelevant.

[Programmatic tool calling](https://platform.claude.com/docs/en/agents-and-tools/tool-use/programmatic-tool-calling) (PTC) fixes that. Claude runs your search tool inside a code sandbox, keeps only the relevant chunks, and passes just those to the model. The rest never reach the context, so you are not billed for them.

It is one change to the API call you already make:

```python
response = client.messages.create(
    model="claude-sonnet-4-6",
    messages=[...],
    tools=[
        {"type": "code_execution_20260120", "name": "code_execution"},   # add this
        { "name": "search_docs", "input_schema": {...},        # your tool, unchanged
          "allowed_callers": ["code_execution_20260120"] },    # add this line
    ],
)
```

Same task and model (Sonnet 4.6), with and without it:

| | input tokens billed | why |
|---|---:|---|
| without PTC | 9,451 | every chunk lands in the model's context |
| with PTC | 6,828 | only the relevant chunks reach the model |

28% cheaper on this demo, and it compounds across every search. On Anthropic's [agentic-search benchmarks](https://claude.com/blog/improved-web-search-with-dynamic-filtering), filtering results in code this way cut input tokens 24% and improved answers 11%.

See it run (about two minutes):

![PTC demo]({repo_url}/raw/main/docs/demo.gif)

```
git clone {repo_url} && cd claude-feature-briefs
export ANTHROPIC_API_KEY=your-key
make ptc        # the example, $0.06
```

To run it on your own tool, open [yourtool.py]({repo_url}/blob/main/ptc/yourtool.py), drop in your search tool, and run `make ptc` again.

More: the [PTC cookbook](https://platform.claude.com/cookbook/tool-use-programmatic-tool-calling-ptc) is a runnable notebook.

Happy building! 🚀
Chris Fregly
Applied AI, Startups @ Anthropic
