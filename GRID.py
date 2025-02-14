import sys
import fluidsynth
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QPushButton, QLabel, QVBoxLayout, QHBoxLayout
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QFont
from PySide6.QtCore import Qt, QTimer, QDateTime

class GridWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("8x8 Ukulele Grid with Playback and Controls")
        self.showMaximized()  # Start maximized

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Grid parameters
        self.rows = 4  # 4 rows for the ukulele notes
        self.columns = 8  # 8 columns
        self.cell_size = 100  # Fixed size of each grid cell
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
        self.fs.start(driver="alsa")  # Use 'alsa' for Linux

        # Load SoundFont file with error handling
        try:
            soundfont_path = "/home/theo/Ukulele soundfiles/Soundfonts/Ukulele_little-scale.sf2"
            self.sfid = self.fs.sfload(soundfont_path)
            if self.sfid == -1:
                raise FileNotFoundError(f"SoundFont file not found or could not be loaded: {soundfont_path}")
            self.fs.program_select(0, self.sfid, 0, 0)  # Select the first instrument
        except Exception as e:
            self.sfid = None
            print(f"Error loading SoundFont: {e}")

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
        button_layout.addStretch()  # Add stretch to align buttons to the left

        # Add widgets to main layout
        main_layout.addWidget(self.info_box)
        main_layout.addLayout(button_layout)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Calculate the starting position of the grid to center it
        grid_width = self.columns * self.cell_size
        grid_height = self.rows * self.cell_size
        grid_x_offset = (self.width() - grid_width) // 2
        grid_y_offset = (self.height() - grid_height) // 2

        # Draw the 4x8 grid for notes
        painter.setPen(QPen(Qt.black, 2))
        for row in range(4):  # First 4 rows for the ukulele notes
            for col in range(self.columns):
                x = col * self.cell_size + grid_x_offset
                y = row * self.cell_size + grid_y_offset
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
            x = col * self.cell_size + grid_x_offset
            y = row * self.cell_size + grid_y_offset
            painter.drawRect(x, y, self.cell_size, self.cell_size)

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
            # Calculate the starting position of the grid to center it
            grid_width = self.columns * self.cell_size
            grid_height = self.rows * self.cell_size
            grid_x_offset = (self.width() - grid_width) // 2
            grid_y_offset = (self.height() - grid_height) // 2

            # Calculate the clicked cell
            x, y = event.position().x() - grid_x_offset, event.position().y() - grid_y_offset
            col = int(x // self.cell_size)
            row = int(y // self.cell_size)

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

                # Set a timer to remove the highlight after 1 second
                QTimer.singleShot(1000, lambda: self.remove_cell(clicked_cell))
                self.update()  # Redraw the grid

    def play_note(self, note):
        if self.sfid is None:
            self.info_box.setText("SoundFont not loaded. Cannot play note.")
            return

        # Map note names to MIDI note numbers
        note_to_midi = {
            "C4": 60, "C#4": 61, "D4": 62, "D#4": 63, "E4": 64, "F4": 65, "F#4": 66, "G4": 67,
            "G#4": 68, "A4": 69, "A#4": 70, "B4": 71, "C5": 72, "C#5": 73, "D5": 74, "D#5": 75,
            "E5": 76
        }
        midi_note = note_to_midi.get(note, 60)  # Default to C4 if note not found
        self.fs.noteon(0, midi_note, self.volume)  # Play the note with current volume
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
                    
                    # Play the note corresponding to the clicked cell
                    row, col = cell
                    note = self.ukulele_notes[row][col]
                    self.play_note(note)
                    
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

    def increase_volume(self):
        """Increase volume by 10, capped at 127."""
        self.volume = min(self.volume + 10, 127)
        self.update_volume()
        self.info_box.setText(f"Volume increased to {self.volume}")

    def decrease_volume(self):
        """Decrease volume by 10, capped at 0."""
        self.volume = max(self.volume - 10, 0)
        self.update_volume()
        self.info_box.setText(f"Volume decreased to {self.volume}")

    def update_volume(self):
        """Update the volume in fluidsynth."""
        if self.sfid is not None:
            self.fs.cc(0, 7, self.volume)  # MIDI CC 7 is the volume controller


def main():
    app = QApplication(sys.argv)
    window = GridWindow()
    window.showMaximized()  # Open the window maximized
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
