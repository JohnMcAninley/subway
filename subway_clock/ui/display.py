"""Qt Quick (QML) front end: runs the clock's timers and draws its Board with qml/Main.qml."""
import dataclasses
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from PySide6.QtCore import Property, QFileSystemWatcher, QObject, QSize, Qt, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QFontDatabase
from PySide6.QtQuick import QQuickView

from ..core.settings import STYLES, Settings

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
QML_DIR = Path(__file__).resolve().parent / "qml"

log = logging.getLogger(__name__)

# Window sizes to preview with keys 1-5 in --dev mode
PRESETS = {
    Qt.Key_1: QSize(1920, 600),  # 3.2:1 ultra-wide bar
    Qt.Key_2: QSize(1920, 480),  # 4:1 bar
    Qt.Key_3: QSize(1280, 720),  # 16:9 TV or monitor
    Qt.Key_4: QSize(608, 1080),  # 9:16 portrait, like the screens in station entrances
    Qt.Key_5: QSize(360, 1080),  # 1:3 tall portrait
}

# How long to wait before trying again when the schedules can't be fetched at startup.
RETRY_SECONDS = 15

# How long the settings file has to be left alone before it is read again: an editor
# saving it can change it several times over.
SETTLE_MS = 300


def load_fonts():
    if QFontDatabase.addApplicationFont(str(ASSETS_DIR / "fonts" / "Roboto.ttf")) < 0:
        log.warning("Couldn't load the bundled Roboto font; falling back to a system font")


class Closing(Exception):
    """Raised on the worker thread to abandon fetching the schedules when the window closes."""


class Display(QObject):
    """Owns the clock's timers and exposes its Board to QML as clock.board.

    There is no board to show until the first trains have been fetched, and a
    first run has to fetch the schedules before that. Until then clock.startup
    says what to show in its place.

    With settings_path, the settings file is read again whenever it is saved,
    and the changes take effect without a restart (apply_settings).
    """

    # Carries a FetchResult from the worker thread back to the UI thread.
    fetched = Signal(object)
    # From the worker thread fetching the schedules: what it is doing and how far along it is,
    # then how it ended (None, or the exception).
    progressed = Signal(str, float)
    prepared = Signal(object)
    boardChanged = Signal()
    startupChanged = Signal()
    settingsChanged = Signal()

    def __init__(self, clock, dev=False, settings_path=None):
        super().__init__()
        self.clock = clock
        self.dev = dev
        self._board = self._to_qml(clock.board())
        self._startup = {"state": "ready", "title": "", "detail": "", "progress": 0.0}
        self._reported = None
        self.closing = False

        self.executor = ThreadPoolExecutor(max_workers=1)
        self.fetching = None
        self.fetched.connect(self.apply_predictions)
        self.progressed.connect(self.show_progress)
        self.prepared.connect(self.finish_preparing)

        self.view = ClockWindow(self)
        self.view.setTitle("NYC Subway Countdown Clock")
        self.view.setResizeMode(QQuickView.SizeRootObjectToView)
        self.view.statusChanged.connect(self._report_errors)
        self.load_qml()

        if dev:
            # Reload the QML whenever a file in qml/ is saved.
            self.watcher = QFileSystemWatcher([str(p) for p in QML_DIR.iterdir()])
            self.watcher.fileChanged.connect(self.reload_qml)

        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_predictions)
        self.rotation_timer = QTimer()
        self.rotation_timer.timeout.connect(self.rotate_last_line)

        if settings_path is not None:
            self.watch_settings(settings_path)

        if clock.static.ready:
            self.start()
        else:
            self.prepare()

    def start(self):
        self.set_startup("loading", "Loading train times", progress=-1)
        self.update_timer.start(self.clock.settings.refresh_seconds * 1000)
        self.rotation_timer.start(self.clock.settings.rotation_seconds * 1000)
        self.update_predictions()

    @Property("QVariant", notify=boardChanged)
    def board(self):
        return self._board

    @Property("QVariant", notify=startupChanged)
    def startup(self):
        """What to show while there is no board yet.

        state: "ready" (show the board), "loading" or "failed" (waiting to try again)
        title, detail: a line saying what is going on, and a lesser one under it
        progress: how far along loading is, 0 to 1, or -1 if there is no telling
        """
        return self._startup

    def set_startup(self, state, title="", detail="", progress=0.0):
        self._startup = {"state": state, "title": title, "detail": detail, "progress": progress}
        self.startupChanged.emit()

    def prepare(self):
        """Fetch the schedules on the worker thread, with the loading screen up meanwhile."""
        if self.closing:
            return
        self.show_progress("Loading schedules", 0)
        self.executor.submit(self.prepare_static)

    def prepare_static(self):
        try:
            self.clock.static.prepare(self.report_progress)
        except Exception as e:
            self.prepared.emit(e)
        else:
            self.prepared.emit(None)

    def report_progress(self, stage, fraction):
        if self.closing:
            raise Closing
        # A download reports every few kilobytes; only whole percents are worth redrawing for.
        report = (stage, int(fraction * 100) / 100)
        if report != self._reported:
            self._reported = report
            self.progressed.emit(*report)

    def show_progress(self, stage, fraction):
        self.set_startup("loading", stage, "This can take a minute", fraction)

    def finish_preparing(self, error):
        if self.closing:
            return
        if error is None:
            self.start()
            return
        offline = isinstance(error, requests.RequestException)
        log.warning("Fetching the schedules failed, trying again in %s seconds: %r", RETRY_SECONDS, error,
                    exc_info=None if offline else error)
        self.set_startup("failed", "No connection" if offline else "Can't read the schedules", "Trying again shortly")
        QTimer.singleShot(RETRY_SECONDS * 1000, self.prepare)

    @Slot(int, bool)
    def setLayout(self, lines, grouped):
        """Called by the QML with how many lines fit the screen, and whether to group them by direction."""
        if (lines, grouped) != (self.clock.lines, self.clock.grouped):
            self.clock.lines = lines
            self.clock.grouped = grouped
            self.publish()

    @Property(bool, notify=settingsChanged)
    def showStation(self):
        return self.clock.settings.show_station

    @Property(str, constant=True)
    def bulletsUrl(self):
        return QUrl.fromLocalFile(str(ASSETS_DIR / "bullets") + "/").toString()

    def load_qml(self):
        self.view.setInitialProperties({"clock": self})
        self.view.setSource(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))

    def reload_qml(self, path):
        # Editors often save by replacing the file, which drops it from the watcher.
        if path not in self.watcher.files() and Path(path).exists():
            self.watcher.addPath(path)
        log.info("Reloading QML (%s changed)", Path(path).name)
        self.view.engine().clearComponentCache()
        self.load_qml()

    def _report_errors(self, status):
        if status == QQuickView.Error:
            for error in self.view.errors():
                log.error("QML: %s", error.toString())

    def publish(self):
        self._board = self._to_qml(self.clock.board())
        self.boardChanged.emit()

    @staticmethod
    def _to_qml(board):
        values = dataclasses.asdict(board)
        # PySide passes lists to QML as arrays, but not tuples
        values["rows"] = list(values["rows"])
        values["messages"] = list(values["messages"])
        values["routes"] = list(values["routes"])
        values["groups"] = [{**group, "rows": list(group["rows"])} for group in values["groups"]]
        return values

    def update_predictions(self):
        # Fetch off the UI thread so a slow network can't freeze the display.
        if self.fetching is None or self.fetching.done():
            self.fetching = self.executor.submit(self.fetch_predictions)

    def fetch_predictions(self):
        try:
            self.fetched.emit(self.clock.fetch())
        except Exception:
            log.exception("Fetching predictions failed")
            self.fetched.emit(None)

    def apply_predictions(self, result):
        if result is not None and not self.clock.apply(result):
            return  # For stops that have since been replaced; the fetch for the new ones is on its way.
        if self._startup["state"] != "ready":
            # The first fetch is back. If it failed, the board says so itself (it is stale).
            self.set_startup("ready")
        self.publish()

    def rotate_last_line(self):
        # Publish even if nothing rotated, so the minutes keep counting down.
        self.clock.rotate()
        self.publish()

    def next_style(self):
        settings = self.clock.settings
        style = STYLES[(STYLES.index(settings.style) + 1) % len(STYLES)]
        self.apply_settings(dataclasses.replace(settings, style=style))

    def apply_settings(self, settings):
        """Switch to new settings without a restart."""
        old = self.clock.settings
        refetch = self.clock.apply_settings(settings)
        self.settingsChanged.emit()
        # With the timers stopped the schedules are still being fetched, and start() is yet to come.
        if self.update_timer.isActive():
            if settings.rotation_seconds != old.rotation_seconds:
                self.rotation_timer.start(settings.rotation_seconds * 1000)
            if refetch or settings.refresh_seconds != old.refresh_seconds:
                self.update_timer.start(settings.refresh_seconds * 1000)
            if refetch:
                if set(settings.stops) != set(old.stops):
                    self.set_startup("loading", "Loading train times", progress=-1)
                # Not update_predictions, which leaves it to a fetch under way: that one has the old settings.
                self.fetching = self.executor.submit(self.fetch_predictions)
        self.publish()

    def watch_settings(self, path):
        self.settings_path = Path(path)
        # What the file last said, which isn't always what is in use: S in --dev changes the style.
        self.file_settings = self.clock.settings
        # The directory too, for a file that doesn't exist yet or is saved by being replaced.
        self.settings_watcher = QFileSystemWatcher([str(self.settings_path.resolve().parent)])
        self.settings_watcher.fileChanged.connect(self.settings_file_changed)
        self.settings_watcher.directoryChanged.connect(self.settings_file_changed)
        self.settings_timer = QTimer()
        self.settings_timer.setSingleShot(True)
        self.settings_timer.setInterval(SETTLE_MS)
        self.settings_timer.timeout.connect(self.reload_settings)
        self.settings_file_changed()

    def settings_file_changed(self, _path=None):
        file = str(self.settings_path.resolve())
        if file not in self.settings_watcher.files() and self.settings_path.exists():
            self.settings_watcher.addPath(file)
        self.settings_timer.start()

    def reload_settings(self):
        old = self.file_settings
        try:
            settings = Settings.load(self.settings_path)
        except (OSError, ValueError, TypeError, AttributeError) as e:
            log.warning("Can't read %s, keeping the settings as they were: %s", self.settings_path, e)
            return
        if settings == old:
            return
        if settings.data_dir != old.data_dir:
            log.warning("A new data_dir takes effect at the next start")
        log.info("Settings changed (%s)", ", ".join(
            field.name for field in dataclasses.fields(settings)
            if getattr(settings, field.name) != getattr(old, field.name)))
        self.file_settings = settings
        self.apply_settings(settings)

    def close(self):
        self.closing = True
        self.executor.shutdown(wait=False, cancel_futures=True)


class ClockWindow(QQuickView):
    """Esc quits. In --dev mode, 1-5 resize to preview screen shapes and S switches style."""

    def __init__(self, display):
        super().__init__()
        self.display = display

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Escape:
            self.close()
        elif self.display.dev and key in PRESETS:
            self.resize(PRESETS[key])
        elif self.display.dev and key == Qt.Key_S:
            self.display.next_style()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        self.display.close()
        super().closeEvent(event)
