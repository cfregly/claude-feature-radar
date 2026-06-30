"""Turn a real ``usage`` object into token/API dollars, using only verified prices.

Nothing here estimates. It reads the token counts the API actually returned and multiplies by
the rates in models.py. Code execution runtime billing is tracked separately from token usage, so
this module does not claim an all-in production COGS number for programmatic tool calling or code-execution workloads.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import get

WEB_SEARCH_PER_REQUEST = 10.0 / 1000.0
BATCH_DISCOUNT = 0.5


def _field(usage, name: str) -> int:
    return getattr(usage, name, 0) or 0


@dataclass
class CostBreakdown:
    input: float
    output: float
    cache_read: float
    cache_write: float
    server_tool: float
    total: float

    def __str__(self) -> str:
        return (
            f"${self.total:.6f}  "
            f"(in ${self.input:.6f} + out ${self.output:.6f} + "
            f"cache_read ${self.cache_read:.6f} + cache_write ${self.cache_write:.6f} + "
            f"server_tool ${self.server_tool:.6f})"
        )


def cost_breakdown(model: str, usage) -> CostBreakdown:
    """Exact cost of one response, split by component.

    ``usage`` is the ``message.usage`` object from the SDK (or anything with the same fields).
    """
    m = get(model)
    in_tok = _field(usage, "input_tokens")
    out_tok = _field(usage, "output_tokens")
    read_tok = _field(usage, "cache_read_input_tokens")

    # Cache writes split into 5-minute and 1-hour buckets when the API reports them.
    cc = getattr(usage, "cache_creation", None)
    if cc is not None:
        w5 = _field(cc, "ephemeral_5m_input_tokens")
        w1 = _field(cc, "ephemeral_1h_input_tokens")
    else:
        w5 = _field(usage, "cache_creation_input_tokens")
        w1 = 0

    inp = in_tok * m.input_per_mtok / 1e6
    out = out_tok * m.output_per_mtok / 1e6
    read = read_tok * m.cache_read_per_mtok / 1e6
    write = (w5 * m.cache_write_5m_per_mtok + w1 * m.cache_write_1h_per_mtok) / 1e6
    server_tool = server_tool_cost_usd(usage)
    return CostBreakdown(inp, out, read, write, server_tool, inp + out + read + write + server_tool)


def cost_usd(model: str, usage) -> float:
    """Token/API dollar cost of one response, excluding code-execution runtime billing."""
    return cost_breakdown(model, usage).total


def batch_cost_usd(model: str, usage) -> float:
    """Total dollar cost of one Anthropic Message Batch response."""
    b = cost_breakdown(model, usage)
    token_cost = b.input + b.output + b.cache_read + b.cache_write
    return token_cost * BATCH_DISCOUNT + b.server_tool


def server_tool_cost_usd(usage) -> float:
    """Server-tool dollar cost that is knowable from the response usage object."""
    stu = getattr(usage, "server_tool_use", None)
    if stu is None:
        return 0.0
    web_search_requests = _field(stu, "web_search_requests")
    return web_search_requests * WEB_SEARCH_PER_REQUEST


def cost_from_buckets(model: str, *, fresh_input: int, cached: int, output: int) -> float:
    """Dollar cost from already-separated token buckets, reading the rates from the one registry.

    For the inclusive-input providers (OpenAI, Gemini) the reported input field already counts the
    cached tokens, so the caller passes fresh_input = reported_input - cached. The cached bucket bills
    at the model's cache-read rate (those providers' discounted cached-input tier), the fresh and
    output buckets at the input and output rates. This is the single cost model the optional OpenAI and Gemini comparison arms share, so a
    competitor price lives in exactly one place, common/models.py.
    """
    m = get(model)
    return (
        fresh_input * m.input_per_mtok
        + cached * m.cache_read_per_mtok
        + output * m.output_per_mtok
    ) / 1e6
