# VHS tape for the README recording (https://github.com/charmbracelet/vhs).
# Regenerate with:  make gif    (needs vhs and ffmpeg installed).
# It replays the committed receipt from a real `make citations` run (sample_citations.txt), so the
# gif always shows the full result. A live run makes real API calls that take minutes and rate-limit,
# too slow and nondeterministic for a clean recording. To record a fresh live run instead, swap the
# cat for:  .venv/bin/python run.py citations    (needs all three keys).

Output docs/demo.gif

Set FontSize 14
Set Width 1320
Set Height 980
Set Padding 16

Type "# the verifiable-citations benchmark, the committed receipt from a real run on real keys:"
Enter
Sleep 1.5s
Type "cat sample_citations.txt"
Enter
Sleep 12s
