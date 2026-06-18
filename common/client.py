"""The shared client and environment loader.

No dependency on python-dotenv: a forked repo runs with nothing but ``anthropic`` installed.
"""

from __future__ import annotations

import os
import pathlib

from anthropic import Anthropic


def repo_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parent.parent


def load_env() -> None:
    """Load ANTHROPIC_API_KEY from a local .env if it is not already in the environment."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return
    env = repo_root() / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def get_client() -> Anthropic:
    load_env()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit(
            "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and paste your key, "
            "or export it. Get one at https://console.anthropic.com/."
        )
    return Anthropic()


def fmt_usd(x: float) -> str:
    return f"${x:,.6f}" if x < 0.01 else f"${x:,.4f}"


def managed_client() -> Anthropic:
    """An Anthropic client for the Managed Agents live paths. The SDK sets the managed-agents beta
    header automatically, so the construction lives here once and both live runtimes share it."""
    return Anthropic()
