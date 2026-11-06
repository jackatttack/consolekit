"""consolekit: dock any Pythonista ui view in the console.

    import consolekit

    panel = consolekit.dock(my_view, title='Timer', icon='⏱')
    consolekit.show('text, HTML, a ui.Image, a PIL image or a matplotlib figure')

    panel.minimise()        # tuck it into the tray; tap its square to bring it back
    panel.restore()
    panel.close()
    consolekit.close_all()

One panel is open at a time: opening one tucks the others into a tray
along the bottom of the console, so nothing overlaps. Pass
exclusive=False to let a panel open alongside the others; open panels
stack upwards from the bottom, newest on top.

Rerun-safe: panels are keyed by title (or key=). Running a script again
replaces its panel instead of stacking another, and a minimised panel
comes back minimised. show() with a key that is already docked updates
that panel in place, so calling it in a loop is smooth.

Your view keeps working after the script ends: actions fire and update()
keeps ticking. Where there is no console to dock in (PythonIDE, or a
Pythonista update that moves its views), dock() presents the panel as a
sheet instead, so scripts never break.

Extending: panel.show() puts anything show() takes into that panel,
panel.add_button() puts your own button in the header,
panel.set_content() swaps the view, and your view can define
panel_opened(panel), panel_tucked(panel) and panel_closed(panel) to hear
what happens to its panel.

How it works: the console is Pythonista's own OMTextView (the editor uses
the same class, always inside an OMTextEditorView). Views added beside it
stay put while the text scrolls and survive Clear. Pythonista clears a
script's globals when it ends, so live panels are parked on builtins.
This relies on private view classes, so a Pythonista update could move
things.
"""
import builtins
import io
import os
import sys
import time

import ui

try:
    from objc_util import CGPoint, ObjCClass, on_main_thread
except ImportError:  # no Objective-C bridge: panels can only be sheets
    CGPoint = ObjCClass = None

    def on_main_thread(function):
        return function

__version__ = '1.3.0'
__all__ = ['dock', 'show', 'get', 'close', 'close_all', 'Panel', 'COLOURS']

# --- Look (edit freely, before docking your first panel) -----------------------
COLOURS = {
    'backdrop': '#0d0e11',
    'panel': '#16181d',
    'header': '#1e2128',
    'tray': '#1a1c22',
    'edge': '#2c303a',
    'accent': '#e8335a',
    'text': '#e6e6e6',
}
FONT = 'Menlo'
BOLD_FONT = 'Menlo-Bold'
PANEL_RADIUS = 14
HEADER_HEIGHT = 40
SQUARE_SIZE = 40
SQUARE_GAP = 8
SQUARE_RADIUS = 10
TRAY_PADDING = 6
TRAY_HEIGHT = SQUARE_SIZE + 2 * TRAY_PADDING
TRAY_GAP = 8                 # between the tray and the open panel above it
TRAY_RADIUS = 14
STACK_GAP = 8                # between open panels stacked with exclusive=False
BIG_TEXT_LIMIT = 40          # show() draws one line up to this long big and centred
BIG_TEXT_SIZE = 48           # its starting size; it shrinks to fit the panel

# Dark style for HTML fragments given to show(); full pages keep their own.
PAGE_STYLE = ('<meta name="viewport" content="width=device-width, initial-scale=1">'
              '<style>body{background:%s;color:%s;font-family:Menlo,monospace;'
              'margin:0;padding:12px}a{color:%s}</style>')

# --- Layout (points) ---------------------------------------------------------
SIDE_MARGIN = 12
TOP_MARGIN = 8
INPUT_BAR_CLEARANCE = 90     # keeps panels and the tray above the input bar
MINIMUM_PANEL_HEIGHT = 120
SHEET_SIZE = (540, 480)      # the fallback when there is no console

# --- Motion (seconds) --------------------------------------------------------
ANIMATION_SECONDS = 0.25
SLIDE_DISTANCE = 16
CLOCK_SECONDS = 0.5          # how often panels check the console's size

# --- Internal names: keep stable so a newer version can clean up an older one -
PANELS_NAME = '_consolekit_panels'   # key -> live Panel
STATE_NAME = '_consolekit_state'     # key -> {'minimised': bool}
PARTS_NAME = '_consolekit_parts'     # the shared tray, backdrop and console
VIEW_TAG = 0x434B4954                # 'CKIT': marks every docked view
DARK_INTERFACE = 2                   # UIUserInterfaceStyleDark
DEFAULT_KEY = 'consolekit'


# --- Public API --------------------------------------------------------------
def dock(view, title=None, key=None, height=None, icon=None, chrome=True,
         exclusive=True, on_close=None):
    """Dock view in the console and return its Panel.

    view       a ui.View, or the path of a .pyui file made in the UI designer
    title      shown in the header; also the default key
    key        names the panel; docking the same key again replaces it
    height     points tall, header included, sitting above the tray;
               None fills the console
    icon       text or emoji for its square in the tray (default: title's first letter)
    chrome     False drops the header (no minimise or close buttons)
    exclusive  True tucks other open panels into the tray when this one opens;
               False opens it alongside them, stacked above
    on_close   called with the panel when it closes
    """
    if isinstance(view, str):
        view = load_pyui(view)
    key = key or title or DEFAULT_KEY
    close(key)
    panel = Panel(view, title, key, height, icon, chrome, exclusive, on_close)
    live_panels()[key] = panel
    attach(panel)
    if not panel.docked:
        present_as_sheet(panel)
    return panel


def show(thing, title=None, **options):
    """Dock anything: a ui.View, text, an HTML string, a ui.Image, a PIL
    image, a matplotlib figure (or pyplot itself, for the current figure)
    or the path of a .pyui file.

    Without a title it is named by kind (Text, Page, Image, Chart, or the
    view's name), so different kinds sit side by side. If a panel with the
    same key is already docked, its content is swapped in place and the
    panel keeps its spot, so show() can run in a loop. Takes the same
    options as dock(); on an update only title and height are applied.
    """
    if title is None and 'key' not in options:
        title = default_title(thing)
    key = options.get('key') or title or DEFAULT_KEY
    panel = get(key)
    if panel is not None and hasattr(panel, 'set_content'):
        panel.set_content(view_for(thing))
        if title is not None:
            panel.set_title(title)
        if 'height' in options:
            panel.set_height(options['height'])
        return panel
    return dock(view_for(thing), title=title, **options)


def get(key):
    """The live panel docked under key (its title, unless you gave a key), or None."""
    return live_panels().get(key)


def close(key):
    """Close the panel docked under key, if there is one."""
    panel = live_panels().get(key)
    if panel is not None:
        panel.close()


@on_main_thread
def close_all():
    """Close every panel, the tray and the backdrop, including strays left
    by an older version, and forget which panels were minimised."""
    for panel in list(live_panels().values()):
        panel.close()
    remove_parts()
    shared(STATE_NAME).clear()
    text_view = find_console_text_view()
    if text_view is not None:
        for subview in list(text_view.superview().subviews()):
            if subview.tag() == VIEW_TAG:
                subview.removeFromSuperview()


# --- Turning things into views -----------------------------------------------
def view_for(thing):
    """A view that shows thing."""
    if isinstance(thing, ui.View):
        return thing
    if is_pyui_path(thing) and os.path.isfile(os.path.abspath(thing)):
        return load_pyui(thing)
    image = image_for(thing)
    if image is not None:
        view = ui.ImageView()
        view.image = image
        view.content_mode = ui.CONTENT_SCALE_ASPECT_FIT
        return view
    text = str(thing)
    if looks_like_html(text):
        view = ui.WebView()
        view.load_html(page_html(text))
        return view
    if is_short_line(text):
        return big_label(text.strip())
    view = ui.TextView()
    view.text = text
    view.editable = False
    view.font = (FONT, 13)
    view.text_color = COLOURS['text']
    view.background_color = COLOURS['panel']
    return view


def image_for(thing):
    """A ui.Image from a ui.Image, matplotlib figure or PIL image, else None."""
    if isinstance(thing, ui.Image):
        return thing
    buffer = io.BytesIO()
    if hasattr(thing, 'savefig'):                     # matplotlib figure or pyplot
        thing.savefig(buffer, format='png')
    elif hasattr(thing, 'save') and hasattr(thing, 'mode'):   # PIL image
        thing.save(buffer, 'PNG')
    else:
        return None
    return ui.Image.from_data(buffer.getvalue())


def is_pyui_path(thing):
    return isinstance(thing, str) and thing.strip().endswith('.pyui')


def load_pyui(path):
    """A view from a .pyui file. A relative path starts in the running
    script's folder. Actions named in the file are looked up in the script
    that called dock() or show()."""
    if not is_pyui_path(path):
        raise ValueError('dock() takes a ui.View or the path of a .pyui file, not %r' % path)
    full_path = os.path.abspath(path.strip())
    if not os.path.isfile(full_path):
        raise FileNotFoundError('No .pyui file at %s' % full_path)
    try:
        return ui.load_view(full_path, stackframe=caller_frame())
    except TypeError:            # a ui module without the stackframe option
        return ui.load_view(full_path)


def caller_frame():
    """The first stack frame outside consolekit: the script that called us."""
    frame = sys._getframe(1)
    while frame is not None and frame.f_globals is globals():
        frame = frame.f_back
    return frame


def looks_like_html(text):
    stripped = text.strip()
    return stripped.startswith('<') and stripped.endswith('>')


def is_short_line(text):
    """One short line reads best big and centred, like a display."""
    stripped = text.strip()
    return bool(stripped) and '\n' not in stripped and len(stripped) <= BIG_TEXT_LIMIT


def big_label(text):
    """A big centred label that shrinks to fit rather than cutting text off."""
    label = ui.Label()
    label.text = text
    label.alignment = ui.ALIGN_CENTER
    label.font = (BOLD_FONT, BIG_TEXT_SIZE)
    label.text_color = COLOURS['text']
    label.background_color = COLOURS['panel']
    if ObjCClass is not None:
        native = label.objc_instance
        native.setAdjustsFontSizeToFitWidth_(True)
        native.setMinimumScaleFactor_(0.25)
    return label


def page_html(text):
    """Full pages pass through; a fragment gets the panel's dark style."""
    lowered = text.lower()
    if '<html' in lowered or '<body' in lowered:
        return text
    return PAGE_STYLE % (COLOURS['panel'], COLOURS['text'], COLOURS['accent']) + text


def default_title(thing):
    """The title show() uses when it is given none."""
    if isinstance(thing, ui.View):
        return thing.name or 'Panel'
    if is_pyui_path(thing):
        return os.path.splitext(os.path.basename(thing.strip()))[0]
    if hasattr(thing, 'savefig'):
        return 'Chart'
    if isinstance(thing, ui.Image) or (hasattr(thing, 'save') and hasattr(thing, 'mode')):
        return 'Image'
    if looks_like_html(str(thing)):
        return 'Page'
    return 'Text'


# --- Layout maths (pure, tested headless) ------------------------------------
def open_area(console_frame, tray_showing=False):
    """(left, top, width, bottom) of the space open panels share."""
    x, y, width, height = console_frame
    bottom = y + height - INPUT_BAR_CLEARANCE
    if tray_showing:
        bottom -= TRAY_HEIGHT + TRAY_GAP
    return x + SIDE_MARGIN, y + TOP_MARGIN, width - 2 * SIDE_MARGIN, bottom


def stack_frames(console_frame, heights, tray_showing=False):
    """Frames for the open panels, stacked upwards from the bottom.

    heights holds each panel's requested height, oldest first, or None to
    share whatever the fixed ones leave. The first sits at the bottom.
    Every panel keeps MINIMUM_PANEL_HEIGHT; when they cannot all fit they
    overlap rather than leave the console.
    """
    if not heights:
        return []
    left, top, width, bottom = open_area(console_frame, tray_showing)
    room = bottom - top - (len(heights) - 1) * STACK_GAP
    fixed = sum(height for height in heights if height is not None)
    flexible_count = sum(1 for height in heights if height is None)
    share = (room - fixed) / flexible_count if flexible_count else 0
    frames = []
    edge = bottom
    for requested in heights:
        wanted = max(share if requested is None else requested, MINIMUM_PANEL_HEIGHT)
        panel_top = max(top, edge - wanted)
        frames.append((left, panel_top, width, max(edge - panel_top, MINIMUM_PANEL_HEIGHT)))
        edge = panel_top - STACK_GAP
    return frames


def panel_frame(console_frame, height=None, tray_showing=False):
    """A single open panel's frame, in the console container's coordinates."""
    return stack_frames(console_frame, [height], tray_showing)[0]


def tray_frame(console_frame):
    """The tray: one row along the bottom, just above the input bar."""
    x, y, width, height = console_frame
    bottom = y + height - INPUT_BAR_CLEARANCE
    return (x + SIDE_MARGIN, bottom - TRAY_HEIGHT, width - 2 * SIDE_MARGIN, TRAY_HEIGHT)


def square_origin(slot):
    """Where square number slot sits in the tray's scrolling strip, left to right."""
    return (slot * (SQUARE_SIZE + SQUARE_GAP), TRAY_PADDING)


def tray_content_width(count):
    """How wide count squares are; the strip scrolls sideways past its width."""
    if count == 0:
        return 0
    return count * SQUARE_SIZE + (count - 1) * SQUARE_GAP


def tray_inset(base_bottom):
    """Extra bottom inset the console needs so its last line clears the tray,
    given the inset Pythonista already uses for its input bar."""
    needed = INPUT_BAR_CLEARANCE + TRAY_HEIGHT + TRAY_GAP
    return max(0, needed - base_bottom)


def square_label(title, icon=None):
    if icon:
        return icon
    title = (title or '').strip()
    return title[0].upper() if title else '•'


# --- Live state, parked on builtins ------------------------------------------
def shared(name):
    value = getattr(builtins, name, None)
    if value is None:
        value = {}
        setattr(builtins, name, value)
    return value


def live_panels():
    return shared(PANELS_NAME)


def parts():
    """The shared tray, backdrop, console text view, its last frame and the
    inset consolekit added to it."""
    return shared(PARTS_NAME)


def remembered(key):
    """Per-key state that outlives reruns until Pythonista quits."""
    return shared(STATE_NAME).setdefault(key, {'minimised': False})


def docked_panels():
    return [panel for panel in live_panels().values() if panel.docked]


def open_panels():
    """Docked panels that are showing, oldest first (the bottom of the stack)."""
    showing = [panel for panel in docked_panels() if not panel.minimised]
    return sorted(showing, key=lambda panel: getattr(panel, 'opened_at', 0))


# --- Finding the console -----------------------------------------------------
def class_name(view):
    name = view._get_objc_classname()
    return name.decode() if isinstance(name, bytes) else str(name)


def search_views(view, inside_editor):
    name = class_name(view)
    if name == 'OMTextEditorView':
        inside_editor = True
    elif name == 'OMTextView' and not inside_editor:
        return view
    for subview in view.subviews():
        found = search_views(subview, inside_editor)
        if found is not None:
            return found
    return None


def find_console_text_view():
    """The console is the first OMTextView with no OMTextEditorView above it.
    None when there is no console to find."""
    if ObjCClass is None:
        return None
    try:
        app = ObjCClass('UIApplication').sharedApplication()
        for window in app.windows():
            found = search_views(window, inside_editor=False)
            if found is not None:
                return found
    except Exception:
        pass
    return None


def read_frame(text_view):
    frame = text_view.frame()
    return (frame.origin.x, frame.origin.y, frame.size.width, frame.size.height)


# --- The console's bottom inset ----------------------------------------------
def set_console_inset(extra):
    """Give the console extra bottom inset over what it had before consolekit
    touched it. Only consolekit's own share is ever added or taken away, so
    whatever Pythonista does to the inset meanwhile is kept."""
    store = parts()
    text_view = store.get('text_view')
    current = store.get('inset_extra', 0)
    if text_view is None or extra == current:
        return
    try:
        inset = text_view.contentInset()
        inset.bottom += extra - current
        text_view.setContentInset_(inset)
        store['inset_extra'] = extra
        if extra > current:
            scroll_to_end(text_view)
    except Exception:
        pass


def scroll_to_end(text_view):
    """Bring the newest console line into view above the tray."""
    inset = text_view.contentInset()
    end = text_view.contentSize().height + inset.bottom - text_view.bounds().size.height
    if end > -inset.top:
        text_view.setContentOffset_animated_(CGPoint(0, end), True)


# --- The shared tray and backdrop --------------------------------------------
def prepare(view):
    native = view.objc_instance
    native.setTag_(VIEW_TAG)
    # Always drawn dark. Under a light theme UIKit would otherwise use light
    # defaults inside (black text on the dark panel).
    native.setOverrideUserInterfaceStyle_(DARK_INTERFACE)
    return native


def make_backdrop():
    view = ui.View()
    view.background_color = COLOURS['backdrop']
    view.alpha = 0
    return view


def ensure_parts(text_view):
    """Create the backdrop and tray beside the console, once."""
    store = parts()
    container = text_view.superview()
    backdrop = store.get('backdrop')
    if backdrop is None or backdrop.objc_instance.superview() is None:
        backdrop = make_backdrop()
        # Just above the console text, below Pythonista's input bar and
        # anything else it draws over the text.
        container.insertSubview_aboveSubview_(prepare(backdrop), text_view)
        store['backdrop'] = backdrop
    tray = store.get('tray')
    # An older version's tray (a bare ScrollView) has no strip: replace it.
    if tray is None or tray.objc_instance.superview() is None or not hasattr(tray, 'strip'):
        if tray is not None:
            tray.objc_instance.removeFromSuperview()
        tray = Tray()
        container.addSubview_(prepare(tray))
        store['tray'] = tray
    if 'base_inset' not in store:
        try:
            store['base_inset'] = text_view.contentInset().bottom
        except Exception:
            store['base_inset'] = 0
        store['inset_extra'] = 0
    store['text_view'] = text_view
    store['frame'] = read_frame(text_view)


def remove_parts():
    """Take away the tray and backdrop and give the console its inset back."""
    set_console_inset(0)
    store = parts()
    for name in ('tray', 'backdrop'):
        view = store.get(name)
        if view is not None:
            try:
                view.objc_instance.removeFromSuperview()
            except Exception:
                pass
    store.clear()


def relayout(animated=True):
    """Fit the tray, its squares, the open panels, the backdrop and the
    console's inset to the console."""
    store = parts()
    tray, backdrop, frame = store.get('tray'), store.get('backdrop'), store.get('frame')
    if tray is None or backdrop is None or frame is None:
        return
    docked = docked_panels()
    tucked = [panel for panel in docked if panel.minimised]
    showing = open_panels()

    tray.frame = tray_frame(frame)
    for slot, panel in enumerate(tucked):
        x, y = square_origin(slot)
        panel.square.frame = (x, y, SQUARE_SIZE, SQUARE_SIZE)
    for panel in docked:
        panel.square.hidden = not panel.minimised
    tray.strip.content_size = (tray_content_width(len(tucked)), TRAY_HEIGHT)
    backdrop.frame = frame
    set_console_inset(tray_inset(store.get('base_inset', 0)) if tucked else 0)
    targets = stack_frames(frame, [panel.requested_height for panel in showing], bool(tucked))

    def settle():
        tray.alpha = 1 if tucked else 0
        backdrop.alpha = 1 if showing else 0
        for panel, target in zip(showing, targets):
            panel.frame = target
            panel.alpha = 1
    if animated:
        ui.animate(settle, ANIMATION_SECONDS)
    else:
        settle()


# --- Docking -----------------------------------------------------------------
@on_main_thread
def attach(panel):
    """Add the panel beside the console and its square to the tray.
    Sets panel.docked."""
    text_view = find_console_text_view()
    if text_view is None:
        return
    ensure_parts(text_view)
    text_view.superview().addSubview_(prepare(panel))
    parts()['tray'].strip.add_subview(panel.square)
    panel.docked = True
    if remembered(panel.key)['minimised']:
        panel.minimised = True
        relayout(animated=False)
        panel.tell('panel_tucked')
    else:
        panel.open()


def present_as_sheet(panel):
    """Fallback with no console: show the same panel as a sheet."""
    panel.alpha = 1
    panel.frame = (0, 0, SHEET_SIZE[0], panel.requested_height or SHEET_SIZE[1])
    if panel.header is None:
        panel.present('sheet')
    else:
        panel.minimise_button.hidden = True
        try:
            panel.present('sheet', hide_title_bar=True)
        except TypeError:
            panel.present('sheet')
    panel.tell('panel_opened')


# --- Views -------------------------------------------------------------------
class Tray(ui.View):
    """The rounded strip along the bottom that holds minimised panels.

    The squares scroll inside an inner strip set in from the rounded ends,
    so a scrolled square is cut by a straight edge, never by the curve."""

    def __init__(self):
        self.background_color = COLOURS['tray']
        self.border_color = COLOURS['edge']
        self.border_width = 1
        self.corner_radius = TRAY_RADIUS
        self.alpha = 0
        self.strip = ui.ScrollView()
        self.strip.background_color = (0, 0, 0, 0)
        self.strip.shows_horizontal_scroll_indicator = False
        self.strip.shows_vertical_scroll_indicator = False
        self.add_subview(self.strip)

    def layout(self):
        self.strip.frame = (TRAY_PADDING, 0, self.width - 2 * TRAY_PADDING, self.height)


class Square(ui.View):
    """A minimised panel in the tray. A tap brings the panel back."""

    def __init__(self, panel, text):
        self.panel = panel
        self.hidden = True
        self.background_color = COLOURS['header']
        self.border_color = COLOURS['accent']
        self.border_width = 2
        self.corner_radius = SQUARE_RADIUS
        label = ui.Label()
        label.text = text
        label.alignment = ui.ALIGN_CENTER
        label.font = (BOLD_FONT, 18)
        label.text_color = COLOURS['text']
        label.touch_enabled = False
        label.frame = (0, 0, SQUARE_SIZE, SQUARE_SIZE)
        self.add_subview(label)
        self.frame = (0, 0, SQUARE_SIZE, SQUARE_SIZE)

    def touch_ended(self, touch):
        if self.panel.minimised:
            self.panel.restore()


class Panel(ui.View):
    """One docked panel: an optional header, your view, and its tray square.

    dock() and show() give you one. Use its methods rather than changing
    its frame or alpha yourself: consolekit lays panels out.
    """

    def __init__(self, content, title, key, height, icon, chrome, exclusive, on_close):
        self.content = content
        self.key = key
        self.requested_height = height
        self.exclusive = exclusive
        self.on_close = on_close
        self.docked = False
        self.minimised = False
        self.closed = False
        self.opened_at = 0.0          # newer open panels stack above older ones
        self.extra_buttons = []       # from add_button(), right to left
        self.alpha = 0                # fades in when it opens
        self.background_color = COLOURS['panel']
        self.border_color = COLOURS['edge']
        self.border_width = 1
        self.corner_radius = PANEL_RADIUS
        self.header = self.make_header(title) if chrome else None
        self.add_subview(content)
        self.square = Square(self, square_label(title, icon))
        self.update_interval = CLOCK_SECONDS

    # --- Header ----------------------------------------------------------------
    def make_header(self, title):
        header = ui.View()
        header.background_color = COLOURS['header']
        self.title_label = ui.Label()
        self.title_label.text = title or ''
        self.title_label.font = (BOLD_FONT, 14)
        self.title_label.text_color = COLOURS['text']
        self.minimise_button = self.make_button('—', lambda sender: self.minimise())
        self.close_button = self.make_button('✕', lambda sender: self.close_by_user())
        for view in (self.title_label, self.minimise_button, self.close_button):
            header.add_subview(view)
        self.add_subview(header)
        return header

    def make_button(self, symbol, action):
        button = ui.Button()
        button.title = symbol            # title before frame: a titled button
        button.font = (BOLD_FONT, 18)    # shrink-wraps unless the frame comes last
        button.tint_color = COLOURS['text']
        button.action = action
        button.frame = (0, 0, HEADER_HEIGHT, HEADER_HEIGHT)
        return button

    def add_button(self, symbol, action):
        """Add a button to the header, left of the minimise button, and return it.

        action is called with this panel when the button is tapped. Adding a
        symbol the header already has gives that button the new action
        instead, so running a script again never doubles its buttons.

        The action runs after your script has ended and its global names
        are cleared, so it should only use the panel it is given (keep any
        state on the panel: panel.score = 0) and builtins.
        """
        if self.header is None:
            raise ValueError('add_button needs the header: dock with chrome=True')
        for button in self.extra_buttons:
            if button.title == symbol:
                button.action = lambda sender: self.run_action(action)
                return button
        button = self.make_button(symbol, lambda sender: self.run_action(action))
        self.attach_header_button(button)
        return button

    @on_main_thread
    def attach_header_button(self, button):
        self.extra_buttons.append(button)
        self.header.add_subview(button)
        self.layout()

    def run_action(self, action):
        try:
            action(self)
        except Exception as error:
            print('consolekit: header button failed: %r' % error)

    def set_title(self, text):
        if self.header is not None:
            self.title_label.text = text

    def header_buttons(self):
        """The header's visible buttons, right to left."""
        buttons = [self.close_button, self.minimise_button] + self.extra_buttons
        return [button for button in buttons if not button.hidden]

    # --- Content ---------------------------------------------------------------
    @on_main_thread
    def set_content(self, view):
        """Swap the view inside the panel, keeping its place, title and state.
        The old view hears panel_closed; the new one hears where it landed."""
        old = self.content
        if view is old:
            return
        self.remove_subview(old)
        self.content = view
        self.add_subview(view)
        self.layout()
        self.tell('panel_closed', old)
        if self.docked:
            self.tell('panel_tucked' if self.minimised else 'panel_opened')
        elif self.on_screen:
            self.tell('panel_opened')

    def show(self, thing):
        """Show thing in this panel in place of what it shows now. Takes
        anything consolekit.show() does: text, HTML, images, charts, views."""
        self.set_content(view_for(thing))
        return self

    @on_main_thread
    def set_height(self, height):
        """Change how tall the panel is, in points with the header; None fills."""
        self.requested_height = height
        if self.docked and not self.minimised:
            relayout()

    def tell(self, hook_name, view=None):
        """Call the content's optional hook (panel_opened, panel_tucked or
        panel_closed) with this panel. A failing hook is printed, never raised."""
        view = self.content if view is None else view
        hook = getattr(view, hook_name, None)
        if hook is None:
            return
        try:
            hook(self)
        except Exception as error:
            print('consolekit: %s failed: %r' % (hook_name, error))

    def layout(self):
        top = 0
        if self.header is not None:
            width = self.width
            buttons = self.header_buttons()
            self.header.frame = (0, 0, width, HEADER_HEIGHT)
            for index, button in enumerate(buttons):
                button.frame = (width - (index + 1) * HEADER_HEIGHT, 0, HEADER_HEIGHT, HEADER_HEIGHT)
            self.title_label.frame = (14, 0, width - len(buttons) * HEADER_HEIGHT - 14, HEADER_HEIGHT)
            top = HEADER_HEIGHT
        self.content.frame = (0, top, self.width, self.height - top)

    # --- Following the console -------------------------------------------------
    def update(self):
        """The clock: refit everything when the console changes size."""
        store = parts()
        text_view = store.get('text_view')
        if not self.docked or text_view is None:
            return
        frame = read_frame(text_view)
        if frame != store.get('frame'):
            store['frame'] = frame
            relayout(animated=False)

    def bring_to_front(self):
        native = self.objc_instance
        superview = native.superview()
        if superview is not None:
            superview.bringSubviewToFront_(native)

    # --- Motion ----------------------------------------------------------------
    def open(self):
        """Show this panel. An exclusive one tucks the other open panels away."""
        self.minimised = False
        self.opened_at = time.time()
        remembered(self.key)['minimised'] = False
        if self.exclusive:
            for other in docked_panels():
                if other is not self and not other.minimised:
                    other.tuck()
        self.bring_to_front()
        target = self.target_frame()
        if target is not None and self.alpha == 0:
            # Start a little low; relayout() slides it up and fades it in.
            x, y, width, height = target
            self.frame = (x, y + SLIDE_DISTANCE, width, height)
        relayout()
        self.tell('panel_opened')

    def target_frame(self):
        """Where relayout() will put this panel, or None if it is not showing."""
        frame = parts().get('frame')
        showing = open_panels()
        if frame is None or self not in showing:
            return None
        tray_showing = any(panel.minimised for panel in docked_panels())
        heights = [panel.requested_height for panel in showing]
        return stack_frames(frame, heights, tray_showing)[showing.index(self)]

    def tuck(self):
        """Fade down into the tray. A view at alpha 0 takes no touches."""
        self.minimised = True
        remembered(self.key)['minimised'] = True
        x, y, width, height = self.frame

        def leave():
            self.alpha = 0
            self.frame = (x, y + SLIDE_DISTANCE, width, height)
        ui.animate(leave, ANIMATION_SECONDS)
        self.tell('panel_tucked')

    @on_main_thread
    def minimise(self):
        if not self.docked or self.minimised:
            return
        self.tuck()
        relayout()

    @on_main_thread
    def restore(self):
        if not self.docked or not self.minimised:
            return
        self.open()

    # --- Closing ---------------------------------------------------------------
    def close_by_user(self):
        remembered(self.key)['minimised'] = False
        self.close()

    @on_main_thread
    def close(self):
        """Remove the panel and its square. Never raises; safe to call twice."""
        if self.closed:
            return
        self.closed = True
        self.update_interval = 0
        was_docked = self.docked
        try:
            if was_docked:
                if self.square.superview is not None:
                    self.square.superview.remove_subview(self.square)
                self.objc_instance.removeFromSuperview()
            elif self.on_screen:
                ui.View.close(self)
        except Exception:
            pass
        self.docked = False
        self.forget()
        if was_docked:
            if docked_panels():
                relayout()
            else:
                remove_parts()
        self.finish()

    def will_close(self):
        """Pythonista calls this when a sheet closes, including a swipe down."""
        if self.docked or self.closed:
            return
        self.closed = True
        self.forget()
        self.finish()

    def finish(self):
        """Tell the content and run on_close, once per panel."""
        self.tell('panel_closed')
        if self.on_close is not None:
            try:
                self.on_close(self)
            except Exception as error:
                print('consolekit: on_close failed: %r' % error)

    def forget(self):
        if live_panels().get(self.key) is self:
            del live_panels()[self.key]