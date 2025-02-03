import sys
import fluidsynth
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QPushButton, QLabel
from PyQt5.QtGui import QPainter, QPen, QBrush, QColor, QFont
from PyQt5.QtCore import Qt, QTimer, QDateTime


class GridWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("8x8 Ukulele Grid with Playback and Controls")
        self.setGeometry(100, 100, 800, 800)  # Adjusted height for layout

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Grid parameters
        self.rows = 4  # 4 rows for the ukulele notes
        self.columns = 8  # 8 columns
        self.cell_size = self.width() // self.columns  # Size of each grid cell
        self.clicked_cells = []  # Store clicked cells as (row, column)
        self.recorded_sequence = []  # Store recorded sequence of clicks (with timestamps)
        self.recording_start_time = 0  # Track when recording starts for relative timestamps

        # Playback controls
        self.is_playing = False
        self.is_recording = False
        self.playback_progress = 0  # Progress for the playback bar
        self.playback_timer = QTimer()
        self.playback_timer.timeout.connect(self.update_playback)
        self.playback_start_time = 0  # Track when playback starts
        self.current_playback_index = 0  # Track current event during playback

        # Notes for each string and fret
        self.ukulele_notes = [
            ["G4", "G#4", "A4", "A#4", "B4", "C5", "C#5", "D5"],  # String 1: G
            ["C4", "C#4", "D4", "D#4", "E4", "F4", "F#4", "G4"],  # String 2: C
            ["E4", "F4", "F#4", "G4", "G#4", "A4", "A#4", "B4"],  # String 3: E
            ["A4", "A#4", "B4", "C5", "C#5", "D5", "D#5", "E5"],  # String 4: A
        ]

        # Initialize fluidsynth
        self.fs = fluidsynth.Synth()
        self.fs.start(driver="alsa")  # Use 'alsa' for Linux, 'coreaudio' for macOS, 'dsound' for Windows
        self.sfid = self.fs.sfload("path/to/your/soundfont.sf2")  # Replace with the path to your SoundFont
        self.fs.program_select(0, self.sfid, 0, 0)  # Select the first instrument (usually a piano)

        # Info box for messages
        self.info_box = QLabel("Messages will appear here.", self)
        self.info_box.setGeometry(250, 450, 300, 50)  # Positioned in the middle
        self.info_box.setStyleSheet("border: 1px solid black; padding: 10px; font-size: 14px;")
        self.info_box.setFont(QFont("Arial", 12))

        # Buttons
        self.play_button = QPushButton("Play", self)
        self.play_button.setGeometry(50, 450, 150, 50)  # Positioned to the left of the info box
        self.play_button.setFont(QFont("Arial", 12))
        self.play_button.clicked.connect(self.toggle_playback)

        self.record_button = QPushButton("Record", self)
        self.record_button.setGeometry(600, 450, 150, 50)  # Positioned to the right of the info box
        self.record_button.setFont(QFont("Arial", 12))
        self.record_button.clicked.connect(self.toggle_recording)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw the 4x8 grid for notes
        painter.setPen(QPen(Qt.black, 2))
        for row in range(4):  # First 4 rows for the ukulele notes
            for col in range(self.columns):
                x = col * self.cell_size
                y = row * self.cell_size + 20  # Small offset for the top margin
                painter.drawRect(x, y, self.cell_size, self.cell_size)

                # Draw note labels in each cell
                painter.setFont(QFont("Arial", 12))
                painter.drawText(
                    x + self.cell_size // 4,
                    y + self.cell_size // 2,
                    self.ukulele_notes[row][col],
                )

        # Highlight clicked cells
        painter.setBrush(QBrush(QColor(255, 0, 0, 128)))  # Semi-transparent red
        for cell in self.clicked_cells:
            row, col = cell
            x = col * self.cell_size
            y = row * self.cell_size + 20  # Offset for top margin
            painter.drawRect(x, y, self.cell_size, self.cell_size)

        # Draw the playback bar at the bottom
        playback_y = 500  # Positioned closer to the grid
        playback_width = self.width() - 100
        playback_x = 50
        playback_height = 20

        # Background of playback bar
        painter.setBrush(QBrush(QColor(200, 200, 200)))
        painter.drawRect(playback_x, playback_y, playback_width, playback_height)

        # Playback progress
        if self.is_playing or self.playback_progress > 0:
            progress_width = int((self.playback_progress / 100) * playback_width)
            painter.setBrush(QBrush(QColor(0, 255, 0)))  # Green for progress
            painter.drawRect(playback_x, playback_y, progress_width, playback_height)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Calculate the clicked cell
            x, y = event.x(), event.y()
            col = x // self.cell_size
            row = (y - 20) // self.cell_size  # Adjust for the top margin

            # Ensure the click is within bounds (first 4 rows)
            if 0 <= row < 4 and 0 <= col < self.columns:
                clicked_cell = (row, col)
                self.clicked_cells.append(clicked_cell)

                # Get the corresponding note
                note = self.ukulele_notes[row][col]
                self.info_box.setText(f"Clicked cell: Row {row}, Column {col}, Note: {note}")

                # Play the note using fluidsynth
                self.play_note(note)

                # Record the click if recording
                if self.is_recording:
                    current_time = QDateTime.currentDateTime().toMSecsSinceEpoch()
                    timestamp = current_time - self.recording_start_time
                    self.recorded_sequence.append((clicked_cell, timestamp))

                # Set a timer to remove the highlight after 1 seconds
                QTimer.singleShot(1000, lambda: self.remove_cell(clicked_cell))
                self.update()  # Redraw the grid

    def play_note(self, note):
        # Map note names to MIDI note numbers
        note_to_midi = {
            "C4": 60, "C#4": 61, "D4": 62, "D#4": 63, "E4": 64, "F4": 65, "F#4": 66, "G4": 67,
            "G#4": 68, "A4": 69, "A#4": 70, "B4": 71, "C5": 72, "C#5": 73, "D5": 74, "D#5": 75,
            "E5": 76
        }
        midi_note = note_to_midi.get(note, 60)  # Default to C4 if note not found
        self.fs.noteon(0, midi_note, 100)  # Play the note
        QTimer.singleShot(500, lambda: self.fs.noteoff(0, midi_note))  # Stop the note after 500ms

    def remove_cell(self, cell):
        # Remove the cell highlight and update the UI
        if cell in self.clicked_cells:
            self.clicked_cells.remove(cell)
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
        self.playback_start_time = QDateTime.currentDateTime().toMSecsSinceEpoch()
        self.current_playback_index = 0
        self.info_box.setText("Playback started.")

    def update_playback(self):
        if self.is_playing and self.recorded_sequence:
            current_time = QDateTime.currentDateTime().toMSecsSinceEpoch()
            elapsed_time = current_time - self.playback_start_time

            # Process all events that should have been triggered by now
            while self.current_playback_index < len(self.recorded_sequence):
                cell, timestamp = self.recorded_sequence[self.current_playback_index]
                if elapsed_time >= timestamp:
                    self.clicked_cells.append(cell)
                    QTimer.singleShot(5000, lambda c=cell: self.remove_cell(c))
                    self.info_box.setText(f"Playback: Clicked cell {cell} at {elapsed_time}ms")
                    self.current_playback_index += 1
                else:
                    break  # No more events to process now

            # Update playback progress
            total_duration = self.recorded_sequence[-1][1] if self.recorded_sequence else 1
            if total_duration == 0:
                total_duration = 1  # Prevent division by zero
            self.playback_progress = min(int((elapsed_time / total_duration) * 100), 100)
            self.update()

            # Check if playback is finished
            if self.current_playback_index >= len(self.recorded_sequence):
                self.stop_playback()

    def stop_playback(self):
        self.is_playing = False
        self.play_button.setText("Play")
        self.playback_timer.stop()
        self.playback_progress = 0
        self.info_box.setText("Playback stopped.")
        self.update()

    def toggle_recording(self):
        self.is_recording = not self.is_recording
        if self.is_recording:
            self.recording_start_time = QDateTime.currentDateTime().toMSecsSinceEpoch()
            self.recorded_sequence = []  # Clear previous recording
            self.info_box.setText("Recording started.")
        else:
            self.info_box.setText("Recording stopped.")
        self.record_button.setText("Stop Recording" if self.is_recording else "Record")

    def clear_recording(self):
        self.recorded_sequence = []  # Clear the recorded sequence
        self.info_box.setText("Recording cleared.")


def main():
    app = QApplication(sys.argv)
    window = GridWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
