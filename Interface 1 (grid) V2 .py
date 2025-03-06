import sys
import json
import pyautogui
import numpy as np
import math
import fluidsynth
from pupil_labs.realtime_api.simple import discover_one_device
from pupil_labs.real_time_screen_gaze.gaze_mapper import GazeMapper
from pupil_labs.real_time_screen_gaze import marker_generator
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *

pyautogui.FAILSAFE = False

# DwellDetector Class (No need to change) Logic for dwell detection
class DwellDetector():# Needed for pupil tracking applications
    def __init__(self, minimumDelayInSeconds, rangeInPixels):
        self.minimumDelay = minimumDelayInSeconds
        self.range = rangeInPixels
        self.points = np.empty(shape=[0, 3])

        self.inDwell = False

    def setDuration(self, duration):
        self.minimumDelay = duration

    def setRange(self, rangeInPixels):
        self.range = rangeInPixels

    def addPoint(self, x, y, timestamp):
        point = np.array([x, y, timestamp])

        self.points = np.append(self.points, [point], axis=0)
        if self.points[-1,2] - self.points[0,2] < self.minimumDelay:
            return False, False, None

        minTimestamp = timestamp - self.minimumDelay - .0001
        self.points = self.points[self.points[:,2] >= minTimestamp]

        center = np.mean(self.points[:,:2], axis=0)
        distances = np.sqrt(np.sum(self.points[:,:2] - center, axis=1)**2)

        if np.max(distances) < self.range:
            inDwell = True
        else:
            inDwell = False

        changed = inDwell != self.inDwell
        self.inDwell = inDwell

        return changed, inDwell, center

# TagWindow Class Main window for the application
def createMarker(marker_id): # genertate marker id
    marker = marker_generator.generate_marker(marker_id, flip_x=True, flip_y=True)

    image = QImage(10, 10, QImage.Format_Mono)
    image.fill(1)
    for y in range(marker.shape[0]):
        for x in range(marker.shape[1]):
            color = marker[y][x]//255
            image.setPixel(x+1, y+1, color)

    # Convert the QImage to a QPixmap
    return QPixmap.fromImage(image)

def pointToTuple(qpoint):
    return (qpoint.x(), qpoint.y())

class TagWindow(QWidget):# Main window for the application
    surfaceChanged = Signal()
    mouseEnableChanged = Signal(bool)
    dwellRadiusChanged = Signal(int)
    dwellTimeChanged = Signal(float)
    smoothingChanged = Signal(float)

    def __init__(self):
        super().__init__()

        self.setStyleSheet('* { font-size: 18pt }')

        self.markerIDs = []
        self.pixmaps = []
        for markerID in range(4):
            self.markerIDs.append(markerID)
            self.pixmaps.append(createMarker(markerID))

        self.point = (0, 0)
        self.clicked = False
        self.settingsVisible = True
        self.visibleMarkerIds = []

        self.form = QWidget()
        self.form.setLayout(QFormLayout())

        self.tagSizeInput = QSpinBox()
        self.tagSizeInput.setRange(10, 512)
        self.tagSizeInput.setValue(190) #Change Marker Size here
        self.tagSizeInput.valueChanged.connect(self.onTagSizeChanged)

        self.tagBrightnessInput = QSpinBox()
        self.tagBrightnessInput.setRange(0, 255)
        self.tagBrightnessInput.setValue(255) #change Marker Brightness here
        self.tagBrightnessInput.valueChanged.connect(lambda _: self.repaint())

        self.smoothingInput = QDoubleSpinBox()
        self.smoothingInput.setRange(0, 1.0)
        self.smoothingInput.setValue(1) #set smoothing value here
        self.smoothingInput.valueChanged.connect(self.smoothingChanged.emit)

        self.dwellRadiusInput = QSpinBox()
        self.dwellRadiusInput.setRange(0, 512)
        self.dwellRadiusInput.setValue(35) #set dwell radius here
        self.dwellRadiusInput.valueChanged.connect(self.dwellRadiusChanged.emit)

        self.dwellTimeInput = QDoubleSpinBox()
        self.dwellTimeInput.setRange(0, 20)
        self.dwellTimeInput.setValue(0.5) #set dwell time here
        self.dwellTimeInput.valueChanged.connect(self.dwellTimeChanged.emit)

        self.mouseEnabledInput = QCheckBox('Mouse Control')
        self.mouseEnabledInput.setChecked(True) #Toggle Mouse Control here
        self.mouseEnabledInput.toggled.connect(self.mouseEnableChanged.emit)

        self.instructionsLabel = QLabel('Right-click one of the tags to toggle settings view.')
        self.instructionsLabel.setAlignment(Qt.AlignHCenter)

        self.statusLabel = QLabel()
        self.statusLabel.setAlignment(Qt.AlignHCenter)

        self.setLayout(QGridLayout())
        self.layout().setSpacing(50)

        self.layout().addWidget(self.instructionsLabel, 0, 0, 1, 3)
        self.layout().addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding), 1, 1, 1, 1)
        self.layout().addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum), 2, 0, 1, 1)
        self.layout().addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum), 2, 2, 1, 1)
        self.layout().addWidget(self.form, 3, 1, 1, 1)
        self.layout().addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding), 4, 1, 1, 1)
        self.layout().addWidget(self.statusLabel, 5, 0, 1, 3)

        main_layout = QVBoxLayout(self)

         # Grid parameters
        self.rows = 4  # 4 rows for the ukulele notes
        self.columns = 8  # 8 columns
        self.cell_size = 175  # Fixed size of each grid cell
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
            ["     G4", "     G#4", "     A4", "     A#4", "     B4", "     C5", "     C#5", "     D5"],  # String 1: G
            ["     C4", "     C#4", "     D4", "     D#4", "     E4", "     F4", "     F#4", "     G4"],  # String 2: C
            ["     E4", "     F4", "     F#4", "     G4", "     G#4", "     A4", "     A#4", "     B4"],  # String 3: E
            ["     A4", "     A#4", "     B4", "     C5", "     C#5", "     D5", "     D#5", "     E5"],  # String 4: A
        ]
        # Initialize fluidsynth
        self.fs = fluidsynth.Synth()
        self.fs.start(driver="alsa")  # Use 'alsa' for Linux

        # Load SoundFont file with error handling
        try:
            soundfont_path = "/home/emanuel/Documents/ROS2_Workspaces/TheosDissertation/SoundFonts/UKU-SF.sf2"
            self.sfid = self.fs.sfload(soundfont_path)
            if self.sfid == -1:
                raise FileNotFoundError(f"SoundFont file not found or could not be loaded: {soundfont_path}")
            self.fs.program_select(0, self.sfid, 0, 0)  # Select the first instrument
        except Exception as e:
            self.sfid = None
            print(f"Error loading SoundFont: {e}")

        # Volume control
        self.volume = 100  # Default volume (0-127, MIDI standard) # Adjust volume here
        self.update_volume()

        # Info box for messages
        self.info_box = QLabel("Messages will appear here.", self) # Set initial message upon launch
        self.info_box.setStyleSheet("border: 1px solid black; padding: 10px; font-size: 14px;") # Set info box border and padding
        self.info_box.setFont(QFont("Arial", 12)) # Set font style and size for info box
        self.info_box.setGeometry(800, 900, 300, 50)  # Set position and size (x, y, width, height)

        # Buttons
        self.play_button = QPushButton("Play", self)
        self.play_button.setFont(QFont("Arial", 12))
        self.play_button.setFixedSize(200, 60) # Adjust button size
        self.play_button.clicked.connect(self.toggle_playback)
        self.play_button.setGeometry(450, 50, 200, 60) # Set position and size (x, y, width, height)

        self.record_button = QPushButton("Record", self)
        self.record_button.setFont(QFont("Arial", 12))
        self.record_button.setFixedSize(200, 60) # Adjust button size
        self.record_button.clicked.connect(self.toggle_recording)
        self.record_button.setGeometry(700, 50, 200, 60) # Set position and size (x, y, width, height)

        self.volume_up_button = QPushButton("Volume +", self)
        self.volume_up_button.setFont(QFont("Arial", 12))
        self.volume_up_button.setFixedSize(200, 60) # Adjust button size
        self.volume_up_button.clicked.connect(self.increase_volume)
        self.volume_up_button.setGeometry(950, 50, 200, 60) # Set position and size (x, y, width, height)

        self.volume_down_button = QPushButton("Volume -", self)
        self.volume_down_button.setFont(QFont("Arial", 12))
        self.volume_down_button.setFixedSize(200, 60) # Adjust button size
        self.volume_down_button.clicked.connect(self.decrease_volume)
        self.volume_down_button.setGeometry(1200, 50, 200, 60) # Set position and size (x, y, width, height)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.RightButton:
            self.setSettingsVisible(not self.settingsVisible)
            

    def setSettingsVisible(self, visible):
        self.settingsVisible = visible

        if sys.platform.startswith('darwin'):
            self.hide()
            self.setWindowFlag(Qt.FramelessWindowHint, not visible)
            self.setWindowFlag(Qt.WindowStaysOnTopHint, not visible)
            self.setAttribute(Qt.WA_TranslucentBackground, not visible)

            if visible:
                self.show()
            else:
                self.showFullScreen()

        self.updateMask()

    def setStatus(self, status):
        self.statusLabel.setText(status)

    def setClicked(self, clicked):
        self.clicked = clicked
        self.repaint()

    def updatePoint(self, norm_x, norm_y):
        tagMargin = 0.1 * self.tagSizeInput.value()
        surfaceSize = (
            self.width() - 2*tagMargin,
            self.height() - 2*tagMargin,
        )

        self.point = (
            norm_x*surfaceSize[0] + tagMargin,
            (surfaceSize[1] - norm_y*surfaceSize[1]) + tagMargin
        )

        self.repaint()
        return self.mapToGlobal(QPoint(*self.point))

    def showMarkerFeedback(self, markerIds):
        self.visibleMarkerIds = markerIds
        self.repaint()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if self.settingsVisible:
            if self.clicked:
                painter.setBrush(Qt.white)# Weird box here set to white to ignore
            else:
                painter.setBrush(Qt.white)

           
        for cornerIdx in range(4):
            cornerRect = self.getCornerRect(cornerIdx)
            if cornerIdx not in self.visibleMarkerIds:
                painter.fillRect(cornerRect.marginsAdded(QMargins(5, 5, 5, 5)), QColor(255, 0, 0))

            painter.drawPixmap(cornerRect, self.pixmaps[cornerIdx])
            painter.fillRect(cornerRect, QColor(0, 0, 0, 255-self.tagBrightnessInput.value()))

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
        playback_y = self.height() - 75  # Position in relation to the bottom of the window
        playback_width = self.width() - 500  # Full width of the window
        playback_x = 255 # Position in relation to the left of the window
        playback_height = 20  # Fixed thickness of the playback bar

        # Background of playback bar
        painter.setBrush(QBrush(QColor(200, 200, 200))) # Light gray
        painter.drawRect(playback_x, playback_y, playback_width, playback_height)

        # Playback progress
        if self.is_playing or self.playback_progress > 0:
            progress_width = int((self.playback_progress / 100) * playback_width)
            painter.setBrush(QBrush(QColor(0, 255, 0)))  # Green for progress
            painter.drawRect(playback_x, playback_y, progress_width, playback_height)  

        painter.drawEllipse(QPoint(*self.point), self.dwellRadiusInput.value(), self.dwellRadiusInput.value())
          

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
            "     C4": 60, "     C#4": 61, "     D4": 62, "     D#4": 63, "     E4": 64, "     F4": 65, "     F#4": 66, "     G4": 67,
            "     G#4": 68, "     A4": 69, "     A#4": 70, "     B4": 71, "     C5": 72, "     C#5": 73, "     D5": 74, "     D#5": 75,
            "     E5": 76
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
            
    def resizeEvent(self, event):
        self.updateMask()
        self.surfaceChanged.emit()

    def onTagSizeChanged(self, value):
        self.repaint()
        self.surfaceChanged.emit()

    def getMarkerSize(self):
        return self.tagSizeInput.value()

    def getTagPadding(self):
        return self.getMarkerSize()/8

    def getMarkerVerts(self):
        tagPadding = self.getTagPadding()
        markers_verts = {}

        for cornerIdx, markerID in enumerate(self.markerIDs):
            rect = self.getCornerRect(cornerIdx) - QMargins(tagPadding, tagPadding, tagPadding, tagPadding)

            markers_verts[markerID] = [
                pointToTuple(rect.topLeft()),
                pointToTuple(rect.topRight()),
                pointToTuple(rect.bottomRight()),
                pointToTuple(rect.bottomLeft()),
            ]

        return markers_verts

    def getSurfaceSize(self):
        return (self.width(), self.height())

    def updateMask(self):
        if self.settingsVisible:
            mask = QRegion(0, 0, self.width(), self.height())

        else:
            mask = QRegion(0, 0, 0, 0)
            for cornerIdx in range(4):
                rect = self.getCornerRect(cornerIdx).marginsAdded(QMargins(2, 2, 2, 2))
                mask = mask.united(rect)

        self.setMask(mask)


    def getCornerRect(self, cornerIdx):
        tagSize = self.tagSizeInput.value()
        tagSizePadded = tagSize + self.getTagPadding()*2

        if cornerIdx == 0:
            return QRect(0, 0, tagSizePadded, tagSizePadded)

        elif cornerIdx == 1:
            return QRect(self.width()-tagSizePadded, 0, tagSizePadded, tagSizePadded)

        elif cornerIdx == 2:
            return QRect(self.width()-tagSizePadded, self.height()-tagSizePadded, tagSizePadded, tagSizePadded)

        elif cornerIdx == 3:
            return QRect(0, self.height()-tagSizePadded, tagSizePadded, tagSizePadded)
        
# PupilPointerApp Class (No need to change)
class PupilPointerApp(QApplication):# Also needed for pupil tracking applications
    def __init__(self):
        super().__init__()

        self.setApplicationDisplayName('Pupil Pointer')
        self.mouseEnabled = True

        self.tagWindow = TagWindow()

        self.device = None
        self.dwellDetector = DwellDetector(.75, 75)
        self.smoothing = 0.8

        self.tagWindow.surfaceChanged.connect(self.onSurfaceChanged)

        self.tagWindow.dwellTimeChanged.connect(self.dwellDetector.setDuration)
        self.tagWindow.dwellRadiusChanged.connect(self.dwellDetector.setRange)
        self.tagWindow.mouseEnableChanged.connect(self.setMouseEnabled)
        self.tagWindow.smoothingChanged.connect(self.setSmoothing)

        self.pollTimer = QTimer()
        self.pollTimer.setInterval(1000/30)
        self.pollTimer.timeout.connect(self.poll)

        self.surface = None
        self.firstPoll = True

        self.mousePosition = None
        self.gazeMapper = None

    def onSurfaceChanged(self):
        self.updateSurface()

    def start(self):
        self.device = discover_one_device(max_search_duration_seconds=0.25)

        if self.device is None:
            QTimer.singleShot(1000, self.start)
            return

        calibration = self.device.get_calibration()
        self.gazeMapper = GazeMapper(calibration)

        self.tagWindow.setStatus(f'Connected to {self.device}. One moment...')

        self.updateSurface()
        self.pollTimer.start()
        self.firstPoll = True

    def updateSurface(self):
        if self.gazeMapper is None:
            return

        self.gazeMapper.clear_surfaces()
        self.surface = self.gazeMapper.add_surface(
            self.tagWindow.getMarkerVerts(),
            self.tagWindow.getSurfaceSize()
        )

    def setMouseEnabled(self, enabled):
        self.mouseEnabled = enabled

    def setSmoothing(self, value):
        self.smoothing = value

    def poll(self):
        frameAndGaze = self.device.receive_matched_scene_video_frame_and_gaze(timeout_seconds=1/15)

        if frameAndGaze is None:
            return

        else:
            self.tagWindow.setStatus(f'Streaming data from {self.device}')
            self.firstPoll = False

        frame, gaze = frameAndGaze
        result = self.gazeMapper.process_frame(frame, gaze)

        markerIds = [int(marker.uid.split(':')[-1]) for marker in result.markers]
        self.tagWindow.showMarkerFeedback(markerIds)

        if self.surface.uid in result.mapped_gaze:
            for surface_gaze in result.mapped_gaze[self.surface.uid]:
                if self.mousePosition is None:
                    self.mousePosition = [surface_gaze.x, surface_gaze.y]

                else:
                    self.mousePosition[0] = self.mousePosition[0] * self.smoothing + surface_gaze.x * (1.0 - self.smoothing)
                    self.mousePosition[1] = self.mousePosition[1] * self.smoothing + surface_gaze.y * (1.0 - self.smoothing)

                mousePoint = self.tagWindow.updatePoint(*self.mousePosition)

                changed, dwell, dwellPosition = self.dwellDetector.addPoint(mousePoint.x(), mousePoint.y(), gaze.timestamp_unix_seconds)
                if changed and dwell:
                    self.tagWindow.setClicked(True)
                    if self.mouseEnabled:
                        pyautogui.click(x=dwellPosition[0], y=dwellPosition[1])
                else:
                    self.tagWindow.setClicked(False)

                if self.mouseEnabled:
                    QCursor().setPos(mousePoint)

    def exec(self):
        self.tagWindow.setStatus('Looking for a device...')
        self.tagWindow.showFullScreen()
        QTimer.singleShot(1000, self.start)
        super().exec()
        if self.device is not None:
            self.device.close()

def run():
    app = PupilPointerApp()
    app.exec()

# Execute the program
run()
