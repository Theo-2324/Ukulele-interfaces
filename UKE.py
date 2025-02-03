import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget
from PyQt5.QtGui import QPainter, QPen, QBrush, QColor, QPixmap
from PyQt5.QtCore import Qt, QPointF, QTimer


class UkuleleWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Interactive Ukulele Fretboard")
        self.setGeometry(100, 100, 1200, 400)  # Horizontal layout window size

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Ukulele parameters
        self.strings = 4  # Number of strings
        self.frets = 12   # Number of frets
        self.clicked_points = []  # Store clicked points

        # Load the background image
        self.background_image = QPixmap("/home/theo/Pictures/ukulele-tuning")  # Update the path to your image
        if self.background_image.isNull():
            print("Failed to load background image.")
        else:
            # Scale the background image to fit the widget size
            self.background_image = self.background_image.scaled(self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)

        # Define fretboard coordinates
        self.top_left = QPointF(389, 127)
        self.bottom_left = QPointF(389, 278)
        self.top_right = QPointF(948, 143)
        self.bottom_right = QPointF(949, 252)


        # Define string start points (from top to bottom)
        self.string_start_points = [
            QPointF(389, 141),  # First string
            QPointF(389, 179),  # Second string
            QPointF(389, 223),  # Third string
            QPointF(389, 262)   # Fourth string
        ]
        # Define string end points (from top to bottom)
        self.string_end_points = [
            QPointF(949, 142),  # First string
            QPointF(949, 180),  # Second string
            QPointF(949, 213),  # Third string
            QPointF(949, 242)   # Fourth string
        ]


    def resizeEvent(self, event):
        # Resize the background image when the widget is resized
        if not self.background_image.isNull():
            self.background_image = self.background_image.scaled(self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        super().resizeEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw background image if it's loaded
        if not self.background_image.isNull():
            painter.drawPixmap(0, 0, self.background_image)

        # Draw the fretboard (trapezoid shape)
        painter.setBrush(QBrush(QColor(50, 25, 25)))  # Dark brown wood
        fretboard_polygon = [
            self.top_left,
            self.top_right,
            self.bottom_right,
            self.bottom_left
        ]
        painter.drawPolygon(fretboard_polygon)

        # Draw frets
        painter.setPen(QPen(Qt.white, 2))
        for i in range(1, self.frets + 1):
            # Calculate x positions for frets (linearly spaced between left and right edges)
            x_left = self.top_left.x() + (self.top_right.x() - self.top_left.x()) * (i / self.frets)
            x_right = self.bottom_left.x() + (self.bottom_right.x() - self.bottom_left.x()) * (i / self.frets)

            # Draw the fret line
            painter.drawLine(
                QPointF(x_left, self.top_left.y()),
                QPointF(x_right, self.bottom_left.y())
            )

        # Draw strings (with custom start and end points)
        painter.setPen(QPen(Qt.lightGray, 1))
        for i in range(self.strings):
            # Start point (custom for each string)
            start_point = self.string_start_points[i]

            # End point (custom for each string)
            end_point = self.string_end_points[i]

            # Draw the string line
            painter.drawLine(start_point, end_point)

        # Highlight clicked points
        painter.setPen(QPen(Qt.red, 5))
        for point in self.clicked_points:
            painter.drawPoint(point)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Record clicked point and print its location
            clicked_point = event.pos()
            self.clicked_points.append(clicked_point)
            print(f"Clicked at: {clicked_point}")

            # Set a timer to remove the point after 5 seconds
            QTimer.singleShot(5000, lambda: self.remove_point(clicked_point))
            self.update()  # Redraw the window

    def remove_point(self, point):
        # Remove the point and update the UI
        if point in self.clicked_points:
            self.clicked_points.remove(point)
            self.update()


def main():
    app = QApplication(sys.argv)
    window = UkuleleWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()