# consolekit

Put your own panels, buttons and pictures inside Pythonista's console.

One function call docks a `ui` view in the console. It stays put while the text scrolls, survives the Clear button, and keeps working after your script finishes. Minimised panels wait as squares in a tray along the bottom, one tap away.

    import consolekit

    consolekit.show('Hello from the console')     # text, HTML, images, charts
    panel = consolekit.dock(my_view, title='Tools', icon='🧰')
    panel.add_button('⟳', lambda panel: panel.content.refresh())
    panel.minimise()                              # tap its square to bring it back
    consolekit.close_all()

## Install

Paste this into a new script in Pythonista and run it:

    import urllib.request
    url = ('https://raw.githubusercontent.com/'
           'jackatttack/consolekit/main/install.py')
    source = urllib.request.urlopen(url).read()
    exec(compile(source, 'install.py', 'exec'), {'__name__': '__main__'})

It does two things:

- puts `consolekit.py` in your `site-packages-3` folder, so `import consolekit` works in any script
- adds a `ConsoleKit` folder with a demo, examples and tests, and opens the demo

To update, run the same script again, then restart Pythonista so your scripts load the new version.

## Try the examples

Run `ConsoleKit/consolekit_demo.py` and tap an example. Each one is a short script in `ConsoleKit/examples` that you can open, change and run again.

| Example | Shows you |
|---|---|
| `hello.py` | the smallest app: one line |
| `flash_cards.py` | a times-table quiz in a dozen lines, with header buttons |
| `counter.py` | buttons that do something |
| `stopwatch.py` | a live view that keeps ticking, and rests while tucked away |
| `notes.py` | typing in a panel, plus your own header button |
| `live_show.py` | `show()` in a loop, updating one panel in place |
| `show_anything.py` | text, a web page, an image and a chart |

The demo's last row closes every panel.

## Your first panel

    import ui
    import consolekit

    label = ui.Label()
    label.text = 'Hello from the console'
    label.text_color = 'white'

    consolekit.dock(label, title='Hello', height=140)

Run it with the play button. The panel appears in the console with a minimise button and a close button. Run it again and it replaces itself rather than stacking a second copy.

## Show anything

If you just want to look at something, `show()` picks a view for you:

    consolekit.show('Some text')
    consolekit.show('<h1>A web page</h1>')
    consolekit.show(ui.Image.named('test:Lenna'))
    consolekit.show(plt)                  # the current matplotlib chart
    consolekit.show('my_panel.pyui')      # a view made in the UI designer

It handles text, HTML, `ui.Image`, PIL images, matplotlib figures and `.pyui` files. One short line of text shows big and centred, like a display; longer text scrolls. An HTML fragment gets a dark style to match the panel.

Calling `show()` again with the same title updates that panel in place, so it works inside a loop:

    for step in range(1, 11):
        consolekit.show('Step %d of 10' % step, title='Progress')
        time.sleep(0.5)

## The whole API

`consolekit.dock(view, ...)` docks a `ui.View` (or the path of a `.pyui` file) and gives you back a panel. All the options are optional:

- `title`: shown in the header
- `height`: how tall the panel is, including its 40-point header. Leave it out to fill the console.
- `icon`: an emoji for the minimised square. Without one, the square shows the first letter of the title.
- `key`: a name for the panel if you'd rather not use the title
- `chrome=False`: no header, just your view
- `exclusive=False`: open alongside other panels instead of tucking them away. Open panels stack upwards, newest on top.
- `on_close`: a function to call with the panel when it closes

`consolekit.show(thing, ...)` takes the same options.

`consolekit.get(key)` gives you a docked panel by its title (or key), or `None`.

`consolekit.close(key)` and `consolekit.close_all()` tidy up.

On a panel:

- `panel.minimise()`, `panel.restore()` and `panel.close()`
- `panel.set_title(text)` and `panel.set_height(points)`
- `panel.show(thing)` shows anything `show()` takes in this panel, in place of what was there
- `panel.set_content(view)` swaps the view inside, keeping the panel where it is
- `panel.add_button(symbol, action)` adds a button to the header; `action` is called with the panel. Adding the same symbol again just gives it the new action, so reruns never double up.
- `panel.content` is the view you docked

## Extending

Your view can define any of these, and consolekit calls them with the panel:

    class MyView(ui.View):
        def panel_opened(self, panel): ...   # docked, or back from the tray
        def panel_tucked(self, panel): ...   # minimised into the tray
        def panel_closed(self, panel): ...   # gone for good

Colours and sizes are plain constants at the top of `consolekit.py`. Change them before you dock your first panel:

    consolekit.COLOURS['accent'] = '#4caf50'

consolekit is one file with no dependencies, so you can also copy `consolekit.py` into your own project and ship it alongside.

## Good to know

- **Keep what your panel needs on `self`.** When your script finishes, Pythonista clears its variables, but your panel keeps running. Inside button actions and `update()`, use things you stored on `self`, or on the panel itself (`panel.deck = ...`), rather than the script's global names. The flash cards, counter and stopwatch examples show how. For a bigger panel, put its class in a module of its own and import it: an imported module keeps its names.
- **Panels are matched by title** (or `key`), so give two panels different titles if you want both.
- **One panel is open at a time** unless you pass `exclusive=False`. Opening a panel tucks the others into the tray. Tap a square to switch back; drag the tray sideways when it fills up.
- **Panels last until you close them** or quit Pythonista.
- **No console, no problem.** If consolekit can't find the console (another app, or a future Pythonista update), your panel opens as a normal sheet instead, so your script still works.

## How it works

Pythonista has no official way to put views in the console, so consolekit finds one.

The console is drawn by Pythonista's own private text view class. The editor uses the same class, so consolekit walks the app's window views with `objc_util` and picks the one that isn't inside the editor. Your view is added beside that text view rather than inside it. It floats above the text, stays still while the text scrolls, and outlives the Clear button.

Two more tricks keep it alive:

- Pythonista wipes a script's variables when it ends, so live panels are parked on Python's `builtins`, where the next run can find and replace them.
- A ui view's `update()` clock keeps running even when the view was never presented, so panels use it to notice the console changing size.

Because it leans on private parts of Pythonista, a future update could move things. That's why the sheet fallback exists.

## Checking it on your device

`ConsoleKit/tests/device_walkthrough.py` docks real panels, steps through every interaction, and prints what passed once it has tidied up. Run it from the editor with the play button. `tests/smoke_consolekit.py` checks the layout maths without docking anything.

## Requirements

Pythonista 3 on iPhone or iPad (tested on 3.4). Nothing else to install.

## License

MIT. See LICENSE.