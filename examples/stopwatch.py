"""A live stopwatch docked in the console.

update() keeps ticking after the script ends. The panel_opened and
panel_tucked hooks let it skip redrawing while it waits in the tray; the
time keeps counting. Minimise it with the header button, tap its square
to bring it back.
"""
import time

import ui

import consolekit


class Stopwatch(ui.View):
    def __init__(self):
        # Kept on self: Pythonista clears the script's globals (like time)
        # when it ends, but update() keeps running.
        self.clock = time.time
        self.started = self.clock()
        self.showing = True
        self.label = ui.Label()
        self.label.font = ('Menlo-Bold', 40)
        self.label.alignment = ui.ALIGN_CENTER
        self.label.text_color = 'white'
        self.add_subview(self.label)
        self.update_interval = 0.1

    def layout(self):
        self.label.frame = self.bounds

    def update(self):
        if self.showing:
            self.label.text = '%.1f s' % (self.clock() - self.started)

    # consolekit calls these when your view has them.
    def panel_opened(self, panel):
        self.showing = True

    def panel_tucked(self, panel):
        self.showing = False


consolekit.dock(Stopwatch(), title='Stopwatch', icon='⏱', height=160)