"""The MCP server: drive the engine from a chat window (Claude Code or Claude Desktop) over stdio.

This is the thin wrapper. It is the one file that imports the MCP Python SDK (the optional `mcp`
dependency in requirements-mcp.txt), and it does nothing but register the engine.mcp_tools functions
as MCP tools and run the stdio transport. All the logic, and the whole gate boundary, live in
engine/mcp_tools.py, which imports no SDK, so the one-dependency gate and the offline boundary test
never need the MCP package.

MCP and the SDK, grounded against the live docs on 2026-06-20:
  - FastMCP, the high-level server, exposes a tool with the @mcp.tool() decorator. Parameter type
    hints become the input schema, the return type hint becomes the structured output schema, and the
    docstring becomes the tool description the client shows. Source:
    https://github.com/modelcontextprotocol/python-sdk (README, checked 2026-06-20).
  - stdio is the default transport and the standard for Claude Code and Claude Desktop. mcp.run() runs
    it, and passing transport="stdio" is the explicit form. Source: the same SDK README, checked
    2026-06-20.
  - The MCP tool-safety annotations (readOnlyHint, destructiveHint) are not yet exposed through the
    Python SDK decorator as of 2026-06-20, so the safety boundary here is structural, not a hint: the
    ASK tools refuse until confirm=True and the NEVER actions are simply not exposed. That matches the
    engine's own posture, where the boundary is the absence of the capability, not a flag.

Run it:
    make mcp                         (installs nothing; needs `make mcp-deps` once first)
    python -m engine.mcp_server      (from the engine repo root)
    python /ABS/PATH/engine/mcp_server.py   (any working directory; the repo root is put on sys.path)

The README "Drive the engine from a chat window" section has the exact `claude mcp add` and Claude
Desktop registration steps and the trigger phrases.
"""

from __future__ import annotations

import pathlib
import sys

# Put the engine repo root on sys.path so this runs both as a module (python -m engine.mcp_server) and
# as a file with an absolute path (what Claude Desktop's config does), regardless of the caller's cwd.
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from mcp.server.fastmcp import FastMCP
except ModuleNotFoundError as exc:  # pragma: no cover - the helpful failure path
    raise SystemExit(
        "The MCP server needs the optional `mcp` package, which is not installed. It is kept out of "
        "the one-dependency core path on purpose. Install it with `make mcp-deps` (or `pip install "
        "-r requirements-mcp.txt`) into the same .venv, then run `make mcp` again."
    ) from exc

from engine import mcp_tools  # noqa: E402  the SDK-free logic + gate boundary

mcp = FastMCP("claude-feature-radar")


# --------------------------------------------------------------------------- read tools (ALWAYS, $0)


@mcp.tool()
def list_edges(leads_only: bool = False, verdict: str = "", limit: int = 0) -> dict:
    """List the ranked Claude-vs-competitor edges from the committed landscape. Read-only and free.

    Each row carries the verdict (claude-ahead, parity, claude-behind, never-evaluated), the
    genuine-lead basis and score, the value score, the axis a founder prices (cost, speed,
    reliability, grounding), the demoKind, the source doc URL, and the reproduction command and
    estimate when one exists. Rows come back sorted by score, highest first.

    Args:
        leads_only: keep only genuine leads (lead_score greater than 0).
        verdict: keep only one verdict, for example "claude-ahead". Empty means all.
        limit: cap the number of rows. 0 means all.
    """
    return mcp_tools.list_edges(leads_only=leads_only, verdict=verdict, limit=limit)


@mcp.tool()
def show_landscape() -> dict:
    """Summarize the edge landscape: the as-of date, the total edge count, counts by verdict, the top
    genuine leads, and how many coverage gaps the engine surfaces about itself. Read-only and free. A
    fast orientation before deciding which edge to publish or benchmark."""
    return mcp_tools.show_landscape()


@mcp.tool()
def show_coverage(ledger_tail: int = 12) -> dict:
    """Show what the engine can prove today: the per-demoKind coverage (registered demonstrator, built
    bundle, where the code came from, which spend lane), plus the tail of the committed coverage ledger
    so you see what the stream has already drafted and dispatched. Read-only and free.

    Args:
        ledger_tail: how many recent ledger rows to include. 0 means none.
    """
    return mcp_tools.show_coverage(ledger_tail=ledger_tail)


@mcp.tool()
def show_boundary() -> dict:
    """Show the safety boundary, for inspection from chat. Returns the engine gate lanes (the actions
    that always run unattended, those that wait for you, and those refused by design), the per-tool
    tier mapping this server exposes, and the audit over what an unattended caller can do without a
    confirmation token, which must be empty. The send, post, and push actions appear in the lanes but
    map to no tool: the boundary is the absence of the capability. Read-only and free."""
    return mcp_tools.show_boundary()


@mcp.tool()
def run_discovery(sweep: bool = True) -> dict:
    """Run the $0 discovery loop and report what changed. This is the safe, unattended-tier heart of
    the engine: it sweeps the live docs, diffs against the last run, ranks edges by value times genuine
    lead, drafts the newest uncovered lead into the inert outbox, updates the coverage ledger, writes
    the run manifest, and audits the boundary. It spends nothing, sends nothing, and pushes nothing,
    and the returned audit_violations list must be empty.

    Args:
        sweep: True (the default) does the live read-only doc fetch over the network (the full loop).
            False reuses the last committed landscape with no network at all. Both are free.
    """
    return mcp_tools.run_discovery(sweep=sweep)


# --------------------------------------------------------------------------- ASK tools (confirm-gated)


@mcp.tool()
def publish_brief(edge: str, confirm: bool = False) -> dict:
    """Generate a public, self-contained brief for a verified-win edge. ASK tier: it writes files into
    the sibling public briefs repo, so it does nothing until you pass confirm=true.

    Call it first with confirm=false (the default) to preview: it runs the fail-closed verdict gate
    and tells you whether the edge would publish and why, writing nothing. Call it again with
    confirm=true to actually write the brief. It never pushes a remote and never sends anything, so
    after it writes you review the diff and push by hand if you want it public. The verdict gate
    refuses any edge that is not a clean, ranked, non-regime-bounded Claude win, and a refusal writes
    nothing.

    Args:
        edge: the edge key, for example "programmatic-tool-calling" or "citations".
        confirm: must be true to write files. False returns a preview only.
    """
    return mcp_tools.publish_brief(edge=edge, confirm=confirm)


@mcp.tool()
def run_benchmark(edge: str, confirm: bool = False, max_usd: float = mcp_tools.DEFAULT_MAX_USD) -> dict:
    """Run a paid proof for an edge against real API calls. ASK tier: it spends real credits on your
    ANTHROPIC_API_KEY, so it surfaces the dollar estimate first and does nothing until you pass
    confirm=true.

    Call it first with confirm=false (the default) to see the estimate (the command, the dollar cost,
    the wall time) and the cap, spending nothing. Call it again with confirm=true to run it. Before any
    spend it enforces the cap: an estimate over max_usd is refused and asks you to raise the cap by
    hand, and an estimate over the hard ceiling is refused outright. A runaway benchmark is killed
    after a fixed timeout. It never sends and never pushes.

    Args:
        edge: the edge key whose reproduction command to run, for example "programmatic-tool-calling".
        confirm: must be true to spend. False returns the estimate only.
        max_usd: the per-call dollar cap. An estimate over it is refused until you raise it.
    """
    return mcp_tools.run_benchmark(edge=edge, confirm=confirm, max_usd=max_usd)


def main() -> None:
    """Run the server over stdio, the transport Claude Code and Claude Desktop speak."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
