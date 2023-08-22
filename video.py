import os
import subprocess
import argparse
import sys
import shutil

from PyQt6.QtGui import QIcon, QFont, QPainter, QPen
from PyQt6.QtCore import QDir, Qt, QUrl, QSize
from PyQt6.QtMultimedia import QMediaPlayer
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import (QApplication, QFileDialog, QHBoxLayout, QLabel, QStyleFactory,
        QPushButton, QSizePolicy, QSlider, QStyle, QVBoxLayout, QWidget, QStatusBar, QMessageBox, QProgressDialog)

def create_directory(name):
    path = os.path.join(os.getcwd(), name)
    if not os.path.exists(path):
        os.makedirs(path)
        
def encode_to_120fps(input_file, output_file):
    abs_input_path = os.path.abspath(input_file)
    abs_output_path = os.path.abspath(output_file)
    command = f"ffmpeg -i {abs_input_path} -r 120 {abs_output_path}"
    subprocess.call(command, shell=True)
    
def extract_frames(input_file, output_folder):
    abs_input_path = os.path.abspath(input_file)
    abs_output_folder = os.path.abspath(output_folder)
    if not os.path.exists(abs_output_folder):
        os.makedirs(abs_output_folder)
    command = f"ffmpeg -i {abs_input_path} -vf fps=120 {os.path.join(abs_output_folder, '%d.jpg')}"
    subprocess.call(command, shell=True)
    
def save_extracted_images(output_folder, marks, group_name):
    for idx, mark in enumerate(marks):
        start = marks[idx-1] if idx > 0 else 0
        end = mark

        true_image = os.path.join(output_folder, f"{end}.jpg")
        destination = os.path.join(group_name, str(idx), 'true')
        shutil.move(true_image, destination)

        for false_frame in range(start + 1, end):  
            false_image = os.path.join(output_folder, f"{false_frame}.jpg")
            destination = os.path.join(group_name, str(idx), 'false')
            shutil.move(false_image, destination)
    
class CustomSlider(QSlider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.marked_positions = []

    def paintEvent(self, event):
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        for pos in self.marked_positions:
            x = self.style().sliderPositionFromValue(self.minimum(), self.maximum(), pos, self.width())
            color = Qt.GlobalColor.red
            painter.setPen(QPen(color, 2))
            painter.drawLine(x, 0, x, self.height())
      
class VideoPlayer(QWidget):     
    def __init__(self, parent=None, group_name=None):
        super(VideoPlayer, self).__init__(parent)
        self.group_name = group_name
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.frame_duration = float(1000 / 120)  
        self.mediaPlayer = QMediaPlayer()
        self.marked_frames = [] 

        btnSize = QSize(16, 16)
        videoWidget = QVideoWidget()
        videoWidget.setStyleSheet("background-color: black;")

        openButton = QPushButton("Open Video")   
        openButton.setToolTip("Open Video File")
        openButton.setStatusTip("Open Video File")
        openButton.setFixedHeight(24)
        openButton.setIconSize(btnSize)
        openButton.setFont(QFont("Noto Sans", 8))
        openButton.setIcon(QIcon.fromTheme("document-open", QIcon("D:/_Qt/img/open.png")))
        openButton.clicked.connect(self.abrir)

        self.playButton = QPushButton()
        self.playButton.setEnabled(False)
        self.playButton.setFixedHeight(24)
        self.playButton.setIconSize(btnSize)
        self.playButton.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.playButton.clicked.connect(self.play)

        self.positionSlider = CustomSlider(Qt.Orientation.Horizontal)
        self.positionSlider.setRange(0, 0)
        self.positionSlider.sliderMoved.connect(self.setPosition)

        self.statusBar = QStatusBar()
        self.statusBar.setFont(QFont("Noto Sans", 7))
        self.statusBar.setFixedHeight(14)

        self.markFrameButton = QPushButton("Mark Frame")
        self.markFrameButton.setEnabled(False)
        self.markFrameButton.clicked.connect(self.mark_frame)
        
        self.extractButton = QPushButton("Extract Images")
        self.extractButton.setEnabled(False)
        self.extractButton.clicked.connect(self.extract_images)

        controlLayout = QHBoxLayout()
        controlLayout.setContentsMargins(0, 0, 0, 0)
        controlLayout.addWidget(openButton)
        controlLayout.addWidget(self.playButton)
        controlLayout.addWidget(self.positionSlider)
        controlLayout.addWidget(self.markFrameButton)
        controlLayout.addWidget(self.extractButton)
        
        self.markedInfoLabel = QLabel() 
        self.markedInfoLabel.setFont(QFont("Noto Sans", 8))

        mainLayout = QVBoxLayout()
        mainLayout.addWidget(videoWidget)
        mainLayout.addLayout(controlLayout)
        mainLayout.addWidget(self.markedInfoLabel)
        mainLayout.addWidget(self.statusBar)

        self.setLayout(mainLayout)

        self.mediaPlayer.setVideoOutput(videoWidget)
        self.mediaPlayer.playbackStateChanged.connect(self.mediaStateChanged)
        self.mediaPlayer.positionChanged.connect(self.positionChanged)
        self.mediaPlayer.durationChanged.connect(self.durationChanged)
        self.mediaPlayer.errorChanged.connect(self.handleError)
        self.statusBar.showMessage("Ready")
        
        self.markedInfoLabel.setFixedHeight(10)

    def abrir(self):
        fileName, _ = QFileDialog.getOpenFileName(self, "Select Media",
                ".", "Video Files (*.mp4 *.flv *.ts *.mts *.avi)")
        
        self.markFrameButton.setEnabled(True)
        self.extractButton.setEnabled(True)

        if fileName != '':
            if not fileName.endswith("_encoded.mp4"):
                basename = os.path.basename(fileName)
                name, ext = os.path.splitext(basename)
                encoded_file = os.path.join(os.path.dirname(fileName), f"{name}_encoded{ext}")
                encode_to_120fps(fileName, encoded_file)
            else:
                encoded_file = fileName
            
            self.mediaPlayer.setSource(QUrl.fromLocalFile(encoded_file))
            self.playButton.setEnabled(True)
            self.statusBar.showMessage(encoded_file)
            self.play()
    
    def mark_frame(self):
        current_position = self.mediaPlayer.position()
        if current_position in self.marked_frames:
            self.marked_frames.remove(current_position)
        else:
            if len(self.marked_frames) >= 16:
                QMessageBox.warning(self, "Warning", "You have reached the maximum number of marked frames (16).")
                return
            self.marked_frames.append(current_position)
            self.marked_frames.sort()
        self.update_button_text()
        self.update_marked_info()
        
    def extract_images(self):
        video_file = self.mediaPlayer.source().fileName()
        output_folder = os.path.join(os.path.dirname(video_file), "image")
        extract_frames(video_file, output_folder)
        self.statusBar.showMessage(f"Images extracted to {output_folder}")

        marked_frames_in_numbers = [int(frame // self.frame_duration) for frame in self.marked_frames]

        for idx, _ in enumerate(marked_frames_in_numbers):
            new_folder_name = str(idx)
            new_folder_path = os.path.join(self.group_name, new_folder_name) 
            create_directory(new_folder_path)

            true_subfolder_path = os.path.join(new_folder_path, "true")
            false_subfolder_path = os.path.join(new_folder_path, "false")
            create_directory(true_subfolder_path)
            create_directory(false_subfolder_path)

        save_extracted_images(output_folder, marked_frames_in_numbers, self.group_name)
    
    def update_marked_info(self):
        marked_info_texts = []
        for index, frame in enumerate(self.marked_frames):
            marked_info_texts.append(f"Mark {index}: {int(frame // self.frame_duration)}")
        self.markedInfoLabel.setText(" | ".join(marked_info_texts))

    def play(self):
        if self.mediaPlayer.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.mediaPlayer.pause()
        else:
            self.mediaPlayer.play()

    def mediaStateChanged(self, state):
        if self.mediaPlayer.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.playButton.setIcon(
                    self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
        else:
            self.playButton.setIcon(
                    self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))

    def positionChanged(self, position):
        self.positionSlider.setValue(position)
        if position in self.marked_frames:
            self.markFrameButton.setText("Remove Mark")
        else:
            self.markFrameButton.setText("Mark Frame")
        self.update_frame_number(position, self.mediaPlayer.duration())

    def durationChanged(self, duration):
        self.positionSlider.setRange(0, duration)

    def setPosition(self, position):
        self.mediaPlayer.setPosition(position)
        
    def positionChanged(self, position):
        self.positionSlider.setValue(position)
        self.update_frame_number(position, self.mediaPlayer.duration())

        if position in self.marked_frames:
            self.markFrameButton.setText("Remove Mark")
        else:
            self.markFrameButton.setText("Mark Frame")

    def durationChanged(self, duration):
        self.positionSlider.setRange(0, duration)
        self.update_frame_number(self.mediaPlayer.position(), duration)

    def update_frame_number(self, position, duration):
        current_frame = round((position + 0.5) / self.frame_duration)
        total_frames = round(duration / self.frame_duration)
        self.statusBar.showMessage(f"{current_frame}/{total_frames}")
            
    def update_button_text(self):
        current_position = self.mediaPlayer.position()

        if current_position in self.marked_frames:
            self.markFrameButton.setText("Remove Mark")
        else:
            self.markFrameButton.setText("Mark Frame")
        
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Right:
            self.mediaPlayer.pause()
            position = self.mediaPlayer.position()
            new_position = int(round(position + self.frame_duration))
            self.mediaPlayer.setPosition(new_position)
        elif event.key() == Qt.Key.Key_Left:
            self.mediaPlayer.pause()
            position = self.mediaPlayer.position()
            new_position = int(round(max(0, position - self.frame_duration)))
            self.mediaPlayer.setPosition(new_position)
        frame_keys = [Qt.Key.Key_0, Qt.Key.Key_1, Qt.Key.Key_2, Qt.Key.Key_3,
                      Qt.Key.Key_4, Qt.Key.Key_5, Qt.Key.Key_6, Qt.Key.Key_7,
                      Qt.Key.Key_8, Qt.Key.Key_9, Qt.Key.Key_A, Qt.Key.Key_B,
                      Qt.Key.Key_C, Qt.Key.Key_D, Qt.Key.Key_E, Qt.Key.Key_F]
        for i, key in enumerate(frame_keys):
            if event.key() == key and i < len(self.marked_frames):
                self.mediaPlayer.setPosition(self.marked_frames[i])

    def handleError(self):
        self.playButton.setEnabled(False)
        self.statusBar.showMessage("Error: " + self.mediaPlayer.errorString())

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Process some arguments.')
    parser.add_argument('-g', required=True, help='The name for creating a new directory')
    args = parser.parse_args()

    create_directory(args.g)

    app = QApplication(sys.argv)
    app.setStyleSheet("""
        QStatusBar {
            font-size: 12px;
        }
    """)
    player = VideoPlayer(group_name=args.g)
    player.setWindowTitle("Player")
    player.resize(900, 600)
    player.show()
    sys.exit(app.exec())
