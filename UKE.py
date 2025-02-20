import sys
import fluidsynth
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QLabel, QVBoxLayout, QHBoxLayout
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QPixmap
from PySide6.QtCore import Qt, QPointF, QTimer, QDateTime

class UkuleleWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Interactive Ukulele Fretboard")
        self.setGeometry(100, 100, 1200, 400)  # Horizontal layout window size
        self.showMaximized()  # Maximize the window 

        # Ukulele parameters
        self.strings = 4  # Number of strings
        self.frets = 12   # Number of frets
        self.clicked_points = []  # Store clicked points
        self.recorded_sequence = []  # Store recorded sequence of clicks (with timestamps)
        self.recording_start_time = 0  # Track when recording starts for relative timestamps

        # Load the background image
        self.background_image = QPixmap("/home/theo/Pictures/ukulele-tuning")  # Update the path to your image
        if self.background_image.isNull():
            print("Failed to load background image.")
        else:
            # Scale the background image to fit the widget size
            self.background_image = self.background_image.scaled(self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)

        # Define fretboard coordinates
        self.top_left = QPointF(619, 314)
        self.bottom_left = QPointF(621, 698)
        self.top_right = QPointF(1527, 359)
        self.bottom_right = QPointF(1532, 645)

        # Define string start points (from top to bottom)
        self.string_start_points = [
            QPointF(619, 357),  # First string
            QPointF(619, 456),  # Second string
            QPointF(619, 561),  # Third string
            QPointF(619, 650)   # Fourth string
        ]
        # Define string end points (from top to bottom)
        self.string_end_points = [
            QPointF(1530, 387),  # First string
            QPointF(1530, 468),  # Second string
            QPointF(1530, 546),  # Third string
            QPointF(1530, 625)   # Fourth string
        ]

        # Playback controls
        self.is_playing = False
        self.is_recording = False
        self.playback_progress = 0  # Progress for the playback bar
        self.playback_timer = QTimer()
        self.playback_timer.timeout.connect(self.update_playback)
        self.playback_start_time = 0  # Track when playback starts
        self.current_playback_index = 0  # Track current event during playback

        # Initialize fluidsynth
        self.fs = fluidsynth.Synth()
        self.fs.start(driver="alsa")  # Use 'alsa' for Linux

        # Load SoundFont file with error handling
        try:
            soundfont_path = "/home/theo/Ukulele soundfiles/Soundfonts/Ukulele_little-scale.sf2"
            self.sfid = self.fs.sfload(soundfont_path)
            if self.sfid == -1:
                raise Exception("Failed to load SoundFont")
            self.fs.program_select(0, self.sfid, 0, 0)  # Select the first instrument
        except Exception as e:
            self.sfid = None
            print(f"Error loading SoundFont: {e}")
    
        # Define notes for each string and fret
        self.ukulele_notes = [
            ["G4", "G#4", "A4", "A#4", "B4", "C5", "C#5", "D5", "D#5", "E5", "F5", "F#5"],  # String 1: G
            ["C4", "C#4", "D4", "D#4", "E4", "F4", "F#4", "G4", "G#4", "A4", "A#4", "B4"],  # String 2: C
            ["E4", "F4", "F#4", "G4", "G#4", "A4", "A#4", "B4", "C5", "C#5", "D5", "D#5"],  # String 3: E
            ["A4", "A#4", "B4", "C5", "C#5", "D5", "D#5", "E5", "F5", "F#5", "G5", "G#5"],  # String 4: A
        ]

        # Volume control
        self.volume = 100  # Default volume (0-127, MIDI standard)
        self.update_volume()

        # Info box for messages
        self.info_box = QLabel("Messages will appear here.", self)
        self.info_box.setStyleSheet("border: 1px solid black; padding: 10px; font-size: 14px;")
        self.info_box.setFont(QFont("Arial", 12))

        # Buttons
        self.play_button = QPushButton("Play", self)
        self.play_button.setFont(QFont("Arial", 12))
        self.play_button.setFixedSize(200, 60)
        self.play_button.clicked.connect(self.toggle_playback)

        self.record_button = QPushButton("Record", self)
        self.record_button.setFont(QFont("Arial", 12))
        self.record_button.setFixedSize(200, 60)
        self.record_button.clicked.connect(self.toggle_recording)

        self.volume_up_button = QPushButton("Volume +", self)
        self.volume_up_button.setFont(QFont("Arial", 12))
        self.volume_up_button.setFixedSize(200, 60)
        self.volume_up_button.clicked.connect(self.increase_volume)

        self.volume_down_button = QPushButton("Volume -", self)
        self.volume_down_button.setFont(QFont("Arial", 12))
        self.volume_down_button.setFixedSize(200, 60)
        self.volume_down_button.clicked.connect(self.decrease_volume)

        # Layout for buttons
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.play_button)
        button_layout.addWidget(self.record_button)
        button_layout.addWidget(self.volume_up_button)
        button_layout.addWidget(self.volume_down_button)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self.info_box)
        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(self.rect(), self.background_image)

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
        painter.setPen(QPen(Qt.lightGray, 2))  # Adjust the thickness and color of the strings
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

        # Draw the playback bar at the bottom
        playback_y = self.height() - 250  # Position in relation to the bottom of the window
        playback_width = self.width() - 500  # Full width of the window
        playback_x = 255 # Position in relation to the left of the window
        playback_height = 20  # Fixed height of the playback bar

        # Background of playback bar
        painter.setBrush(QBrush(QColor(200, 200, 200))) # Light gray
        painter.drawRect(playback_x, playback_y, playback_width, playback_height)

        # Playback progress
        if self.is_playing or self.playback_progress > 0:
            progress_width = int((self.playback_progress / 100) * playback_width)
            painter.setBrush(QBrush(QColor(0, 255, 0)))  # Green for progress
            painter.drawRect(playback_x, playback_y, progress_width, playback_height)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Record clicked point and print its location
            clicked_point = event.pos()
            self.clicked_points.append(clicked_point)
            print(f"Clicked at: {clicked_point}")

            # Record the click with a timestamp if recording is active
            if self.is_recording:
                timestamp = QDateTime.currentMSecsSinceEpoch() - self.recording_start_time
                self.recorded_sequence.append((clicked_point, timestamp))
                print(f"Recorded click at {clicked_point} with timestamp {timestamp}")

            # Determine which string and fret was clicked
            string_index = self.get_string_index(clicked_point)
            if string_index is not None:
                fret_index = self.get_fret_index(clicked_point, string_index)
                if fret_index is not None:
                    note = self.ukulele_notes[string_index][fret_index]
                    self.play_note(note)

            # Set a timer to remove the point after 5 seconds
            QTimer.singleShot(5000, lambda: self.remove_point(clicked_point))
            self.update()  # Redraw the window
    
    def play_note(self, note):
        if self.sfid is not None:
            self.info_box.setText("SoundFont not loaded. Cannot play note.")
            return

            # Map note to MIDI note number
        note_map = {
            "C4": 60, "C#4": 61, "D4": 62, "D#4": 63, "E4": 64, "F4": 65, "F#4": 66, "G4": 67, "G#4": 68, "A4": 69, "A#4": 70, "B4": 71,
            "C5": 72, "C#5": 73, "D5": 74, "D#5": 75, "E5": 76, "F5": 77, "F#5": 78, "G5": 79, "G#5": 80, "A5": 81, "A#5": 82, "B5": 83
        }        
        midi_note = note_map.get(note,60)
        self.fs.noteon(0, midi_note, 127)  # Play the note with full velocity
        QTimer.singleShot(500, lambda: self.fs.noteoff(0, midi_note))  # Stop the note after 500ms
        
    def remove_point(self, point):
        # Remove the point and update the UI
        if point in self.clicked_points:
            self.clicked_points.remove(point)
            self.update()

    def toggle_playback(self):
        if self.is_playing:
            self.stop_playback()
        else:
            if not self.recorded_sequence:
                self.info_box.setText("No recorded sequence to play.")
                return

            self.is_playing = True
            self.play_button.setText("Stop")
            self.playback_progress = 0  # Reset progress
            self.playback_timer.start(50)  # Update every 50ms for smoother progress
            self.start_playback()  # Start playback from the beginning 

    def start_playback(self):
        if not self.recorded_sequence:
            self.info_box.setText("No recorded sequence to play")
            return
        self.is_playing = True
        self.playback_start_time = QDateTime.currentMSecsSinceEpoch()
        self.current_playback_index = 0
        self.playback_timer.start(10)  # Update playback every 10 ms
        self.info_box.setText("Playback started")
        print("Playback started")

    def update_playback(self):
        if self.is_playing and self.current_playback_index < len(self.recorded_sequence):
            point, timestamp = self.recorded_sequence[self.current_playback_index]
            current_time = QDateTime.currentMSecsSinceEpoch() - self.playback_start_time

            if current_time >= timestamp:
                self.clicked_points.append(point)
                self.current_playback_index += 1
                self.update()  # Redraw the window

        if self.current_playback_index >= len(self.recorded_sequence):
            self.stop_playback()
            self.info_box.setText("Playback finished")
            print("Playback finished")

    def stop_playback(self):
        self.is_playing = False
        self.playback_timer.stop()
        self.info_box.setText("Playback stopped")
        print("Playback stopped")

    def toggle_recording(self):
        if self.is_recording:
            self.stop_recording()
        else:
            self.start_recording()

    def clear_recording(self):
        self.recorded_sequence = []  # Clear the recorded sequence
        self.info_box.setText("Recording cleared.")#


    def increase_volume(self):
        #Increase volume by 10, capped at 127.
        self.volume = min(self.volume + 10, 127)
        self.update_volume()
        self.info_box.setText(f"Volume increased to {self.volume}")

    def decrease_volume(self):
        #Decrease volume by 10, capped at 0.
        self.volume = max(self.volume - 10, 0)
        self.update_volume()
        self.info_box.setText(f"Volume decreased to {self.volume}")

    def update_volume(self):
        #Update the volume in fluidsynth.
        if self.sfid is not None:
            self.fs.cc(0, 7, self.volume)  # MIDI CC 7 is the volume controller
    


    def start_recording(self):
        self.is_recording = True
        self.recording_start_time = QDateTime.currentMSecsSinceEpoch()
        self.recorded_sequence = []  # Clear any previous recordings
        self.info_box.setText("Recording started")
        print("Recording started")

    def stop_recording(self):
        self.is_recording = False
        self.info_box.setText("Recording stopped")
        print("Recording stopped")

    
    
    
    

    
    

    
    
    
    def get_string_index(self, point):
        # Determine which string was clicked
        for i in range(self.strings):
            # Check if the click is near the string (within a small vertical range)
            if (self.string_start_points[i].y() - 10 <= point.y() <= self.string_start_points[i].y() + 10):
                return i
        return None

    def get_fret_index(self, point, string_index):
        # Determine which fret gap was clicked for the specific string
        for i in range(self.frets):
            # Calculate x positions for frets (linearly spaced between left and right edges for the specific string)
            x_left = self.string_start_points[string_index].x() + (self.string_end_points[string_index].x() - self.string_start_points[string_index].x()) * (i / self.frets)
            next_x_left = self.string_start_points[string_index].x() + (self.string_end_points[string_index].x() - self.string_start_points[string_index].x()) * ((i + 1) / self.frets)
            if x_left <= point.x() <= next_x_left:
                return i
        return None

def main():
    app = QApplication(sys.argv)
    window = UkuleleWidget()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
