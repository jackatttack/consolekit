"""ConsoleKit demo: run this, then tap an example to dock it in the console.

Each example is a short script in the examples folder. Open one, change
it, and run it again. Opening an example tucks this menu into the tray;
tap its square to come back.
"""
import os
import runpy
import sys

import ui

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import consolekit

EXAMPLES = (
    ('👋', 'Hello', 'hello.py'),
    ('🔢', 'Counter', 'counter.py'),
    ('⏱', 'Stopwatch', 'stopwatch.py'),
    ('🧩', 'Show anything', 'show_anything.py'),
)
ROW_HEIGHT = 50
GAP = 10


class Menu(ui.View):
    def __init__(self):
        # Kept on self, because the script's globals are cleared when it ends.
        self.run_path = runpy.run_path
        self.examples_folder = os.path.join(HERE, 'examples')
        self.join = os.path.join
        self.buttons = []
        for icon, name, file_name in EXAMPLES:
            button = ui.Button()
            button.title = '%s  %s' % (icon, name)
            button.font = ('Menlo-Bold', 16)
            button.tint_color = consolekit.COLOURS['text']
            button.background_color = consolekit.COLOURS['header']
            button.corner_radius = 10
            button.action = lambda sender, file_name=file_name: self.run_example(file_name)
            self.add_subview(button)
            self.buttons.append(button)

    def run_example(self, file_name):
        self.run_path(self.join(self.examples_folder, file_name), run_name='__main__')

    def layout(self):
        for index, button in enumerate(self.buttons):
            button.frame = (GAP, GAP + index * (ROW_HEIGHT + GAP),
                            self.width - 2 * GAP, ROW_HEIGHT)


height = consolekit.HEADER_HEIGHT + GAP + len(EXAMPLES) * (ROW_HEIGHT + GAP)
consolekit.dock(Menu(), title='ConsoleKit demo', icon='🧰', height=height)
print('Tap an example in the panel. Each one is a short script in examples/.')