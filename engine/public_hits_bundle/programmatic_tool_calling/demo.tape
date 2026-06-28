# VHS tape for the programmatic_tool_calling artifact gif (https://github.com/charmbracelet/vhs).
# Regenerate from the repo root with:  make gif    (needs vhs and ffmpeg).
# It replays the committed receipt (programmatic_tool_calling/sample.txt) for $0, so the gif is reproducible.
# A republish regenerates this tape, and the gif binary is rendered from it by make gif.
Output programmatic_tool_calling/demo.gif

Set FontSize 16
Set Width 1200
Set Height 640
Set Padding 18

Hide
Type "make() { cat programmatic_tool_calling/sample.txt; }"
Enter
Type "clear"
Enter
Show

Type "# Meter usage per cohort: token cost of the answer, not every tool output"
Enter
Sleep 1200ms
Type "make programmatic_tool_calling"
Enter
Sleep 3s
