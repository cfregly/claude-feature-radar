# VHS tape for the programmatic_tool_calling_cache_context demo gif (https://github.com/charmbracelet/vhs).
# Regenerate from the repo root with:  make gif    (needs vhs and ffmpeg).
# It replays the committed receipt (programmatic_tool_calling_cache_context/sample.txt) for $0, so the gif is deterministic.
Output programmatic_tool_calling_cache_context/demo.gif

Set FontSize 16
Set Width 1200
Set Height 720
Set Padding 18

Hide
Type "make() { cat programmatic_tool_calling_cache_context/sample.txt; }"
Enter
Type "clear"
Enter
Show

Type "# programmatic tool calling keeps raw tool outputs out of the cached 1M-context loop"
Enter
Sleep 1200ms
Type "make programmatic_tool_calling_cache_context"
Enter
Sleep 3s
