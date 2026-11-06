# consolekit

Put your own panels, buttons and pictures inside Pythonista's console.

One function call docks a `ui` view in the console. It stays put while the text scrolls, survives the Clear button, and keeps working after your script finishes. Minimised panels wait as squares in a tray along the bottom, one tap away.

## Install

Paste this into a new script in Pythonista and run it:

    import urllib.request
    url = ('https://raw.githubusercontent.com/'
           'jackatttack/consolekit/main/install.py')
    source = urllib.request.urlopen(url).read()
    exec(compile(source, 'install.py', 'exec'), {'__name__': '__main__'})

It does two things:

- puts `consolekit.py` in your `site-packages-3` folder, so `import consolekit` works in any script
- adds a `ConsoleKit` folder with a demo and examples, and opens the demo

To update, run the same script again.

## Your first panel

    import ui
    import consolekit

    label = ui.Label()
    label.text = 'Hello from the console'
    label.text_color = 'white'

    consolekit.dock(label, title='Hello', height=140)

Run it with the play button. The panel appears in the console with a minimise button and a close button.

## Show anything

If you just want to look at something, `show()` picks a view for you:

    consolekit.show('Some text')
    consolekit.show('<h1>A web page</h1>')
    consolekit.show(ui.Image.named('test:Lenna'))
    consolekit.show(plt)      # the current matplotlib chart

It handles text, HTML, `ui.Image`, PIL images and matplotlib figures.

## Examples

Run `ConsoleKit/consolekit_demo.py` and tap an example to try it. Each one is a short script in `ConsoleKit/examples` that you can open and change.

- `hello.py`: the smallest panel, one label
- `counter.py`: buttons that do something
- `stopwatch.py`: a live view that keeps ticking
- `show_anything.py`: text, a web page, an image and a chart

## What you can call

`consolekit.dock(view, ...)` docks any `ui.View` and gives you back a panel. All the options are optional:

- `title`: shown in the header
- `height`: how tall the panel is, sitting just above the console's input bar. Leave it out to fill the console.
- `icon`: an emoji for the minimised square. Without one, the square shows the first letter of the title.
- `key`: a name for the panel if you'd rather not use the title (see below)
- `chrome=False`: no header, just your view
- `exclusive=False`: let this panel open alongside others, instead of tucking them into the tray
- `on_close`: a function to call when the panel closes

`consolekit.show(thing, ...)` takes the same options.

On the panel you get back:

- `panel.minimise()` and `panel.restore()`
- `panel.close()`
- `panel.set_title(text)`
- `panel.content` is the view you docked

And two tidy-up functions: `consolekit.close(key)` and `consolekit.close_all()`.

## Good to know

- **Running a script again replaces its panels** instead of adding more. Panels are matched by title (or `key`), so give two panels different titles if you want both.
- **Keep what your panel needs on `self`.** When your script finishes, Pythonista clears its variables, but your panel keeps running. Inside button actions and `update()`, use things you stored on `self` rather than the script's global names. The counter and stopwatch examples show how.
- **One panel is open at a time.** Opening a panel tucks the others into a tray along the bottom of the console. Tap a square in the tray to switch back.
- **Panels last until you close them** or quit Pythonista.
- **It relies on unofficial parts of Pythonista.** A future Pythonista update could change them. If consolekit can't find the console, your panel opens as a normal sheet instead, so your script still works.

## Requirements

Pythonista 3 on iPhone or iPad (tested on 3.4). Nothing else to install.

## License

MIT. See LICENSE.