"""Qt Quick (QML) front end: runs the clock's timers and draws its Board with qml/Main.qml."""
import dataclasses
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PySide6.QtCore import Property, QFileSystemWatcher, QObject, QSize, Qt, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QFontDatabase
from PySide6.QtQuick import QQuickView

from ..core.settings import STYLES

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


def load_fonts():
    if QFontDatabase.addApplicationFont(str(ASSETS_DIR / "fonts" / "Roboto.ttf")) < 0:
        log.warning("Couldn't load the bundled Roboto font; falling back to a system font")


class Display(QObject):
    """Owns the clock's timers and exposes its Board to QML as clock.board."""

    # Carries a FetchResult from the worker thread back to the UI thread.
    fetched = Signal(object)
    boardChanged = Signal()

    def __init__(self, clock, dev=False):
        super().__init__()
        self.clock = clock
        self.dev = dev
        self._board = self._to_qml(clock.board())

        self.executor = ThreadPoolExecutor(max_workers=1)
        self.fetching = None
        self.fetched.connect(self.apply_predictions)

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
        self.update_timer.start(clock.settings.refresh_seconds * 1000)

        self.rotation_timer = QTimer()
        self.rotation_timer.timeout.connect(self.rotate_last_line)
        self.rotation_timer.start(clock.settings.rotation_seconds * 1000)

        self.update_predictions()

    @Property("QVariant", notify=boardChanged)
    def board(self):
        return self._board

    @Slot(int, bool)
    def setLayout(self, lines, grouped):
        """Called by the QML with how many lines fit the screen, and whether to group them by direction."""
        if (lines, grouped) != (self.clock.lines, self.clock.grouped):
            self.clock.lines = lines
            self.clock.grouped = grouped
            self.publish()

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

    def apply_predictions(self, result):
        self.clock.apply(result)
        self.publish()

    def rotate_last_line(self):
        # Publish even if nothing rotated, so the minutes keep counting down.
        self.clock.rotate()
        self.publish()

    def next_style(self):
        settings = self.clock.settings
        settings.style = STYLES[(STYLES.index(settings.style) + 1) % len(STYLES)]
        self.publish()

    def close(self):
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
