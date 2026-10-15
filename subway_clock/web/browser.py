"""Finding a browser that can draw a page without a window: for scripts/capture.py --web and the JavaScript core's tests."""
import os
import shutil

# Commands, then the usual places.
BROWSERS = ("chromium", "chromium-browser", "google-chrome", "chrome", "msedge")
BROWSER_PATHS = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
)


def find_browser():
    """Chrome, Chromium or Edge, whichever is found first, or None."""
    found = next(filter(None, map(shutil.which, BROWSERS)), None)
    return found or next(filter(os.path.exists, BROWSER_PATHS), None)
