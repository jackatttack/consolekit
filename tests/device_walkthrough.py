"""On-device walkthrough of every consolekit interaction.

Run it with the play button from the editor. It docks real panels in the
console, steps through opening, tucking, restoring, replacing, stacking,
updating and closing, and checks what the views actually did. Open panels
hide the console text, so the results print once everything is closed
again. They are also saved to device_walkthrough.log beside this file.

Afterwards it lists the few things only your eyes and fingers can check.
"""
import os
import sys
import time

import ui
from objc_util import on_main_thread

HERE = os.path.dirname(os.path.abspath(__file__))
PACKAGE = os.path.dirname(HERE)
if os.path.isfile(os.path.join(PACKAGE, 'consolekit.py')):
    # A source checkout: test the copy beside this folder, not the installed one.
    sys.path.insert(0, PACKAGE)
    sys.modules.pop('consolekit', None)
import consolekit as ck

STEP_SECONDS = 0.6           # long enough for every animation to settle
LOG_FILE = os.path.join(HERE, 'device_walkthrough.log')
BY_EYE = (
    'Run consolekit_demo.py, tap each example, then tap squares to switch.',
    'Notes: tap the field and type; the field stays clear of the keyboard.',
    'Rotate the device (or resize on iPad): panels and the tray refit.',
    'Several squares in the tray: scroll it; squares are cut straight at the ends.',
    'Only the tray showing: the newest console line sits above it.',
    'Switch Pythonista to a light theme: panels stay dark and readable.',
)

results = []
events = []


def check(name, passed):
    results.append((name, bool(passed)))


def pause():
    time.sleep(STEP_SECONDS)


def label(text):
    view = ui.Label()
    view.text = text
    view.alignment = ui.ALIGN_CENTER
    view.text_color = 'white'
    return view


@on_main_thread
def snapshot():
    """What the docked views are doing right now, read on the main thread."""
    store = ck.parts()
    text_view = ck.find_console_text_view()
    tagged = 0
    if text_view is not None:
        tagged = sum(1 for view in text_view.superview().subviews() if view.tag() == ck.VIEW_TAG)
    tray, backdrop, frame = store.get('tray'), store.get('backdrop'), store.get('frame')
    panels = {}
    for key, panel in ck.live_panels().items():
        x, y, width, height = panel.frame
        panels[key] = {'alpha': panel.alpha, 'minimised': panel.minimised,
                       'square': not panel.square.hidden, 'frame': (x, y, width, height)}
    return {
        'console': text_view is not None,
        'inset': text_view.contentInset().bottom if text_view is not None else None,
        'tagged': tagged,
        'tray': tray.alpha if tray is not None else 0,
        'backdrop': backdrop.alpha if backdrop is not None else 0,
        'tray_top': ck.tray_frame(frame)[1] if frame else None,
        'panels': panels,
    }


def overlaps(a, b):
    return a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


class Hooked(ui.View):
    def panel_opened(self, panel):
        events.append('opened')

    def panel_tucked(self, panel):
        events.append('tucked')

    def panel_closed(self, panel):
        events.append('closed')


def walk():
    ck.close_all()
    pause()
    start = snapshot()
    if not start['console']:
        check('found the console (run this in Pythonista, from the editor)', False)
        return
    start_inset = start['inset']

    # One panel.
    first = ck.dock(label('A'), title='Walk A', icon='A', height=160)
    pause()
    state = snapshot()
    check('a docked panel fades fully in', state['panels']['Walk A']['alpha'] == 1)
    check('the backdrop covers the console text', state['backdrop'] == 1)
    check('no tray while nothing is tucked', state['tray'] == 0)
    check('the console inset is untouched without a tray', state['inset'] == start_inset)

    # A second exclusive panel tucks the first.
    ck.dock(label('B'), title='Walk B', icon='B', height=160)
    pause()
    state = snapshot()
    a, b = state['panels']['Walk A'], state['panels']['Walk B']
    check('opening B tucks A away', a['minimised'] and a['alpha'] == 0)
    check("A's square shows in the tray", a['square'] and state['tray'] == 1)
    check('B sits above the tray',
          b['frame'][1] + b['frame'][3] <= state['tray_top'] - ck.TRAY_GAP + 0.5)
    check('the console inset grows to clear the tray', state['inset'] > start_inset)

    # What a tap on A's square does.
    first.square.touch_ended(None)
    pause()
    state = snapshot()
    check("tapping A's square brings A back and tucks B",
          not state['panels']['Walk A']['minimised'] and state['panels']['Walk B']['minimised'])

    # Rerunning a script replaces its panel.
    again = ck.dock(label('A again'), title='Walk A', height=160)
    pause()
    state = snapshot()
    check('docking the same title replaces the panel', ck.get('Walk A') is again)
    check('no stray views are left behind', state['tagged'] == len(state['panels']) + 2)

    # A minimised panel comes back minimised.
    again.minimise()
    pause()
    ck.dock(label('A third time'), title='Walk A', height=160)
    pause()
    check('a minimised panel comes back minimised on rerun',
          snapshot()['panels']['Walk A']['minimised'])

    # Side by side.
    ck.close_all()
    pause()
    check('close_all forgets minimised panels', not ck.remembered('Walk A')['minimised'])
    ck.dock(label('C'), title='Walk C', height=140, exclusive=False)
    ck.dock(label('D'), title='Walk D', height=140, exclusive=False)
    pause()
    state = snapshot()
    c, d = state['panels']['Walk C'], state['panels']['Walk D']
    check('two non-exclusive panels are both open', c['alpha'] == 1 and d['alpha'] == 1)
    check('they stack instead of overlapping', not overlaps(c['frame'], d['frame']))
    check('the newer one sits on top', d['frame'][1] < c['frame'][1])

    # show() updates in place.
    shown = ck.show('one', title='Walk text')
    pause()
    updated = ck.show('two', title='Walk text')
    pause()
    check('show() with the same title reuses the panel', shown is updated)
    check('the reused panel shows the new content', updated.content.text == 'two')

    # Hooks and on_close.
    hooked = ck.dock(Hooked(), title='Walk hooks', height=140,
                     on_close=lambda panel: events.append('on_close'))
    pause()
    hooked.minimise()
    pause()
    hooked.restore()
    pause()
    hooked.close()
    hooked.close()
    pause()
    check('hooks arrive in order and on_close runs once',
          events == ['opened', 'tucked', 'opened', 'closed', 'on_close'])

    # A header button.
    tapped = []
    tools = ck.dock(label('E'), title='Walk button', height=140)
    button = tools.add_button('★', tapped.append)
    pause()
    button.action(button)
    check('an added header button calls its action with the panel', tapped == [tools])

    # Tidy up.
    ck.close_all()
    pause()
    state = snapshot()
    check('close_all leaves no panels', not state['panels'])
    check('close_all leaves no stray views', state['tagged'] == 0)
    check('the console inset is given back', abs(state['inset'] - start_inset) < 0.5)


def report():
    passed = sum(1 for _, ok in results if ok)
    lines = ['consolekit %s walkthrough: %d of %d passed' % (ck.__version__, passed, len(results))]
    lines += [('ok    ' if ok else 'FAIL  ') + name for name, ok in results]
    lines += ['', 'Now check by eye:'] + ['- ' + line for line in BY_EYE]
    text = '\n'.join(lines)
    print(text)
    with open(LOG_FILE, 'w', encoding='utf-8') as handle:
        handle.write(text + '\n')


try:
    walk()
except Exception as error:
    check('the walkthrough ran to the end (stopped: %r)' % error, False)
finally:
    ck.close_all()
    pause()
    report()