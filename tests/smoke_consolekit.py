"""Headless checks for consolekit: layout maths, view picking, and the
panel lifecycle (panels built on the main thread, never docked)."""
import os
import sys

import ui

try:
    from objc_util import on_main_thread
except ImportError:
    on_main_thread = None

PACKAGE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.isfile(os.path.join(PACKAGE, 'consolekit.py')):
    # A source checkout: test the copy beside this folder, not the installed one.
    sys.path.insert(0, PACKAGE)
sys.modules.pop('consolekit', None)
import consolekit as ck

print('testing consolekit %s from %s' % (ck.__version__, ck.__file__))
failures = []
KEEP = []      # views built for the lifecycle checks stay referenced


def check(name, condition):
    print(('ok    ' if condition else 'FAIL  ') + name)
    if not condition:
        failures.append(name)


# --- One panel ----------------------------------------------------------------
console = (0, 0, 400, 800)
input_bar_top = 800 - ck.INPUT_BAR_CLEARANCE

full = ck.panel_frame(console)
check('full panel keeps side margins',
      full[0] == ck.SIDE_MARGIN and full[2] == 400 - 2 * ck.SIDE_MARGIN)
check('full panel starts at the top margin', full[1] == ck.TOP_MARGIN)
check('full panel stops above the input bar', full[1] + full[3] == input_bar_top)

short = ck.panel_frame(console, height=200)
check('fixed height sits on the input bar',
      short[3] == 200 and short[1] + short[3] == input_bar_top)
check('too tall is clamped to the top margin',
      ck.panel_frame(console, height=5000)[1] == ck.TOP_MARGIN)
check('tiny console keeps the minimum height',
      ck.panel_frame((0, 0, 400, 150))[3] == ck.MINIMUM_PANEL_HEIGHT)

# --- Stacked panels (exclusive=False) -------------------------------------
two = ck.stack_frames(console, [200, 150])
check('the first panel sits at the bottom', two[0][1] + two[0][3] == input_bar_top)
check('stacked panels do not overlap', two[1][1] + two[1][3] <= two[0][1] - ck.STACK_GAP)
check('fixed heights are kept when they fit', two[0][3] == 200 and two[1][3] == 150)
shared = ck.stack_frames(console, [None, None])
check('flexible panels share the space equally', abs(shared[0][3] - shared[1][3]) < 1)
check('flexible panels reach the top margin', abs(shared[1][1] - ck.TOP_MARGIN) < 1)
mixed = ck.stack_frames(console, [200, None])
check('a flexible panel fills what a fixed one leaves',
      mixed[0][3] == 200 and abs(mixed[1][1] - ck.TOP_MARGIN) < 1)
check('no panels, no frames', ck.stack_frames(console, []) == [])
check('one panel stacks exactly like panel_frame',
      ck.stack_frames(console, [200])[0] == ck.panel_frame(console, 200))

# --- Tray -----------------------------------------------------------------
tray = ck.tray_frame(console)
check('tray sits on the input bar', tray[1] + tray[3] == input_bar_top)
check('tray keeps side margins',
      tray[0] == ck.SIDE_MARGIN and tray[2] == 400 - 2 * ck.SIDE_MARGIN)
above = ck.panel_frame(console, tray_showing=True)
check('panel stops above the tray', above[1] + above[3] == tray[1] - ck.TRAY_GAP)
short_above = ck.panel_frame(console, height=200, tray_showing=True)
check('fixed height sits on the tray',
      short_above[3] == 200 and short_above[1] + short_above[3] == tray[1] - ck.TRAY_GAP)

first = ck.square_origin(0)
second = ck.square_origin(1)
check('the first square starts the strip', first == (0, ck.TRAY_PADDING))
check('squares run left to right',
      second[1] == first[1] and second[0] - first[0] == ck.SQUARE_SIZE + ck.SQUARE_GAP)
check('square fits the tray height', 2 * ck.TRAY_PADDING + ck.SQUARE_SIZE == ck.TRAY_HEIGHT)
check('empty tray has no content', ck.tray_content_width(0) == 0)
check('strip content fits its squares',
      ck.tray_content_width(3) == 3 * ck.SQUARE_SIZE + 2 * ck.SQUARE_GAP)
check('the tray asks for enough console inset to clear it',
      44 + ck.tray_inset(44) == ck.INPUT_BAR_CLEARANCE + ck.TRAY_HEIGHT + ck.TRAY_GAP)
check('no extra inset when the console already has room', ck.tray_inset(1000) == 0)

check('square shows the icon', ck.square_label('Timer', '⏱') == '⏱')
check('square shows the first letter', ck.square_label(' timer') == 'T')
check('square without a title', ck.square_label(None) == '•')

# --- Turning things into views --------------------------------------------
check('html is recognised', ck.looks_like_html('  <b>hi</b>\n'))
check('plain text is not html', not ck.looks_like_html('a < b'))
styled = ck.page_html('<h1>Hi</h1>')
check('an HTML fragment gets the dark page style',
      styled.startswith('<meta') and styled.endswith('<h1>Hi</h1>'))
page = '<html><body>x</body></html>'
check('a full page is left alone', ck.page_html(page) == page)

view = ui.View()
check('a view docks as itself', ck.view_for(view) is view)
text_view = ck.view_for('hello')
check('text becomes a read-only TextView',
      isinstance(text_view, ui.TextView) and not text_view.editable)
check('numbers become text', ck.view_for(42).text == '42')
check('a missing .pyui path shows as text', isinstance(ck.view_for('gone.pyui'), ui.TextView))
image = ui.Image.named('test:Lenna')
check('a ui.Image becomes an ImageView', isinstance(ck.view_for(image), ui.ImageView))


class FakeFigure:
    def savefig(self, buffer, format=None):
        pass


check('show names text Text', ck.default_title('hello') == 'Text')
check('show names HTML Page', ck.default_title('<p>hi</p>') == 'Page')
check('show names an image Image', ck.default_title(image) == 'Image')
check('show names a figure Chart', ck.default_title(FakeFigure()) == 'Chart')
check('show names a .pyui file after it', ck.default_title('panels/tools.pyui') == 'tools')
check('show names an unnamed view Panel', ck.default_title(ui.View()) == 'Panel')
named = ui.View()
named.name = 'Tools'
check('show uses a view name', ck.default_title(named) == 'Tools')

try:
    ck.dock('notes.txt')
    refused = False
except ValueError:
    refused = True
check('dock refuses a string that is not a .pyui path', refused)
check('get finds nothing for an unknown key', ck.get('no such panel %d' % id(ck)) is None)
check('the public names are all there', all(hasattr(ck, name) for name in ck.__all__))


# --- Panel lifecycle (never docked) ---------------------------------------
class Recorder(ui.View):
    """Content that records which hooks it heard."""

    def __init__(self):
        self.calls = []

    def panel_opened(self, panel):
        self.calls.append('opened')

    def panel_tucked(self, panel):
        self.calls.append('tucked')

    def panel_closed(self, panel):
        self.calls.append('closed')


def lifecycle():
    results = {}
    closed = []
    first_content, second_content = Recorder(), Recorder()
    panel = ck.Panel(first_content, 'Life', 'smoke-life', 200, None, True, True, closed.append)
    panel.frame = (0, 0, 300, 200)
    button = panel.add_button('★', lambda panel: None)
    results['an added button lands in the header'] = button.superview is panel.header
    results['an added button sits left of minimise'] = button.x < panel.minimise_button.x
    results['the title makes room for the added button'] = (
        panel.title_label.width == 300 - 3 * ck.HEADER_HEIGHT - 14)
    panel.set_content(second_content)
    results['set_content swaps the view'] = (
        panel.content is second_content and second_content.superview is panel)
    results['the old view hears panel_closed'] = first_content.calls == ['closed']
    panel.close()
    panel.close()
    results['on_close runs once for two closes'] = closed == [panel]
    results['the view hears panel_closed once'] = second_content.calls == ['closed']
    bare = ck.Panel(ui.View(), 'Bare', 'smoke-bare', None, None, False, True, None)
    try:
        bare.add_button('x', print)
        results['add_button without a header is refused'] = False
    except ValueError:
        results['add_button without a header is refused'] = True
    KEEP.extend([panel, bare, first_content, second_content])
    return results


if on_main_thread is None:
    print('skip  panel lifecycle (no objc_util here)')
else:
    results = on_main_thread(lifecycle)()
    if not results:
        check('lifecycle checks returned results', False)
    else:
        for name, passed in results.items():
            check(name, passed)

if failures:
    print('%d failed' % len(failures))
    sys.exit(1)
print('consolekit smoke: all passed')