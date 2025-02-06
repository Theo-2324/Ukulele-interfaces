import sys
import fluidsynth
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout
from PyQt5.QtCore import QTimer

class SoundFontPlayer(QWidget):
    def __init__(self):
        super().__init__()

        # Initialize FluidSynth
        self.fs = fluidsynth.Synth()
        self.fs.start(driver="alsa")  # Replace with the correct driver for your OS

        # Load a SoundFont
        self.sfid = self.fs.sfload("/home/theo/Ukulele soundfiles/Soundfonts/Heavy_Metal.sf2")
        if self.sfid == -1:
            print("Error: Failed to load SoundFont.")
        else:
            print("SoundFont loaded successfully.")
            self.fs.program_select(0, self.sfid, 0, 0)  # Set the first channel to use the first instrument in the SoundFont

        # Set up the UI
        self.initUI()

    def initUI(self):
        # Create a button
        self.button = QPushButton('Play Note', self)
        self.button.clicked.connect(self.play_note)

        # Set up the layout
        layout = QVBoxLayout()
        layout.addWidget(self.button)
        self.setLayout(layout)

        # Set window properties
        self.setWindowTitle('1x1 Grid SoundFont Player')
        self.setGeometry(300, 300, 200, 100)

    def play_note(self):
        # Play a note (Middle C, velocity 100)
        self.fs.noteon(0, 60, 100)

        # Stop the note after 1 second
        QTimer.singleShot(1000, lambda: self.fs.noteoff(0, 60))  # 1000 ms = 1 second

    def closeEvent(self, event):
        # Clean up FluidSynth when the window is closed
        self.fs.delete()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    player = SoundFontPlayer()
    player.show()
    sys.exit(app.exec_())