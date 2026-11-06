"""
Install or update consolekit in Pythonista.

Run it again at any time to update to the latest version from GitHub.

    Library:   site-packages-3/consolekit.py   so import consolekit works in any script
    Examples:  Documents/ConsoleKit/           run consolekit_demo.py to try them

Options (for testing):
    --from-folder PATH   install from a local copy instead of GitHub
    --target PATH        put the examples somewhere other than Documents/ConsoleKit
    --library PATH       put consolekit.py somewhere other than site-packages-3
    --no-open            do not open the demo afterwards
"""

import argparse
import io
import os
import shutil
import sys
import tempfile
import urllib.request
import zipfile


REPOSITORY = "jackatttack/consolekit"
REF = "main"
APP_FOLDER = "ConsoleKit"
LAUNCHER = "consolekit_demo.py"
LIBRARY_FILE = "consolekit.py"

# Files earlier releases shipped that are gone now; an update removes them.
# Until 1.2.0 a copy of consolekit.py sat in the ConsoleKit folder, where it
# shadowed the site-packages copy for scripts run from that folder.
RETIRED_FILES = ("consolekit.py",)


def documents():
    return os.path.expanduser("~/Documents")


def default_target():
    return os.path.join(documents(), APP_FOLDER)


def default_library():
    """Pythonista's site-packages-3 folder, which every script can import from."""
    preferred = os.path.join(documents(), "site-packages-3")
    if os.path.isdir(preferred):
        return preferred
    for path in sys.path:
        if os.path.basename(path.rstrip(os.sep)) == "site-packages-3" and os.access(path, os.W_OK):
            return path
    return preferred


def download_release(work_dir):
    """Download the repository zip, unpack it, return the release folder."""
    url = "https://codeload.github.com/{}/zip/refs/heads/{}".format(REPOSITORY, REF)
    print("Downloading {} ...".format(REPOSITORY))
    with urllib.request.urlopen(url) as response:
        data = response.read()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        archive.extractall(work_dir)
        top = archive.namelist()[0].split("/")[0]
    return os.path.join(work_dir, top)


def install_examples(release, target):
    """Replace every top-level item the release ships, except the library
    itself (that lives only in site-packages-3); leave anything else."""
    os.makedirs(target, exist_ok=True)
    shipped = sorted(name for name in os.listdir(release)
                     if not name.startswith(".") and name != LIBRARY_FILE)
    for name in shipped:
        source = os.path.join(release, name)
        destination = os.path.join(target, name)
        if os.path.isdir(destination) and not os.path.islink(destination):
            shutil.rmtree(destination)
        elif os.path.exists(destination):
            os.remove(destination)
        if os.path.isdir(source):
            shutil.copytree(source, destination,
                            ignore=shutil.ignore_patterns("__pycache__"))
        else:
            shutil.copy2(source, destination)
    for name in RETIRED_FILES:
        path = os.path.join(target, name)
        if name not in shipped and os.path.isfile(path):
            os.remove(path)
    return shipped


def install_library(release, library):
    """Copy consolekit.py into the library folder and return its path."""
    os.makedirs(library, exist_ok=True)
    destination = os.path.join(library, LIBRARY_FILE)
    shutil.copy2(os.path.join(release, LIBRARY_FILE), destination)
    sys.modules.pop("consolekit", None)   # the next import gets the new copy
    return destination


def read_version(folder):
    try:
        with open(os.path.join(folder, "VERSION")) as handle:
            return handle.read().strip()
    except OSError:
        return "unknown version"


def open_launcher(path):
    """Open the demo in Pythonista's editor; quietly skip elsewhere."""
    try:
        import editor
        editor.open_file(path)
    except Exception:
        pass


def main(argv=None):
    parser = argparse.ArgumentParser(description="Install or update consolekit")
    parser.add_argument("--from-folder")
    parser.add_argument("--target")
    parser.add_argument("--library")
    parser.add_argument("--no-open", action="store_true")
    args, _ = parser.parse_known_args(argv)

    target = os.path.abspath(args.target or default_target())
    library = os.path.abspath(args.library or default_library())
    work_dir = tempfile.mkdtemp(prefix="consolekit_install_")
    try:
        if args.from_folder:
            release = os.path.abspath(args.from_folder)
        else:
            release = download_release(work_dir)
        version = read_version(release)
        install_examples(release, target)
        library_path = install_library(release, library)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

    print("")
    print("Installed consolekit {}".format(version))
    print("    Library:  " + library_path)
    print("    Examples: " + target)
    print("Try it: run {} in the {} folder.".format(LAUNCHER, APP_FOLDER))
    print("Run the installer again any time to update. If you already used")
    print("consolekit since opening Pythonista, restart it to load the new version.")
    if not args.no_open:
        open_launcher(os.path.join(target, LAUNCHER))
    return 0


if __name__ == "__main__":
    main()