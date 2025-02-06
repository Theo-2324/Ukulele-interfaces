import sys
import json
import pyautogui
import numpy as np
import math
import fluidsynth  # Add FluidSynth
from pupil_labs.realtime_api.simple import discover_one_device
from pupil_labs.real_time_screen_gaze.gaze_mapper import GazeMapper
from pupil_labs.real_time_screen_gaze import marker_generator
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *

pyautogui.FAILSAFE = False

# SoundFontPlayer Class
class SoundFontPlayer:
    def __init__(self, soundfont_path):
        self.fs = fluidsynth.Synth()
        self.fs.start(driver="alsa")  # Replace with the correct driver for your OS
        self.sfid = self.fs.sfload(soundfont_path)  # Load the SoundFont
        if self.sfid == -1:
            print("Error: Failed to load SoundFont.")
        else:
            print("SoundFont loaded successfully.")
            self.fs.program_select(0, self.sfid, 0, 0)  # Set the first channel to use the first instrument

    def play_note(self, note=60, velocity=100, duration=1.0):
        """Play a note with FluidSynth."""
        self.fs.noteon(0, note, velocity)
        QTimer.singleShot(int(duration * 1000), lambda: self.fs.noteoff(0, note))  # Stop the note after duration

    def close(self):
        """Clean up FluidSynth."""
        self.fs.delete()

# DwellDetector Class (unchanged)
class DwellDetector:
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
        if self.points[-1, 2] - self.points[0, 2] < self.minimumDelay:
            return False, False, None

        minTimestamp = timestamp - self.minimumDelay - .0001
        self.points = self.points[self.points[:, 2] >= minTimestamp]

        center = np.mean(self.points[:, :2], axis=0)
        distances = np.sqrt(np.sum(self.points[:, :2] - center, axis=1) ** 2)

        if np.max(distances) < self.range:
            inDwell = True
        else:
            inDwell = False

        changed = inDwell != self.inDwell
        self.inDwell = inDwell

        return changed, inDwell, center

# TagWindow Class (unchanged)
def createMarker(marker_id):
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

class TagWindow(QWidget):
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
        self.tagSizeInput.setValue(256)
        self.tagSizeInput.valueChanged.connect(self.onTagSizeChanged)

        self.tagBrightnessInput = QSpinBox()
        self.tagBrightnessInput.setRange(0, 255)
        self.tagBrightnessInput.setValue(128)
        self.tagBrightnessInput.valueChanged.connect(lambda _: self.repaint())

        self.smoothingInput = QDoubleSpinBox()
        self.smoothingInput.setRange(0, 1.0)
        self.smoothingInput.setValue(0.8)
        self.smoothingInput.valueChanged.connect(self.smoothingChanged.emit)

        self.dwellRadiusInput = QSpinBox()
        self.dwellRadiusInput.setRange(0, 512)
        self.dwellRadiusInput.setValue(25)
        self.dwellRadiusInput.valueChanged.connect(self.dwellRadiusChanged.emit)

        self.dwellTimeInput = QDoubleSpinBox()
        self.dwellTimeInput.setRange(0, 20)
        self.dwellTimeInput.setValue(0.75)
        self.dwellTimeInput.valueChanged.connect(self.dwellTimeChanged.emit)

        self.mouseEnabledInput = QCheckBox('Mouse Control')
        self.mouseEnabledInput.setChecked(False)
        self.mouseEnabledInput.toggled.connect(self.mouseEnableChanged.emit)

        self.form.layout().addRow('Tag Size', self.tagSizeInput)
        self.form.layout().addRow('Tag Brightness', self.tagBrightnessInput)
        self.form.layout().addRow('Smoothing', self.smoothingInput)
        self.form.layout().addRow('Dwell Radius', self.dwellRadiusInput)
        self.form.layout().addRow('Dwell Time', self.dwellTimeInput)
        self.form.layout().addRow('', self.mouseEnabledInput)

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
                self.showMaximized()

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

        if self.settingsVisible:
            if self.clicked:
                painter.setBrush(Qt.red)
            else:
                painter.setBrush(Qt.white)

            painter.drawEllipse(QPoint(*self.point), self.dwellRadiusInput.value(), self.dwellRadiusInput.value())

        for cornerIdx in range(4):
            cornerRect = self.getCornerRect(cornerIdx)
            if cornerIdx not in self.visibleMarkerIds:
                painter.fillRect(cornerRect.marginsAdded(QMargins(5, 5, 5, 5)), QColor(255, 0, 0))

            painter.drawPixmap(cornerRect, self.pixmaps[cornerIdx])
            painter.fillRect(cornerRect, QColor(0, 0, 0, 255-self.tagBrightnessInput.value()))

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


# PupilPointerApp Class
class PupilPointerApp(QApplication):
    def __init__(self):
        super().__init__()

        self.setApplicationDisplayName('Pupil Pointer')
        self.mouseEnabled = False

        self.tagWindow = TagWindow()

        self.device = None
        self.dwellDetector = DwellDetector(.75, 75)
        self.smoothing = 0.8

        # Initialize SoundFontPlayer
        self.soundfont_player = SoundFontPlayer("/home/theo/Ukulele soundfiles/Soundfonts/Heavy_Metal.sf2")

        self.tagWindow.surfaceChanged.connect(self.onSurfaceChanged)
        self.tagWindow.dwellTimeChanged.connect(self.dwellDetector.setDuration)
        self.tagWindow.dwellRadiusChanged.connect(self.dwellDetector.setRange)
        self.tagWindow.mouseEnableChanged.connect(self.setMouseEnabled)
        self.tagWindow.smoothingChanged.connect(self.setSmoothing)

        self.pollTimer = QTimer()
        self.pollTimer.setInterval(1000 / 30)
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
        frameAndGaze = self.device.receive_matched_scene_video_frame_and_gaze(timeout_seconds=1 / 15)

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
                    # Play a sound when dwell is detected
                    self.soundfont_player.play_note(note=60, velocity=100, duration=1.0)
                else:
                    self.tagWindow.setClicked(False)

                if self.mouseEnabled:
                    QCursor().setPos(mousePoint)

    def exec(self):
        self.tagWindow.setStatus('Looking for a device...')
        self.tagWindow.showMaximized()
        QTimer.singleShot(1000, self.start)
        super().exec()
        if self.device is not None:
            self.device.close()
        # Clean up FluidSynth
        self.soundfont_player.close()

def run():
    app = PupilPointerApp()
    app.exec()

# Execute the program
run()