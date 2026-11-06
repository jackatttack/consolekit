"""The smallest consolekit panel: one label in the console."""
import ui

import consolekit

label = ui.Label()
label.text = 'Hello from the console 👋'
label.alignment = ui.ALIGN_CENTER
label.text_color = 'white'

consolekit.dock(label, title='Hello', height=140)