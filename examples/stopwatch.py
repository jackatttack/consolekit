"""A live stopwatch docked in the console.

update() keeps ticking after the script ends. Minimise it with the header
button; tap the square to bring it back.
"""
import os
import sys
import time

import ui

# Finds consolekit.py one folder up, so the examples run from this folder.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import consolekit


class Stopwatch(ui.View):
    def __init__(self):
        # Kept on self: Pythonista clears the script's globals (like time)
        # when it ends, but update() keeps running.
        self.clock = time.time
        self.started = self.clock()
        self.label = ui.Label()
        self.label.font = ('Menlo-Bold', 40)
        self.label.alignment = ui.ALIGN_CENTER
        self.label.text_color = 'white'
        self.add_subview(self.label)
        self.update_interval = 0.1

    def layout(self):
        self.label.frame = self.bounds

    def update(self):
        self.label.text = '%.1f s' % (self.clock() - self.started)


consolekit.dock(Stopwatch(), title='Stopwatch', icon='⏱', height=160)