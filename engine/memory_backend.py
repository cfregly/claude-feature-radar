"""Client-side handler for the Claude memory tool (`memory_20250818`).

The model issues memory commands (view, create, str_replace, insert, delete, rename) and this
class runs them as file operations under a sandboxed root, returning the strings the tool
contract documents. Paths are confined to the root: a command that escapes it is refused.

Source for the command set and return strings:
https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool
"""

from __future__ import annotations

import pathlib
import shutil


class MemoryBackend:
    def __init__(self, root: str | pathlib.Path):
        self.root = pathlib.Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, path: str) -> pathlib.Path | None:
        """Map a model-supplied /memories path to a real path under root, or None if it escapes."""
        rel = str(path).lstrip("/")
        if rel.startswith("memories/"):
            rel = rel[len("memories/"):]
        elif rel == "memories":
            rel = ""
        full = (self.root / rel).resolve()
        if full != self.root and not str(full).startswith(str(self.root) + "/"):
            return None
        return full

    def handle(self, tool_input: dict) -> str:
        cmd = tool_input.get("command")
        try:
            if cmd == "view":
                return self._view(tool_input)
            if cmd == "create":
                return self._create(tool_input)
            if cmd == "str_replace":
                return self._str_replace(tool_input)
            if cmd == "insert":
                return self._insert(tool_input)
            if cmd == "delete":
                return self._delete(tool_input)
            if cmd == "rename":
                return self._rename(tool_input)
            return f"Error: unknown memory command {cmd!r}"
        except Exception as e:  # noqa: BLE001 - report errors back to the model as text
            return f"Error: {e}"

    def _view(self, t: dict) -> str:
        path = t["path"]
        full = self._resolve(path)
        if full is None:
            return f"Error: path {path} is outside /memories"
        if full.is_dir():
            lines = [f"Directory listing of {path}:"]
            for item in sorted(full.rglob("*")):
                if item.name.startswith("."):
                    continue
                rel = item.relative_to(self.root)
                lines.append(f"  /memories/{rel}" + ("/" if item.is_dir() else ""))
            if len(lines) == 1:
                lines.append("  (empty)")
            return "\n".join(lines)
        if not full.exists():
            return f"Error: the path {path} does not exist"
        text = full.read_text()
        out = [f"Here's the content of {path} with line numbers:"]
        for i, line in enumerate(text.splitlines(), 1):
            out.append(f"{i:6d}\t{line}")
        return "\n".join(out)

    def _create(self, t: dict) -> str:
        path = t["path"]
        full = self._resolve(path)
        if full is None:
            return f"Error: path {path} is outside /memories"
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(t.get("file_text", ""))
        return f"File created successfully at: {path}"

    def _str_replace(self, t: dict) -> str:
        path = t["path"]
        full = self._resolve(path)
        if full is None or not full.exists():
            return f"Error: the path {path} does not exist. Please provide a valid path."
        content = full.read_text()
        old = t["old_str"]
        if old not in content:
            return f"No replacement was performed, old_str did not appear verbatim in {path}."
        if content.count(old) > 1:
            lines = [i + 1 for i, ln in enumerate(content.splitlines()) if old in ln]
            return (
                f"No replacement was performed. Multiple occurrences of old_str in lines: "
                f"{lines}. Please ensure it is unique."
            )
        full.write_text(content.replace(old, t["new_str"]))
        return "The memory file has been edited."

    def _insert(self, t: dict) -> str:
        path = t["path"]
        full = self._resolve(path)
        if full is None or not full.exists():
            return f"Error: the path {path} does not exist"
        lines = full.read_text().splitlines(keepends=True)
        n = t["insert_line"]
        if n < 0 or n > len(lines):
            return (
                f"Error: Invalid insert_line parameter: {n}. It should be within the range "
                f"of lines of the file: [0, {len(lines)}]"
            )
        text = t["insert_text"]
        if not text.endswith("\n"):
            text += "\n"
        lines.insert(n, text)
        full.write_text("".join(lines))
        return f"The file {path} has been edited."

    def _delete(self, t: dict) -> str:
        path = t["path"]
        full = self._resolve(path)
        if full is None or not full.exists():
            return f"Error: the path {path} does not exist"
        if full.is_dir():
            shutil.rmtree(full)
        else:
            full.unlink()
        return f"Successfully deleted {path}"

    def _rename(self, t: dict) -> str:
        old_full = self._resolve(t["old_path"])
        new_full = self._resolve(t["new_path"])
        if old_full is None or new_full is None:
            return "Error: a path is outside /memories"
        if not old_full.exists():
            return f"Error: the path {t['old_path']} does not exist"
        if new_full.exists():
            return f"Error: the destination {t['new_path']} already exists"
        new_full.parent.mkdir(parents=True, exist_ok=True)
        old_full.rename(new_full)
        return f"Successfully renamed {t['old_path']} to {t['new_path']}"
