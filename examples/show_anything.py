"""consolekit.show() with text, HTML, an image and (if installed) a chart.

Each one opens and tucks the one before it into the tray along the bottom.
Tap a square to switch.
"""
import os
import sys

import ui

# Finds consolekit.py one folder up, so the examples run from this folder.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import consolekit

HTML = '''
<body style="background:#16181d;color:#e6e6e6;font-family:Menlo;padding:12px">
<h2 style="color:#e8335a">Hello from a WebView</h2>
<p>Any HTML string becomes a page docked in the console.</p>
</body>
'''

try:
    import matplotlib.pyplot as plt
    figure = plt.figure(figsize=(5, 3))
    xs = [i / 10 for i in range(100)]
    plt.plot(xs, [x * x % 7 for x in xs])
    consolekit.show(figure, icon='📈')
except ImportError:
    pass

consolekit.show(ui.Image.named('test:Lenna'), icon='🖼')
consolekit.show(HTML, icon='🌐')
consolekit.show(consolekit.__doc__, title='consolekit')