"""Buttons that do something: a counter docked in the console.

Everything the buttons need lives on self. When your script finishes,
Pythonista clears its global names, but the panel keeps running.
"""
import ui

import consolekit


class Counter(ui.View):
    def __init__(self):
        self.count = 0
        self.label = ui.Label()
        self.label.font = ('Menlo-Bold', 44)
        self.label.alignment = ui.ALIGN_CENTER
        self.label.text_color = 'white'
        self.add_subview(self.label)
        self.buttons = [
            self.make_button('−', -1),
            self.make_button('+', 1),
            self.make_button('Reset', None),
        ]
        self.show_count()

    def make_button(self, title, step):
        button = ui.Button()
        button.title = title
        button.font = ('Menlo-Bold', 20)
        button.tint_color = 'white'
        button.background_color = '#2c303a'
        button.corner_radius = 10
        button.action = lambda sender: self.change(step)
        self.add_subview(button)
        return button

    def change(self, step):
        self.count = 0 if step is None else self.count + step
        self.show_count()

    def show_count(self):
        self.label.text = str(self.count)

    def layout(self):
        gap = 10
        button_width = (self.width - 4 * gap) / 3
        self.label.frame = (0, 0, self.width, self.height - 70)
        for index, button in enumerate(self.buttons):
            button.frame = (gap + index * (button_width + gap), self.height - 60,
                            button_width, 48)


consolekit.dock(Counter(), title='Counter', icon='🔢', height=240)