"""Typing in a docked panel: a quick list of notes.

Tap the field, type a note and press return. The field sits at the top of
the panel so the keyboard never covers it. The 🗑 button in the header
was added with panel.add_button().
"""
import ui

import consolekit


class Notes(ui.View):
    def __init__(self):
        self.notes = []
        self.field = ui.TextField()
        self.field.placeholder = 'Type a note, then return'
        self.field.font = ('Menlo', 16)
        self.field.text_color = 'white'
        self.field.background_color = '#2c303a'
        self.field.corner_radius = 8
        self.field.action = self.add_note        # runs when editing ends
        self.add_subview(self.field)
        self.list = ui.TextView()
        self.list.editable = False
        self.list.font = ('Menlo', 15)
        self.list.text_color = 'white'
        self.list.background_color = (0, 0, 0, 0)
        self.add_subview(self.list)
        self.show_notes()

    def add_note(self, sender):
        text = self.field.text.strip()
        if text:
            self.notes.append(text)
            self.field.text = ''
            self.show_notes()

    def clear_notes(self):
        self.notes = []
        self.show_notes()

    def show_notes(self):
        if self.notes:
            self.list.text = '\n'.join('• ' + note for note in self.notes)
        else:
            self.list.text = 'No notes yet.'

    def layout(self):
        gap = 10
        self.field.frame = (gap, gap, self.width - 2 * gap, 40)
        self.list.frame = (gap, 60, self.width - 2 * gap, self.height - 70)


panel = consolekit.dock(Notes(), title='Notes', icon='📝', height=300)
# The action only uses its argument, so it still works after the script
# ends and its global names are cleared.
panel.add_button('🗑', lambda panel: panel.content.clear_notes())