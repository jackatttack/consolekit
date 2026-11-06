"""Headless checks for consolekit's layout maths and view picking."""
import os
import sys

import ui

PACKAGE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PACKAGE)
sys.modules.pop('consolekit', None)
import consolekit as ck

print('testing consolekit %s from %s' % (ck.__version__, ck.__file__))
failures = []


def check(name, condition):
    print(('ok    ' if condition else 'FAIL  ') + name)
    if not condition:
        failures.append(name)


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
check('squares run left to right',
      second[1] == first[1] and second[0] - first[0] == ck.SQUARE_SIZE + ck.SQUARE_GAP)
check('square fits the tray height',
      first[1] == ck.TRAY_PADDING and 2 * ck.TRAY_PADDING + ck.SQUARE_SIZE == ck.TRAY_HEIGHT)
check('empty tray has no content', ck.tray_content_width(0) == 0)
check('tray content fits its squares',
      ck.tray_content_width(3) == 2 * ck.TRAY_PADDING + 3 * ck.SQUARE_SIZE + 2 * ck.SQUARE_GAP)

check('square shows the icon', ck.square_label('Timer', '⏱') == '⏱')
check('square shows the first letter', ck.square_label(' timer') == 'T')
check('square without a title', ck.square_label(None) == '•')

check('html is recognised', ck.looks_like_html('  <b>hi</b>\n'))
check('plain text is not html', not ck.looks_like_html('a < b'))

view = ui.View()
check('a view docks as itself', ck.view_for(view) is view)
text_view = ck.view_for('hello')
check('text becomes a read-only TextView',
      isinstance(text_view, ui.TextView) and not text_view.editable)
check('numbers become text', ck.view_for(42).text == '42')
image = ui.Image.named('test:Lenna')
check('a ui.Image becomes an ImageView', isinstance(ck.view_for(image), ui.ImageView))


class FakeFigure:
    def savefig(self, buffer, format=None):
        pass


check('show names text Text', ck.default_title('hello') == 'Text')
check('show names HTML Page', ck.default_title('<p>hi</p>') == 'Page')
check('show names an image Image', ck.default_title(image) == 'Image')
check('show names a figure Chart', ck.default_title(FakeFigure()) == 'Chart')
check('show names an unnamed view Panel', ck.default_title(ui.View()) == 'Panel')
named = ui.View()
named.name = 'Tools'
check('show uses a view name', ck.default_title(named) == 'Tools')

if failures:
    print('%d failed' % len(failures))
    sys.exit(1)
print('consolekit smoke: all passed')