"""consolekit.show() with text, HTML, an image and (if installed) a chart.

The extras dock minimised: they stack up the right edge as squares. Tap
one to open it.
"""
import os
import sys

import ui

# Find consolekit.py one folder up when run from the repo.
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
    consolekit.show(figure, title='Chart', icon='📈').minimise()
except ImportError:
    pass

consolekit.show(ui.Image.named('test:Lenna'), title='Image', icon='🖼').minimise()
consolekit.show(HTML, title='HTML', icon='🌐').minimise()
consolekit.show(consolekit.__doc__, title='consolekit')