"""Times-table flash cards: a whole console app in a dozen lines.

Tap 👀 for the answer and 🔀 for the next card. The shuffled deck lives on
the panel, so the buttons keep working after the script ends.
"""
import random

import consolekit


def deal(panel):
    panel.a, panel.b = panel.deck.pop() if panel.deck else (12, 12)
    panel.show(f'{panel.a} × {panel.b}')


def reveal(panel):
    panel.show(f'{panel.a} × {panel.b} = {panel.a * panel.b}')


panel = consolekit.show('Flash cards', title='Flash cards', icon='✖️', height=220)
panel.deck = random.sample([(a, b) for a in range(2, 13) for b in range(2, 13)], 121)
panel.add_button('👀', reveal)
panel.add_button('🔀', deal)
deal(panel)