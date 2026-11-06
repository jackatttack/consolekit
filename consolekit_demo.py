"""ConsoleKit demo: run this, then tap an example to dock it in the console.

Each example is a short script in the examples folder. Open one, change
it, and run it again. Opening an example tucks this menu into the tray;
tap its square to come back.
"""
import os
import runpy

import ui

import consolekit

HERE = os.path.dirname(os.path.abspath(__file__))
EXAMPLES = (
    ('👋', 'Hello', 'hello.py'),
    ('🔢', 'Counter', 'counter.py'),
    ('⏱', 'Stopwatch', 'stopwatch.py'),
    ('📝', 'Notes', 'notes.py'),
    ('🔍', 'Live updates', 'live_show.py'),
    ('🧩', 'Show anything', 'show_anything.py'),
)
HINT = 'Tap an example. Each one is a short script in examples/.'
HINT_HEIGHT = 34
ROW_HEIGHT = 46
GAP = 8


class Menu(ui.View):
    def __init__(self):
        # Kept on self, because the script's globals are cleared when it ends.
        self.run_path = runpy.run_path
        self.close_all = consolekit.close_all
        self.examples_folder = os.path.join(HERE, 'examples')
        self.join = os.path.join
        self.hint = ui.Label()
        self.hint.text = HINT
        self.hint.font = ('Menlo', 12)
        self.hint.text_color = '#9a9da6'
        self.hint.number_of_lines = 2
        self.add_subview(self.hint)
        self.buttons = []
        for icon, name, file_name in EXAMPLES:
            self.add_row('%s  %s' % (icon, name),
                         lambda sender, file_name=file_name: self.run_example(file_name))
        self.add_row('✕  Close all panels', lambda sender: self.close_all())

    def add_row(self, title, action):
        button = ui.Button()
        button.title = title
        button.font = ('Menlo-Bold', 16)
        button.tint_color = consolekit.COLOURS['text']
        button.background_color = consolekit.COLOURS['header']
        button.corner_radius = 10
        button.action = action
        self.add_subview(button)
        self.buttons.append(button)

    @ui.in_background
    def run_example(self, file_name):
        # Off the main thread, like pressing the play button, so a slow
        # import (matplotlib) or a loop never freezes the console.
        self.run_path(self.join(self.examples_folder, file_name), run_name='__main__')

    def layout(self):
        self.hint.frame = (GAP, 0, self.width - 2 * GAP, HINT_HEIGHT)
        for index, button in enumerate(self.buttons):
            button.frame = (GAP, HINT_HEIGHT + index * (ROW_HEIGHT + GAP),
                            self.width - 2 * GAP, ROW_HEIGHT)


rows = len(EXAMPLES) + 1
height = consolekit.HEADER_HEIGHT + HINT_HEIGHT + rows * (ROW_HEIGHT + GAP)
consolekit.dock(Menu(), title='ConsoleKit demo', icon='🧰', height=height)