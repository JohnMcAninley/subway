import os
import sys
import time

from PySide6.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout, QHBoxLayout, QFrame, QSpacerItem, QSizePolicy
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt, QTimer
from PySide6.QtSvgWidgets import QSvgWidget

from mta_feed import get_predictions
from stops import load_headsigns, load_stop_names
import download


class SubwayDisplay(QWidget):
    def __init__(self, width):
        super().__init__()
        self.setWindowTitle("NYC Subway Countdown Clock")
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setFixedSize(width, width / 3.2)  # Matches 3.2:1 aspect ratio
        #self.setStyleSheet("background-color: black;")
        self.setStyleSheet("background-color: white;")
        self.init_ui()
        self.headsigns = load_headsigns()
        self.headsigns = load_headsigns("gtfs-supplemented/trips.txt", self.headsigns)
        self.stops = load_stop_names()
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_predictions)
        self.update_timer.start(30000)  # Every 30 seconds

        self.predictions = []
        self.rotation_index = 0
        self.rotation_timer = QTimer()
        self.rotation_timer.timeout.connect(self.rotate_second_train)
        self.rotation_timer.start(5000)  # every 3 seconds

        self.update_predictions()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)

        # Status bar
        status = QLabel("Planned Work: No 3 trains after 11:30 PM")
        status.setFont(QFont("Helvetica", 20))
        status.setStyleSheet("color: yellow;")
        status.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        status.setFixedHeight(50)
        layout.addWidget(self.line_separator())
        layout.addWidget(status)

        self.setLayout(layout)

    def clearLayout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
            elif item.layout() is not None:
                self.clearLayout(item.layout())

    def update_predictions(self):

        if download.download_if_newer_zip("https://rrgtfsfeeds.s3.amazonaws.com/gtfs_supplemented.zip", "gtfs_supplemented.zip"):
            download.unzip_and_replace("gtfs_supplemented.zip", "gtfs-supplemented")
            self.headsigns = load_headsigns("gtfs-supplemented/trips.txt", self.headsigns)
        
        preds = get_predictions("633S")
        now = time.time()
        upcoming = sorted([p for p in preds if p['arrival_time'] >= now], key=lambda p: p['arrival_time'])

        self.predictions = upcoming[:5]
        self.rotation_index = 1  # Reset rotation to 2nd train

        self.render_display()

    def train_row(self, train_number, destination, eta, index, mode="dark", highlight=False):
        row = QWidget()
        hbox = QHBoxLayout()
        #hbox.setSpacing(40)
        hbox.setContentsMargins(0,0,0,0)
        if highlight:
            row.setStyleSheet("background-color: black;")

        text_color = "yellow" if highlight else "white" if mode=="dark" else "black"

        index_label = QLabel(f"{index}." if index is not None else "")
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
        bullet_id = train_number.upper().replace("X", "d")
        svg_path = os.path.join("bullets-cropped", f"NYCS-bull-trans-{bullet_id}.svg")
        bullet = QSvgWidget(svg_path)
        bullet.setFixedSize(150, 150)

        # Destination
        dest = QLabel(destination)
        #dest.setFont(QFont("Helvetica", 72))
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
        eta_label.setText(f"<span style='font-size:96pt; font-weight: 330;'>{eta}</span><span style='font-size:48pt'> min</span>")
        #eta_label.setFont(QFont("Helvetica", 60))
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
        #line.setStyleSheet("color: white; background-color: white;")
        line.setStyleSheet("color: #CCCCCC; background-color: #CCCCCC;")
        line.setFixedHeight(2)  # Or 1px for super thin
        return line
    
    def render_display(self):
        now = time.time()
        self.clearLayout(self.layout())  # Reset layout
        layout = QVBoxLayout()
        layout.setSpacing(0)
        #layout.setContentsMargins(20, 20, 20, 20)

        # First train (always static)
        if self.predictions:
            pred = self.predictions[0]
            train_number = pred['route_id']
            minutes = (pred['arrival_time'] - time.time()) / 60.0
            headsign = self.headsigns.get(pred['trip_id'], "Unknown")
            row = self.train_row(train_number, headsign, int(minutes), 1, "light", minutes < 1)
            self.layout().addWidget(row)
            self.layout().addWidget(self.line_separator())

        # Second train (cycled)
        if len(self.predictions) > 1:
            idx = self.rotation_index % len(self.predictions)
            pred = self.predictions[idx]
            train_number = pred['route_id']
            minutes = (pred['arrival_time'] - time.time()) / 60.0
            headsign = self.headsigns.get(pred['trip_id'], "Unknown")
            row = self.train_row(train_number, headsign, int(minutes), idx + 1, "light", minutes < 1)
            self.layout().addWidget(row)
            self.layout().addWidget(self.line_separator())

        self.setLayout(layout)
    
    def rotate_second_train(self):
        if len(self.predictions) > 2:
            self.rotation_index += 1
            if self.rotation_index >= len(self.predictions):
                self.rotation_index = 1
            self.render_display()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    screen = app.primaryScreen()
    width = screen.size().width()
    display = SubwayDisplay(width)
    display.show()
    sys.exit(app.exec())
