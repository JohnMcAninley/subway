import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PySide6.QtWidgets import QLabel, QWidget, QVBoxLayout, QHBoxLayout, QFrame, QSpacerItem, QSizePolicy
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtSvgWidgets import QSvgWidget

BULLETS_DIR = Path(__file__).resolve().parent.parent / "assets" / "bullets"

log = logging.getLogger(__name__)


class SubwayDisplay(QWidget):
    # Carries a FetchResult from the worker thread back to the UI thread.
    fetched = Signal(object)

    def __init__(self, clock, width):
        super().__init__()
        self.clock = clock
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.fetching = None
        self.fetched.connect(self.apply_predictions)
        self.setWindowTitle("NYC Subway Countdown Clock")
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setFixedSize(width, int(width / 3.2))  # Matches 3.2:1 aspect ratio
        background = "white" if clock.settings.theme == "light" else "black"
        self.setStyleSheet(f"background-color: {background};")

        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)
        self.setLayout(layout)

        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_predictions)
        self.update_timer.start(clock.settings.refresh_seconds * 1000)

        self.rotation_timer = QTimer()
        self.rotation_timer.timeout.connect(self.rotate_second_train)
        self.rotation_timer.start(clock.settings.rotation_seconds * 1000)

        self.update_predictions()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()

    def closeEvent(self, event):
        self.executor.shutdown(wait=False, cancel_futures=True)
        super().closeEvent(event)

    def clearLayout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
            elif item.layout() is not None:
                self.clearLayout(item.layout())

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
        self.render_display(self.clock.board())

    def rotate_second_train(self):
        if self.clock.rotate():
            self.render_display(self.clock.board())

    def train_row(self, train, mode, stale):
        row = QWidget()
        hbox = QHBoxLayout()
        hbox.setContentsMargins(0,0,0,0)
        if train.arriving:
            row.setStyleSheet("background-color: black;")

        text_color = "yellow" if train.arriving else "white" if mode=="dark" else "black"
        if stale and not train.arriving:
            text_color = "gray"  # Out of date, e.g. the network is down

        index_label = QLabel(f"{train.number}.")
        index_label.setStyleSheet(
            f"""
            color: {text_color};
            font-weight: 330;
            font-size: 96pt;
            """
        )
        index_label.setAlignment(Qt.AlignCenter)
        index_label.setFixedWidth(85)
        hbox.addWidget(index_label)

        # Train bullet
        bullet = QSvgWidget(str(BULLETS_DIR / f"NYCS-bull-trans-{train.bullet}.svg"))
        bullet.setFixedSize(150, 150)

        # Destination
        dest = QLabel(train.destination)
        dest.setStyleSheet(
            f"""
            color: {text_color};
            font-size: 72pt;
            font-weight: 330;
            letter-spacing: -5px;
            """
        )
        dest.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

        # ETA
        eta_label = QLabel()
        eta_label.setText(f"<span style='font-size:96pt; font-weight: 330;'>{train.minutes}</span><span style='font-size:48pt'> min</span>")
        eta_label.setStyleSheet(f"color: {text_color};")
        eta_label.setAlignment(Qt.AlignVCenter | Qt.AlignRight)

        hbox.addWidget(bullet)
        hbox.addSpacerItem(QSpacerItem(20, 0, QSizePolicy.Fixed, QSizePolicy.Minimum))
        hbox.addWidget(dest, 2)
        hbox.addWidget(eta_label, 1)
        row.setLayout(hbox)
        return row

    def line_separator(self):
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet("color: #CCCCCC; background-color: #CCCCCC;")
        line.setFixedHeight(2)  # Or 1px for super thin
        return line

    def render_display(self, board):
        self.clearLayout(self.layout())
        for i, train in enumerate(board.rows):
            if i:
                self.layout().addWidget(self.line_separator())
            self.layout().addWidget(self.train_row(train, board.theme, board.stale))
