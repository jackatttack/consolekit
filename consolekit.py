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
exclusive=False to let a panel open alongside the others.

Rerun-safe: panels are keyed by title (or key=), so running a script again
replaces its panel instead of stacking another, and a minimised panel comes
back minimised.

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

__version__ = '1.1.0'

# --- Look (edit freely) ------------------------------------------------------
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

    title      shown in the header; also the default key
    key        names the panel; docking the same key again replaces it
    height     points tall, sitting above the tray; None fills the console
    icon       text or emoji for its square in the tray (default: title's first letter)
    chrome     False drops the header (no minimise or close buttons)
    exclusive  True tucks other open panels into the tray when this one opens
    on_close   called with the panel when it closes
    """
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
    """Close every panel, the tray and the backdrop, including strays left
    by an older version."""
    for panel in list(live_panels().values()):
        panel.close()
    remove_parts()
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
def panel_frame(console_frame, height=None, tray_showing=False):
    """An open panel's frame, in the console container's coordinates."""
    x, y, width, console_height = console_frame
    bottom = y + console_height - INPUT_BAR_CLEARANCE
    if tray_showing:
        bottom -= TRAY_HEIGHT + TRAY_GAP
    top = y + TOP_MARGIN
    panel_top = top if height is None else max(top, bottom - height)
    panel_height = max(bottom - panel_top, MINIMUM_PANEL_HEIGHT)
    return (x + SIDE_MARGIN, panel_top, width - 2 * SIDE_MARGIN, panel_height)


def tray_frame(console_frame):
    """The tray: one row along the bottom, just above the input bar."""
    x, y, width, height = console_frame
    bottom = y + height - INPUT_BAR_CLEARANCE
    return (x + SIDE_MARGIN, bottom - TRAY_HEIGHT, width - 2 * SIDE_MARGIN, TRAY_HEIGHT)


def square_origin(slot):
    """Where square number slot sits inside the tray, left to right."""
    return (TRAY_PADDING + slot * (SQUARE_SIZE + SQUARE_GAP), TRAY_PADDING)


def tray_content_width(count):
    """How wide count squares are; the tray scrolls sideways past its width."""
    if count == 0:
        return 0
    return 2 * TRAY_PADDING + count * SQUARE_SIZE + (count - 1) * SQUARE_GAP


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
    """The shared tray, backdrop, console text view and its last frame."""
    return shared(PARTS_NAME)


def remembered(key):
    """Per-key state that outlives reruns until Pythonista quits."""
    return shared(STATE_NAME).setdefault(key, {'minimised': False})


def docked_panels():
    return [panel for panel in live_panels().values() if panel.docked]


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


def make_tray():
    tray = ui.ScrollView()
    tray.background_color = COLOURS['tray']
    tray.border_color = COLOURS['edge']
    tray.border_width = 1
    tray.corner_radius = TRAY_RADIUS
    tray.shows_horizontal_scroll_indicator = False
    tray.shows_vertical_scroll_indicator = False
    tray.alpha = 0
    return tray


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
    if tray is None or tray.objc_instance.superview() is None:
        tray = make_tray()
        container.addSubview_(prepare(tray))
        store['tray'] = tray
    store['text_view'] = text_view
    store['frame'] = read_frame(text_view)


def remove_parts():
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
    """Fit the tray, its squares, the open panels and the backdrop to the console."""
    store = parts()
    tray, backdrop, frame = store.get('tray'), store.get('backdrop'), store.get('frame')
    if tray is None or backdrop is None or frame is None:
        return
    docked = docked_panels()
    tucked = [panel for panel in docked if panel.minimised]
    showing = [panel for panel in docked if not panel.minimised]

    tray.frame = tray_frame(frame)
    for slot, panel in enumerate(tucked):
        x, y = square_origin(slot)
        panel.square.frame = (x, y, SQUARE_SIZE, SQUARE_SIZE)
    for panel in docked:
        panel.square.hidden = not panel.minimised
    tray.content_size = (tray_content_width(len(tucked)), TRAY_HEIGHT)
    backdrop.frame = frame

    def settle():
        tray.alpha = 1 if tucked else 0
        backdrop.alpha = 1 if showing else 0
        for panel in showing:
            panel.frame = panel_frame(frame, panel.requested_height, bool(tucked))
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
    parts()['tray'].add_subview(panel.square)
    panel.docked = True
    if remembered(panel.key)['minimised']:
        panel.minimised = True
        panel.alpha = 0
        relayout(animated=False)
    else:
        panel.open()


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


# --- Views -------------------------------------------------------------------
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
    """One docked panel: an optional header, your view, and its tray square."""

    def __init__(self, content, title, key, height, icon, chrome, exclusive, on_close):
        self.content = content
        self.key = key
        self.requested_height = height
        self.exclusive = exclusive
        self.on_close = on_close
        self.docked = False
        self.minimised = False
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
        remembered(self.key)['minimised'] = False
        if self.exclusive:
            for other in docked_panels():
                if other is not self and not other.minimised:
                    other.tuck()
        self.bring_to_front()
        tray_showing = any(panel.minimised for panel in docked_panels())
        target = panel_frame(parts()['frame'], self.requested_height, tray_showing)
        x, y, width, height = target
        self.frame = (x, y + SLIDE_DISTANCE, width, height)

        def arrive():
            self.frame = target
            self.alpha = 1
        ui.animate(arrive, ANIMATION_SECONDS)
        relayout()

    def tuck(self):
        """Fade down into the tray. A view at alpha 0 takes no touches."""
        self.minimised = True
        remembered(self.key)['minimised'] = True
        x, y, width, height = self.frame

        def leave():
            self.alpha = 0
            self.frame = (x, y + SLIDE_DISTANCE, width, height)
        ui.animate(leave, ANIMATION_SECONDS)

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
        """Remove the panel and its square. Never raises."""
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