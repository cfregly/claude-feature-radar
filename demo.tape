# VHS tape for the README recording (https://github.com/charmbracelet/vhs).
# Regenerate with:  make gif    (needs vhs and ffmpeg installed).
# It replays the committed receipt from a real `make programmatic-tool-calling` run (edges/programmatic-tool-calling/sample.txt),
# so the gif always shows the full result for $0. A live run makes real API calls that take minutes and
# rate-limit, too slow and nondeterministic for a clean recording. To record a fresh live run instead,
# swap the printf block for:  make programmatic-tool-calling    (needs ANTHROPIC_API_KEY).

Output docs/demo.gif

Set FontSize 18
Set Width 1180
Set Height 640
Set Padding 14
Set TypingSpeed 0.004

Type "# programmatic tool calling: about 28% fewer billed input tokens on a fan-out task"
Enter
Sleep 700ms
Type "make programmatic-tool-calling   # about $0.08 on a real run; below is the committed receipt, replayed for $0"
Enter
Sleep 700ms
Type `printf '\n  Task: across 4 regions (240 sales rows total), find the highest-revenue region.\n  Same task, same model (Sonnet 4.6), both ways.\n\n  mode                                      billed input tok    what happens to the 240 rows\n  --------------------------------------------------------------------------------------------\n  plain tool use                                       9,451    all 240 rows flow through the model context\n  programmatic (allowed_callers)                       6,828    the sandbox aggregates, only the answer (east) reaches the model\n  --------------------------------------------------------------------------------------------\n  -> 28%% fewer billed input tokens, and the sandbox returns the exact winner (east).\n\n  full receipt: edges/programmatic-tool-calling/sample.txt\n\n'`
Enter
Sleep 2200ms
