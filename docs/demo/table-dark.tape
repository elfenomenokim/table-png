Output docs/products/skills/feno-handoff/table-png/docs/demo/table-dark.gif
Set FontSize 18
Set Width 1200
Set Height 680
Set Padding 28
Set Theme "Catppuccin Mocha"
Set TypingSpeed 45ms
Set WindowBar Colorful
Set BorderRadius 10
Hide
Set TypingSpeed 0
Type "cd docs/products/skills/feno-handoff/table-png"
Enter
Type "alias table-png='PYTHONPATH=src python3 -m table_png'; clear"
Enter
Show
Set TypingSpeed 45ms
Type "cat docs/demo/status.md"
Sleep 350ms
Enter
Sleep 1s
Type "table-png docs/demo/status.md --out /tmp/table-demo-dark.png --title 'Status' --theme dark --width 720 --font-size 48"
Sleep 350ms
Enter
Sleep 2s
Type "python3 docs/demo/show_png.py /tmp/table-demo-dark.png"
Sleep 350ms
Enter
Sleep 3s
