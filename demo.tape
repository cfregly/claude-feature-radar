# VHS tape for the README recording (https://github.com/charmbracelet/vhs).
# Regenerate with:  make gif    (needs vhs and ffmpeg installed).
# It replays the committed receipt from a real fair run (sample_compare.txt), so the gif always
# shows the full honest three-way table. A live run makes real API calls that take minutes and
# rate-limit, too slow and nondeterministic for a clean recording. To record a fresh live run
# instead, swap the cat for:  .venv/bin/python run.py compare    (needs all three keys).

Output docs/demo.gif

Set FontSize 14
Set Width 1320
Set Height 940
Set Padding 16

Type "# the fair three-way benchmark, the committed receipt from a real run on real keys:"
Enter
Sleep 1.5s
Type "cat sample_compare.txt"
Enter
Sleep 12s
