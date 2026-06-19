"""grounding_stack: cite a text doc, a PDF, and a RAG chunk in ONE Claude request.

A doc-QA agent often answers over more than one kind of source at once: a plain-text
note, a PDF the user just uploaded, and a chunk your own retriever returned. In one
client.messages.create call you supply all three with citations enabled, and Claude
cites each with the location type that fits it: char_location for the text, page_location
for the PDF, and search_result_location for the chunk. One request, three typed pointers
back into the user's own content, no vector store and no upload step.

  run a live demo:   python run.py
  self-test (~$0.01): python run.py --check

Cost: the three-source Claude request runs for about $0.01 on Haiku 4.5.
Doc: https://platform.claude.com/docs/en/build-with-claude/citations
"""

from __future__ import annotations

import argparse
import base64
import struct
import sys
import time
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from .common.models import get
from .common.pricing import cost_usd

CLAUDE_MODEL = "haiku"
MAX_TOKENS = 600

# Three inline sources, each holding ONE disjoint fact, so a correct answer must cite that source.
TEXT_FACT = "Data residency: customer data for EU organizations is stored exclusively in Frankfurt."
PDF_FACT = "The Pro Plan carries a monthly uptime commitment of 99.9 percent."
CHUNK_TITLE = "Rate limits"
CHUNK_FACT = "The Growth plan API rate limit is 600 requests per minute."
QUESTION = (
    "Answer all three, each on its own line, and cite the source for each: "
    "(1) where EU customer data is stored, "
    "(2) the monthly uptime commitment percentage, "
    "(3) the API rate limit in requests per minute."
)
# What a correct answer must contain, per part.
TOKENS = ("Frankfurt", "99.9", "600")
EXPECTED_KINDS = {"char_location", "page_location", "search_result_location"}


def _make_pdf(line: str) -> bytes:
    """A minimal one-page PDF carrying one line of extractable text, standard library only."""
    def obj(n: int, body: bytes) -> bytes:
        return f"{n} 0 obj\n".encode() + body + b"\nendobj\n"

    stream = b"BT /F1 12 Tf 72 720 Td (" + line.encode("latin-1", "replace") + b") Tj ET"
    objs = [
        obj(1, b"<< /Type /Catalog /Pages 2 0 R >>"),
        obj(2, b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>"),
        obj(3, b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
               b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"),
        obj(4, b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"),
        obj(5, b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"),
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for o in objs:
        offsets.append(len(out))
        out += o
    xref = len(out)
    out += b"xref\n0 " + str(len(objs) + 1).encode() + b"\n0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (b"trailer\n<< /Size " + str(len(objs) + 1).encode() + b" /Root 1 0 R >>\n"
            b"startxref\n" + str(xref).encode() + b"\n%%EOF\n")
    # silence the unused-import linters on platforms that strip them; struct/zlib kept for parity
    _ = (struct, zlib)
    return out


def _run_once(client):
    """One request carrying all three mixed inline sources, citations on each. Returns
    (answered, pointer_kinds, cost, latency, text)."""
    m = get(CLAUDE_MODEL)
    pdf_b64 = base64.standard_b64encode(_make_pdf(PDF_FACT)).decode("ascii")
    content = [
        {"type": "document",
         "source": {"type": "text", "media_type": "text/plain", "data": TEXT_FACT},
         "title": "Residency note", "citations": {"enabled": True}},                  # add this
        {"type": "document",
         "source": {"type": "base64", "media_type": "application/pdf", "data": pdf_b64},
         "title": "Pro Plan Agreement", "citations": {"enabled": True}},              # add this
        {"type": "search_result", "source": "kb://ratelimit", "title": CHUNK_TITLE,
         "content": [{"type": "text", "text": CHUNK_FACT}], "citations": {"enabled": True}},  # add this
        {"type": "text", "text": QUESTION},
    ]
    t0 = time.perf_counter()
    r = client.messages.create(model=m.id, max_tokens=MAX_TOKENS,
                               messages=[{"role": "user", "content": content}])
    latency = time.perf_counter() - t0
    text = "".join(b.text for b in r.content if getattr(b, "type", None) == "text")
    answered = sum(1 for tok in TOKENS if tok.lower() in text.lower())
    kinds = set()
    for b in r.content:
        if getattr(b, "type", None) == "text":
            for ci in (getattr(b, "citations", None) or []):
                k = getattr(ci, "type", None)
                if k in EXPECTED_KINDS:
                    kinds.add(k)
    return answered, sorted(kinds), cost_usd(CLAUDE_MODEL, r.usage), latency, text


def _print_table(answered, kinds, cost, latency):
    m = get(CLAUDE_MODEL)
    print(f"\n  model: {m.id}   (one request, three mixed inline sources, citations on each)")
    print(f"  {'metric':<34}{'result':>22}")
    print("  " + "-" * 54)
    print(f"  {'parts answered correctly':<34}{f'{answered}/3':>22}")
    print(f"  {'source types cited in 1 request':<34}{f'{len(kinds)}/3':>22}")
    print(f"  {'pointer kinds':<34}{'+'.join(k.replace('_location','') for k in kinds):>22}")
    print(f"  {'hosted vector-store objects':<34}{'0':>22}")
    print(f"  {'cost':<34}{f'${cost:.4f}':>22}")
    print(f"  {'wall time':<34}{f'{latency:.1f}s':>22}")


def cmd_run(client) -> int:
    print("\n  grounding_stack: text + PDF + RAG chunk, each cited, in ONE request.")
    print("  upfront estimate: about $0.01, about 3s on Haiku 4.5.")
    answered, kinds, cost, latency, _ = _run_once(client)
    _print_table(answered, kinds, cost, latency)
    return 0


def cmd_check(client) -> int:
    print("\n  --check: one request must answer 3/3 and return all three typed pointers.")
    print("  upfront estimate: about $0.01 on Haiku 4.5.")
    answered, kinds, cost, latency, _ = _run_once(client)
    _print_table(answered, kinds, cost, latency)
    assert answered == 3, f"expected 3/3 answered, got {answered}/3"
    assert set(kinds) == EXPECTED_KINDS, f"expected {sorted(EXPECTED_KINDS)} pointers, got {kinds}"
    print(f"\n  PASS: 3/3 answered, all three pointer types in one request, $0 hosted objects, ${cost:.4f}.")
    return 0


def main(argv=None) -> int:
    from .common.client import get_client

    p = argparse.ArgumentParser(description="grounding_stack: cite text + PDF + RAG chunk in one request.")
    p.add_argument("--check", action="store_true", help="assert the win invariant for a few cents")
    a = p.parse_args(argv)
    client = get_client()
    return cmd_check(client) if a.check else cmd_run(client)


if __name__ == "__main__":
    raise SystemExit(main())
