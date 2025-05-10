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
        self.update_predictions()
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_predictions)
        self.update_timer.start(30000)  # Every 30 seconds

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
        
        preds = get_predictions("R36")
        now = time.time()
        upcoming = sorted([p for p in preds if p['arrival_time'] >= now], key=lambda p: p['arrival_time'])

        self.clearLayout(self.layout())  # Reset layout

        layout = QVBoxLayout()
        layout.setSpacing(0)
        #layout.setContentsMargins(20, 20, 20, 20)

        for i, pred in enumerate(upcoming[:2], start=1):  # Show up to 5 trains
            train_number = pred['route_id']
            destination = self.stops.get(pred['stop_id'], pred['stop_id'])
            minutes = (pred['arrival_time'] - time.time()) / 60.0
            #eta_text = "Arriving" if minutes <= 1.0 else f"{int(minutes)} min"
            headsign = self.headsigns.get(pred['trip_id'], "Unknown")
            #destination_name = self.stops.get(last_stop_id, "Unknown")
            print(f"route_id={pred['route_id']}, trip_id={pred['trip_id']}, headsign={headsign}")
            row = self.train_row(train_number, headsign, int(minutes), i, "light", minutes < 1)
            #self.layout().addLayout(row)
            self.layout().addWidget(row)
            self.layout().addWidget(self.line_separator())

    def train_row(self, train_number, destination, eta, index, mode="dark", highlight=False):
        row = QWidget()
        hbox = QHBoxLayout()
        #hbox.setSpacing(40)
        hbox.setContentsMargins(0,0,0,0)

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
        svg_path = os.path.join("bullets-cropped", f"NYCS-bull-trans-{train_number.upper()}.svg")
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

if __name__ == "__main__":
    app = QApplication(sys.argv)
    screen = app.primaryScreen()
    width = screen.size().width()
    display = SubwayDisplay(width)
    display.show()
    sys.exit(app.exec())
