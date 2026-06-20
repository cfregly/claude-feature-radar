Subject: Congrats on YC! A Claude trick for citing your own RAG chunks

Hey {first_name},

Congrats on the batch. One quick tip from building RAG over private data: keep your retriever and
your reranker yours. The moment you let an answer point only at a file name, your users stop trusting
the citation, and you stop being able to debug a bad answer.

The problem I keep hitting: I run my own retrieval (pgvector, a reranker I wrote) and I want each
answer to deep-link to the exact passage it came from. The common path ships those passages into a
hosted vector store and hands back a file-level pointer, plus a copy of customer data I now have to
manage.

Claude has a cleaner route. Pass the chunks your retriever already returned straight into the request
as search_result content blocks with citations enabled. Claude answers and cites them inline.

    blocks = [{"type": "search_result", "source": "kb://overage.txt", "title": "Overage billing",
               "content": [{"type": "text", "text": chunk_text}],
               "citations": {"enabled": True}}]              # makes each chunk citable
    content = blocks + [{"type": "text", "text": question}]   # ask over the chunks inline

Every answer comes back with a search_result_location pointer: which chunk, the block span inside it,
and the verbatim cited text. No hosted store, no upload, no copy of your users' data, no resolver code.
I measured it over five questions across five chunks: 5 of 5 answered, 5 of 5 cited to the correct
chunk, block-level pointer, 0 hosted objects, $0.0067 on Claude Haiku 4.5.

Demo and code: https://github.com/cfregly/claude-feature-hits/blob/main/search_results/README.md

Run it in about a minute for $0.05:

    make search_results

To try it on your own data, edit the CHUNKS and QUESTIONS in search_results/run.py with your
retriever's passages and questions, then run python search_results/run.py.

Happy building! 🚀
{your_name}
Building with Claude
