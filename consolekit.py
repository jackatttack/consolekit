"""consolekit: dock any Pythonista ui view in the console.

    import consolekit

    panel = consolekit.dock(my_view, title='Timer', icon='⏱')
    consolekit.show('text, HTML, a ui.Image, a PIL image or a matplotlib figure')

    panel.minimise()        # fade down to a small square; tap it to come back
    panel.restore()
    panel.close()
    consolekit.close_all()

Rerun-safe: panels are keyed by title (or key=), so running a script again
replaces its panel instead of stacking another, and a minimised panel comes
back minimised. Several minimised panels stack up the console's right edge.

Your view keeps working after the script ends: actions fire and update()
keeps ticking. Where there is no console to dock in (PythonIDE, or a
Pythonista update that moves its views), dock() presents the panel as a
sheet instead, so scripts never break.

How it works: the console is Pythonista's own OMTextView (the editor uses
the same class, always inside an OMTextEditorView). Views added beside it
stay put while the text scrolls and survive Clear. Pythonista clears a
script's globals when it ends, so live panels are parked on builtins.
This relies on private view classes, so a Pythonista update could move
things.
"""
import builtins
import io

import ui

try:
    from objc_util import ObjCClass, on_main_thread
except ImportError:  # no Objective-C bridge: panels can only be sheets
    ObjCClass = None

    def on_main_thread(function):
        return function

__version__ = '1.0.0'

# --- Look (edit freely) ------------------------------------------------------
COLOURS = {
    'panel': '#16181d',
    'header': '#1e2128',
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
SQUARE_BACKGROUND = (0.12, 0.13, 0.16, 0.85)   # a little see-through over content

# --- Layout (points) ---------------------------------------------------------
SIDE_MARGIN = 12
TOP_MARGIN = 8
INPUT_BAR_CLEARANCE = 90     # keeps panels and squares above the input bar
MINIMUM_PANEL_HEIGHT = 120
SHEET_SIZE = (540, 480)      # the fallback when there is no console

# --- Motion (seconds) --------------------------------------------------------
ANIMATION_SECONDS = 0.25
SLIDE_DISTANCE = 16
CLOCK_SECONDS = 0.5          # how often a panel checks the console's size

# --- Internal names: keep stable so a newer version can clean up an older one -
PANELS_NAME = '_consolekit_panels'   # key -> live Panel
STATE_NAME = '_consolekit_state'     # key -> {'minimised': bool}
VIEW_TAG = 0x434B4954                # 'CKIT': marks every docked view
DARK_INTERFACE = 2                   # UIUserInterfaceStyleDark
DEFAULT_KEY = 'consolekit'


# --- Public API --------------------------------------------------------------
def dock(view, title=None, key=None, height=None, icon=None, chrome=True,
         on_close=None):
    """Dock view in the console and return its Panel.

    title   shown in the header; also the default key
    key     names the panel; docking the same key again replaces it
    height  points tall, sitting on the input bar; None fills the console
    icon    text or emoji for the minimised square (default: title's first letter)
    chrome  False drops the header (no minimise or close buttons)
    on_close  called with the panel when it closes
    """
    key = key or title or DEFAULT_KEY
    close(key)
    panel = Panel(view, title, key, height, icon, chrome, on_close)
    live_panels()[key] = panel
    attach(panel)
    if not panel.docked:
        present_as_sheet(panel)
    return panel


def show(thing, title=None, **options):
    """Dock anything: a ui.View, text, an HTML string, a ui.Image, a PIL
    image or a matplotlib figure (or pyplot itself, for the current figure).

    Without a title it is named by kind (Text, Page, Image, Chart, or the
    view's name), so different kinds sit side by side and a rerun replaces
    each one. Takes the same options as dock().
    """
    if title is None and 'key' not in options:
        title = default_title(thing)
    return dock(view_for(thing), title=title, **options)


def close(key):
    """Close the panel docked under key, if there is one."""
    panel = live_panels().get(key)
    if panel is not None:
        panel.close()


@on_main_thread
def close_all():
    """Close every panel, including strays left by an older version."""
    for panel in list(live_panels().values()):
        panel.close()
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
    image = image_for(thing)
    if image is not None:
        view = ui.ImageView()
        view.image = image
        view.content_mode = ui.CONTENT_SCALE_ASPECT_FIT
        return view
    text = str(thing)
    if looks_like_html(text):
        view = ui.WebView()
        view.load_html(text)
        return view
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


def looks_like_html(text):
    stripped = text.strip()
    return stripped.startswith('<') and stripped.endswith('>')


def default_title(thing):
    """The title show() uses when it is given none."""
    if isinstance(thing, ui.View):
        return thing.name or 'Panel'
    if hasattr(thing, 'savefig'):
        return 'Chart'
    if isinstance(thing, ui.Image) or (hasattr(thing, 'save') and hasattr(thing, 'mode')):
        return 'Image'
    if looks_like_html(str(thing)):
        return 'Page'
    return 'Text'


# --- Layout maths (pure, tested headless) ------------------------------------
def panel_frame(console_frame, height=None):
    """An expanded panel's frame, in the console container's coordinates."""
    x, y, width, console_height = console_frame
    bottom = y + console_height - INPUT_BAR_CLEARANCE
    top = y + TOP_MARGIN
    panel_top = top if height is None else max(top, bottom - height)
    panel_height = max(bottom - panel_top, MINIMUM_PANEL_HEIGHT)
    return (x + SIDE_MARGIN, panel_top, width - 2 * SIDE_MARGIN, panel_height)


def square_origin(console_frame, slot):
    """Where minimised square number slot sits: up the right edge from the bottom."""
    x, y, width, height = console_frame
    left = x + width - SIDE_MARGIN - SQUARE_SIZE
    bottom = y + height - INPUT_BAR_CLEARANCE
    return (left, bottom - SQUARE_SIZE - slot * (SQUARE_SIZE + SQUARE_GAP))


def square_label(title, icon=None):
    if icon:
        return icon
    title = (title or '').strip()
    return title[0].upper() if title else '•'


# --- Live state, parked on builtins ------------------------------------------
def live_panels():
    panels = getattr(builtins, PANELS_NAME, None)
    if panels is None:
        panels = {}
        setattr(builtins, PANELS_NAME, panels)
    return panels


def remembered(key):
    """Per-key state that outlives reruns until Pythonista quits."""
    state = getattr(builtins, STATE_NAME, None)
    if state is None:
        state = {}
        setattr(builtins, STATE_NAME, state)
    return state.setdefault(key, {'minimised': False})


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


# --- Docking -----------------------------------------------------------------
@on_main_thread
def attach(panel):
    """Add the panel and its square beside the console. Sets panel.docked."""
    text_view = find_console_text_view()
    if text_view is None:
        return
    container = text_view.superview()
    panel.console_text_view = text_view
    for view in (panel, panel.square):
        native = view.objc_instance
        native.setTag_(VIEW_TAG)
        # Panels are always drawn dark. Under a light theme UIKit would
        # otherwise use light defaults inside them (black text on dark).
        native.setOverrideUserInterfaceStyle_(DARK_INTERFACE)
        container.addSubview_(native)
    panel.docked = True
    panel.fit(panel.read_console_frame())
    if remembered(panel.key)['minimised']:
        panel.minimised = True
        panel.alpha = 0
        panel.square.alpha = 1
        arrange_squares()
    else:
        panel.slide_in()


def present_as_sheet(panel):
    """Fallback with no console: show the same panel as a sheet."""
    panel.frame = (0, 0, SHEET_SIZE[0], panel.requested_height or SHEET_SIZE[1])
    if panel.header is None:
        panel.present('sheet')
        return
    panel.minimise_button.hidden = True
    try:
        panel.present('sheet', hide_title_bar=True)
    except TypeError:
        panel.present('sheet')


def arrange_squares():
    """Stack every minimised panel's square up the right edge, in dock order."""
    slot = 0
    for panel in live_panels().values():
        if not (panel.docked and panel.minimised and panel.last_console_frame):
            continue
        x, y = square_origin(panel.last_console_frame, slot)
        panel.square.frame = (x, y, SQUARE_SIZE, SQUARE_SIZE)
        native = panel.square.objc_instance
        superview = native.superview()
        if superview is not None:
            superview.bringSubviewToFront_(native)
        slot += 1


# --- Views -------------------------------------------------------------------
class Square(ui.View):
    """A minimised panel. A tap brings the panel back."""

    def __init__(self, panel, text):
        self.panel = panel
        self.alpha = 0
        self.background_color = SQUARE_BACKGROUND
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
    """One docked panel: an optional header, your view, and a minimised square."""

    def __init__(self, content, title, key, height, icon, chrome, on_close):
        self.content = content
        self.key = key
        self.requested_height = height
        self.on_close = on_close
        self.docked = False
        self.minimised = False
        self.console_text_view = None
        self.last_console_frame = None
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

    def set_title(self, text):
        if self.header is not None:
            self.title_label.text = text

    def layout(self):
        top = 0
        if self.header is not None:
            width = self.width
            self.header.frame = (0, 0, width, HEADER_HEIGHT)
            self.title_label.frame = (14, 0, width - 2 * HEADER_HEIGHT - 14, HEADER_HEIGHT)
            self.minimise_button.frame = (width - 2 * HEADER_HEIGHT, 0, HEADER_HEIGHT, HEADER_HEIGHT)
            self.close_button.frame = (width - HEADER_HEIGHT, 0, HEADER_HEIGHT, HEADER_HEIGHT)
            top = HEADER_HEIGHT
        self.content.frame = (0, top, self.width, self.height - top)

    # --- Following the console -------------------------------------------------
    def read_console_frame(self):
        if self.console_text_view is None:
            return None
        frame = self.console_text_view.frame()
        return (frame.origin.x, frame.origin.y, frame.size.width, frame.size.height)

    def update(self):
        """The clock: refit when the console changes size (rotation, iPad split)."""
        frame = self.read_console_frame()
        if frame is not None and frame != self.last_console_frame:
            self.fit(frame)

    def fit(self, console_frame):
        self.last_console_frame = console_frame
        self.frame = panel_frame(console_frame, self.requested_height)
        arrange_squares()

    def bring_to_front(self):
        native = self.objc_instance
        superview = native.superview()
        if superview is not None:
            superview.bringSubviewToFront_(native)

    # --- Motion ----------------------------------------------------------------
    def slide_in(self):
        x, y, width, height = self.frame
        self.frame = (x, y + SLIDE_DISTANCE, width, height)
        self.alpha = 0

        def arrive():
            self.frame = (x, y, width, height)
            self.alpha = 1
        ui.animate(arrive, ANIMATION_SECONDS)

    @on_main_thread
    def minimise(self):
        """Fade down to the square. A view at alpha 0 takes no touches."""
        if not self.docked or self.minimised:
            return
        self.minimised = True
        remembered(self.key)['minimised'] = True
        arrange_squares()
        x, y, width, height = self.frame

        def leave():
            self.alpha = 0
            self.frame = (x, y + SLIDE_DISTANCE, width, height)
            self.square.alpha = 1
        ui.animate(leave, ANIMATION_SECONDS)

    @on_main_thread
    def restore(self):
        if not self.docked or not self.minimised:
            return
        self.minimised = False
        remembered(self.key)['minimised'] = False
        self.bring_to_front()
        arrange_squares()
        target = panel_frame(self.last_console_frame, self.requested_height)

        def arrive():
            self.alpha = 1
            self.frame = target
            self.square.alpha = 0
        ui.animate(arrive, ANIMATION_SECONDS)

    # --- Closing ---------------------------------------------------------------
    def close_by_user(self):
        remembered(self.key)['minimised'] = False
        self.close()

    @on_main_thread
    def close(self):
        """Remove the panel and its square. Never raises."""
        self.update_interval = 0
        try:
            if self.docked:
                self.square.objc_instance.removeFromSuperview()
                self.objc_instance.removeFromSuperview()
            elif self.on_screen:
                ui.View.close(self)
        except Exception:
            pass
        self.forget()
        arrange_squares()
        if self.on_close is not None:
            try:
                self.on_close(self)
            except Exception as error:
                print('consolekit: on_close failed: %r' % error)

    def will_close(self):
        """A sheet closed by its own controls."""
        if not self.docked:
            self.forget()

    def forget(self):
        if live_panels().get(self.key) is self:
            del live_panels()[self.key]