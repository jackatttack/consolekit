"""The smallest consolekit panel: one label in the console."""
import os
import sys

import ui

# Finds consolekit.py one folder up, so the examples run from this folder.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import consolekit

label = ui.Label()
label.text = 'Hello from the console 👋'
label.alignment = ui.ALIGN_CENTER
label.text_color = 'white'

consolekit.dock(label, title='Hello', height=140)