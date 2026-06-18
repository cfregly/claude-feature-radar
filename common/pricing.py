"""Turn a real ``usage`` object into real dollars, using only verified prices.

Nothing here estimates. It reads the token counts the API actually returned and multiplies by
the rates in models.py. That is what makes every dollar figure in this repo a receipt.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import get


def _field(usage, name: str) -> int:
    return getattr(usage, name, 0) or 0


@dataclass
class CostBreakdown:
    input: float
    output: float
    cache_read: float
    cache_write: float
    total: float

    def __str__(self) -> str:
        return (
            f"${self.total:.6f}  "
            f"(in ${self.input:.6f} + out ${self.output:.6f} + "
            f"cache_read ${self.cache_read:.6f} + cache_write ${self.cache_write:.6f})"
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
    return CostBreakdown(inp, out, read, write, inp + out + read + write)


def cost_usd(model: str, usage) -> float:
    """Total dollar cost of one response."""
    return cost_breakdown(model, usage).total
