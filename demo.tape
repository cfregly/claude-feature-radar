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

Type "# programmatic tool calling: 74% fewer billed input tokens on a customer-evidence fan-out task"
Enter
Sleep 700ms
Type "make programmatic-tool-calling   # about $0.08 on a real run; below is the committed receipt, replayed for $0"
Enter
Sleep 700ms
Type `printf '\n  Task: from support tickets, product logs, usage, CRM notes, and compliance docs,\n  find the three customer accounts most likely to churn or block expansion.\n\n  mode                                      billed input tok    what happens to the evidence rows\n  --------------------------------------------------------------------------------------------\n  plain tool use                                      54,989    all rows flow through the model context\n  programmatic (allowed_callers)                      14,299    sandbox reduces, only the compact packet returns\n  --------------------------------------------------------------------------------------------\n  -> 74%% fewer billed input tokens, with acct_1842, acct_2199, and acct_7731 returned.\n\n  full receipt: edges/programmatic-tool-calling/sample.txt\n\n'`
Enter
Sleep 2200ms
