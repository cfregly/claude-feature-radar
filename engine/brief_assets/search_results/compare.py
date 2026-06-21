"""compare: reproduce the inline-RAG-citation head-to-head against OpenAI and Gemini, same chunks.

The default brief runs the Claude side alone on one dependency. Set OPENAI_API_KEY and GEMINI_API_KEY,
install the optional comparison SDKs (pip install -r requirements-compare.txt), and run
`make search_results COMPARE=1` to reproduce the whole table using your own API keys, not just the Claude side.

Best to best, the same chunks cited on each platform's strongest path. The measured thing is two things:
the citation pointer the developer receives, and how many objects you must persist to get it. Claude
takes the chunks inline as search_result blocks and returns a block-range pointer (which chunk plus the
block span inside it) while persisting zero objects. OpenAI file_search requires creating a hosted
vector store and uploading each chunk as a file (the citation is file-level), and Gemini file_search
requires a hosted file_search_store with each chunk imported (the grounding is chunk-level). So both
competitors persist a copy of your users' data to cite it. Each arm deletes its store on cleanup, so no
persisted copy is left behind. Sources, re-fetched 2026-06-19:
  - Claude search results: https://platform.claude.com/docs/en/build-with-claude/search-results
  - OpenAI file search: https://developers.openai.com/api/docs/guides/tools-file-search
  - Gemini file search: https://ai.google.dev/gemini-api/docs/file-search

Every SDK import is lazy, so importing this module needs no comparison SDK. A missing API key or SDK skips
that arm with a clear note. Note that the OpenAI and Gemini arms CREATE a hosted store and upload your
chunks (the objects the table counts), then delete it, so this arm runs slower than the Claude side.
"""

from __future__ import annotations

import time

from .common.compare_clients import COMPARE_DEPS_HINT, gemini_cost, get_gemini_client, get_openai_client, openai_cost
from .common.models import get

# The competitor models, each side's strongest hosted-retrieval reader, matching the brief table.
OPENAI_MODEL = "gpt-mid"    # gpt-5.4
GEMINI_MODEL = "gem-flash"  # gemini-3.5-flash
MAX_TOKENS = 512


def _openai_arm() -> dict:
    """OpenAI file_search: create a hosted vector store, upload each chunk as a file, query, and read the
    citation granularity. The store plus one file per chunk are the persisted objects the table counts."""
    import io

    from .run import CHUNKS, QUESTIONS

    m = get(OPENAI_MODEL)
    client = get_openai_client()
    if client is None:
        return {"label": "OpenAI (" + m.id + ")", "skipped": "set OPENAI_API_KEY to run this arm"}
    store = None
    file_ids = []
    pointer = "none"
    cost = 0.0
    try:
        store = client.vector_stores.create(name="feature-hits-sr")
        objects = 1
        for cid, title, body in CHUNKS:
            f = client.files.create(file=(cid, io.BytesIO(body.encode()), "text/plain"), purpose="assistants")
            file_ids.append(f.id)
            client.vector_stores.files.create(vector_store_id=store.id, file_id=f.id)
            objects += 1
        for _ in range(30):
            lst = client.vector_stores.files.list(vector_store_id=store.id)
            if lst.data and all(getattr(x, "status", "") == "completed" for x in lst.data):
                break
            time.sleep(2)
        for q, ans_idx, token in QUESTIONS[:2]:
            r = client.responses.create(
                model=m.id, max_output_tokens=MAX_TOKENS,
                tools=[{"type": "file_search", "vector_store_ids": [store.id]}],
                input=q + " Answer in one sentence and cite the source.")
            cost += openai_cost(OPENAI_MODEL, r.usage)
            for item in (getattr(r, "output", None) or []):
                for c in (getattr(item, "content", None) or []):
                    for a in (getattr(c, "annotations", None) or []):
                        if getattr(a, "type", None) == "file_citation":
                            pointer = "file-level"
        return {"label": "OpenAI (" + m.id + ")", "pointer": pointer, "objects": objects, "cost": cost}
    finally:
        try:
            if store is not None:
                client.vector_stores.delete(store.id)
            for fid in file_ids:
                try:
                    client.files.delete(fid)
                except Exception:  # noqa: BLE001
                    pass
        except Exception:  # noqa: BLE001
            pass


def _gemini_arm() -> dict:
    """Gemini file_search: create a hosted file_search_store, import each chunk, query, and read the
    grounding granularity. The store plus one import per chunk are the persisted objects the table counts."""
    import os
    import tempfile

    from .run import CHUNKS, QUESTIONS

    m = get(GEMINI_MODEL)
    client = get_gemini_client()
    if client is None:
        return {"label": "Gemini (" + m.id + ")", "skipped": "set GEMINI_API_KEY to run this arm"}
    from google.genai import types

    store = None
    pointer = "none"
    cost = 0.0
    tmpdir = tempfile.mkdtemp()
    try:
        store = client.file_search_stores.create(config={"display_name": "feature-hits-sr"})
        objects = 1
        for cid, title, body in CHUNKS:
            path = os.path.join(tmpdir, cid)
            with open(path, "w") as fh:
                fh.write(body)
            op = client.file_search_stores.upload_to_file_search_store(
                file=path, file_search_store_name=store.name, config={"display_name": cid})
            objects += 1
            for _ in range(30):
                op = client.operations.get(op)
                if getattr(op, "done", False):
                    break
                time.sleep(2)
        tool = types.Tool(file_search=types.FileSearch(file_search_store_names=[store.name]))
        for q, ans_idx, token in QUESTIONS[:2]:
            r = client.models.generate_content(
                model=m.id, contents=q + " Answer in one sentence and cite the source.",
                config=types.GenerateContentConfig(tools=[tool], max_output_tokens=MAX_TOKENS))
            cost += gemini_cost(GEMINI_MODEL, getattr(r, "usage_metadata", None))
            for cand in (getattr(r, "candidates", None) or []):
                gm = getattr(cand, "grounding_metadata", None)
                if gm and (getattr(gm, "grounding_chunks", None) or []):
                    pointer = "chunk-level"
        return {"label": "Gemini (" + m.id + ")", "pointer": pointer, "objects": objects, "cost": cost}
    finally:
        try:
            if store is not None:
                client.file_search_stores.delete(name=store.name, config={"force": True})
        except Exception:  # noqa: BLE001
            pass


def _run_arm(fn, *args) -> dict:
    """Run one competitor arm, turning any failure into a skipped row, so --compare never crashes."""
    try:
        return fn(*args)
    except SystemExit as e:
        return {"skipped": str(e)}
    except Exception as e:  # noqa: BLE001
        return {"skipped": type(e).__name__ + ": " + str(e)[:80]}


def append_comparison(model_key: str, claude_result: dict) -> None:
    """Run the OpenAI and Gemini arms on the SAME chunks the Claude arm just cited inline, then print the
    full head-to-head table: the citation pointer each developer receives, and the objects you must
    persist to get it. The Claude row reuses the result already computed, so Claude is not billed twice."""
    short = get(model_key).label.replace("Claude ", "")
    claude_label = "Claude (" + short + ")"

    print("  Reproducing the head-to-head: the citation pointer you receive and the objects you store.")
    print("  The OpenAI and Gemini arms create a hosted store and upload your chunks. " + COMPARE_DEPS_HINT + ".\n")

    oai = _run_arm(_openai_arm)
    gem = _run_arm(_gemini_arm)

    rows = [(claude_label, claude_result["pointer"], str(claude_result["objects"]) + " persisted")]
    for arm in (oai, gem):
        if "skipped" in arm:
            rows.append((arm.get("label", "competitor"), "skipped: " + arm["skipped"], ""))
        else:
            rows.append((arm["label"], arm["pointer"], str(arm["objects"]) + " persisted"))

    print(f"  {'platform':<22}{'citation pointer':>18}{'objects you store':>20}")
    print("  " + "-" * 60)
    for label, pointer, objects in rows:
        print(f"  {label:<22}{pointer:>18}{objects:>20}")
    print("  " + "-" * 60)
    print()
    print("  Claude cites your retrieved chunks inline with a block-range pointer and stores zero objects,")
    print("  so your users' data never leaves the request and there is no hosted store to stand up first.")
    ran = [a for a in (oai, gem) if "skipped" not in a]
    if ran:
        extra = sum(a["cost"] for a in ran)
        print("  Competitor arms this run: $" + format(extra, ",.2f") + " across "
              + str(len(ran)) + " of 2 (OpenAI, Gemini), each store deleted on cleanup.")
    print()
