# VHS tape for the README recording (https://github.com/charmbracelet/vhs).
# Regenerate with:  make gif    (needs vhs, ffmpeg, and ttyd installed, plus both keys in .env)
# It records the cross-platform comparison on the quick preset, so the gif is a real live run.

Output docs/demo.gif

Set FontSize 14
Set Width 1320
Set Height 940
Set Padding 16

Type ".venv/bin/python run.py compare --quick"
Enter
Sleep 55s
