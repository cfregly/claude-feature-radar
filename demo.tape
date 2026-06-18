# VHS tape for the README recording (https://github.com/charmbracelet/vhs).
# Regenerate with:  make gif    (needs vhs and ffmpeg installed).
# It replays the committed receipt from a real `make ptc` run (edges/programmatic-tool-calling/sample.txt),
# so the gif always shows the full result for $0. A live run makes real API calls that take minutes and
# rate-limit, too slow and nondeterministic for a clean recording. To record a fresh live run instead,
# swap the printf block for:  make ptc    (needs ANTHROPIC_API_KEY).

Output docs/demo.gif

Set FontSize 16
Set Width 1180
Set Height 640
Set Padding 18

Type "# programmatic tool calling: about 28% fewer billed input tokens on a fan-out task"
Enter
Sleep 1.2s
Type "make ptc   # about $0.06 on a real run; below is the committed receipt, replayed for $0"
Enter
Sleep 1.2s
Type `printf '\n  Task: across 4 regions (240 sales rows total), find the highest-revenue region.\n  Same task, same model (Sonnet 4.6), both ways. The answer must match.\n\n  mode                                      billed input tok    answer\n  ------------------------------------------------------------------------\n  plain tool use (240 rows through context)            9,451      None  (model summed in its head)\n  programmatic (rows filtered in the sandbox)          6,828      east  (the sandbox computed it)\n  ------------------------------------------------------------------------\n  -> 28%% fewer billed input tokens, and the sandbox code got the exact winner.\n\n  full receipt: edges/programmatic-tool-calling/sample.txt\n\n'`
Enter
Sleep 6s
