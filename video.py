import os
import subprocess
import argparse
import sys
import signal
import shutil

from PyQt6.QtGui import QIcon, QFont, QPainter, QPen
from PyQt6.QtCore import QDir, Qt, QUrl, QSize
from PyQt6.QtMultimedia import QMediaPlayer
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import (QApplication, QFileDialog, QHBoxLayout, QLabel, QStyleFactory,
        QPushButton, QSizePolicy, QSlider, QStyle, QVBoxLayout, QWidget, QStatusBar, QMessageBox, QProgressDialog)
from PIL import Image, UnidentifiedImageError
import imagehash
import glob
import cv2
import tensorflow as tf
    
def quit_app(*args):
    QApplication.instance().quit()

def resize_image(image_path, output_path, scale_factor):
    #image = Image.open(image_path)
    #new_size = (int(image.width * scale_factor), int(image.height * scale_factor))
    #image_resized = image.resize(new_size)
    #image_resized.save(output_path)
    image = cv2.imread(image_path)
    height, width = image.shape[:2]
    new_height = int(width * scale_factor)
    new_width = int(height * scale_factor)
    image_resized = tf.image.resize(image, [new_width, new_height])
    # image_resized.save(output_path)
    tf.keras.utils.save_img(output_path, image_resized)
        
def filter_similar_images(directory, hash_threshold=10):
    # image hash value
    image_files = sorted(glob.glob(os.path.join(directory, '*.jpg')))
    total_images = len(image_files)
    
    hashes = []
    for idx, img_file in enumerate(image_files):
        with Image.open(img_file) as img:
            h = imagehash.phash(img)
            hashes.append((img_file, h))
        # Print progress for every 10 images
        if idx % 10 == 0:
            print(f"Processed {idx}/{total_images} images", end='\r')

    # grouping 
    checked = set()
    to_keep = set()
    for i, (img_file1, hash1) in enumerate(hashes):
        if img_file1 in checked:
            continue
        similar_group = [img_file1]
        for j, (img_file2, hash2) in enumerate(hashes[i+1:], start=i+1):
            if hash1 - hash2 <= hash_threshold:  # setting for hashing
                similar_group.append(img_file2)
        checked.update(similar_group)
        to_keep.update(similar_group[:40]) 

    # delete other images
    for img_file in image_files:
        if img_file not in to_keep:
            os.remove(img_file)

def create_directory(path, name):
    directory_path = os.path.join(path, name)
    if os.path.exists(directory_path):
        shutil.rmtree(directory_path)  # delete folder (reset)
    os.makedirs(directory_path)
        
def encode_to_120fps(input_file, output_file):
    abs_input_path = os.path.abspath(input_file)
    abs_output_path = os.path.abspath(output_file)
    command = f"ffmpeg -i {abs_input_path} -r 120 {abs_output_path}"
    subprocess.call(command, shell=True)
    
def extract_frames(input_file, output_folder, last_frame_number):
    abs_input_path = os.path.abspath(input_file)
    abs_output_folder = os.path.abspath(output_folder)
    
    if os.path.exists(abs_output_folder):
        shutil.rmtree(abs_output_folder)
    
    os.makedirs(abs_output_folder)
        
    output_path = os.path.join(abs_output_folder, '%d.jpg')
    command = f'ffmpeg -i "{abs_input_path}" -vf fps=120 -vframes {last_frame_number} "{output_path}"'
    
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"Error occurred during ffmpeg execution:\n{result.stderr}")
    else:
        print(f"ffmpeg output:\n{result.stdout}")
    
def save_extracted_images(output_folder, marks, group_name, hash_threshold):
    start = 1
    for idx, sublist in marks:
        if len(sublist) == 0:                    
            print(f"task is completed.")
            return
        end = min(sublist)
        
        # true image save
        for true_frame in sublist:
            true_image = os.path.join(output_folder, f"{true_frame}.jpg")
            destination = os.path.join(os.path.abspath(group_name), str(idx), 'true')
            shutil.copy(true_image, destination)

        # false image save
        for false_frame in range(start, end):  
            false_image = os.path.join(output_folder, f"{false_frame}.jpg")
            destination = os.path.join(os.path.abspath(group_name), str(idx), 'false')
            shutil.copy(false_image, destination)
        
        start = min(sublist)
    
        false_dirs = os.path.join(group_name, str(idx), 'false')
        filter_similar_images(false_dirs, hash_threshold)
        
class CustomSlider(QSlider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.marked_positions = []
     
# main class
class VideoPlayer(QWidget):     
    def __init__(self, parent=None, group_name=None, directory_path=None):
        super(VideoPlayer, self).__init__(parent)
        self.group_name = group_name
        self.directory_path = directory_path
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.frame_duration = float(1000 / 120)  # time of 1 frame (milisec)
        self.mediaPlayer = QMediaPlayer()
        self.frame_range = {}
        self.true_frames = {key: [] for key in range(16)}

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

        self.markFrameButton = QPushButton("No Marked")
        self.markFrameButton.setEnabled(False)
        
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
        
        self.markedInfoLabel = QLabel()  # Used to display marked frames
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

    # open video
    def abrir(self):
        fileName, _ = QFileDialog.getOpenFileName(self, "Select Media",
                ".", "Video Files (*.mp4 *.flv *.ts *.mts *.avi *.m4a)")
        
        self.markFrameButton.setEnabled(True)
        self.extractButton.setEnabled(True)

        if fileName != '':
            # end with 'encoded'
            if not os.path.splitext(fileName)[0].endswith("_encoded"):
                # do encoding
                basename = os.path.basename(fileName)
                name, ext = os.path.splitext(basename)
                encoded_file = os.path.join(os.path.dirname(fileName), f"{name}_encoded{ext}")
                encode_to_120fps(fileName, encoded_file)
            else:
                # skip encoding
                encoded_file = fileName
            
            self.mediaPlayer.setSource(QUrl.fromLocalFile(encoded_file))
            self.playButton.setEnabled(True)
            self.statusBar.showMessage(encoded_file)
            self.play()
        
    def extract_images(self):
        url = self.mediaPlayer.source()
        video_file = url.toLocalFile()

        output_folder = os.path.join(self.directory_path, "image")
        
        marks = [frame for sublist in self.true_frames.values() for frame in sublist]
        last_frame = max(marks) if marks else 0
        print(f"{last_frame}")
        extract_frames(video_file, output_folder, last_frame)
        print(f"Images extracted to {output_folder}")

        for filename in os.listdir(output_folder):
            if filename.endswith(".jpg"):
                img_path = os.path.join(output_folder, filename)
                resize_image(img_path, img_path, 1/2)
        
        # Create folders
        for idx, frames in self.true_frames.items():
            if len(frames) == 0:
                continue
                
            new_folder_name = str(idx) 
            new_folder_path = os.path.join(self.group_name, new_folder_name)
            create_directory(self.group_name, new_folder_name)

            # true and false subfolder
            create_directory(new_folder_path, "true")
            create_directory(new_folder_path, "false")

        save_extracted_images(os.path.abspath(output_folder), self.true_frames.items(), self.group_name, hash_threshold=args.s)
        
    def update_marked_info(self):
        marked_info_texts = []
        for index, ranges in self.frame_range.items():
            ranges_count = len(ranges)
            if ranges_count == 0:
                continue
            elif ranges_count == 1:
                marked_info_texts.append(f"Mark {index-48}: {ranges[0]}~{ranges[0]}")
            else:
                marked_info_texts.append(f"Mark {index-48}: {ranges[0]}~{ranges[1]}")
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

    def setPosition(self, position):
        self.mediaPlayer.setPosition(position)
        
    def positionChanged(self, position):
        self.positionSlider.setValue(position)
        self.update_frame_number()
        # current location = mark frame location
        self.update_button_text()

    def durationChanged(self, duration):
        self.positionSlider.setRange(0, duration)
        self.update_frame_number()

    def update_frame_number(self):
        current_frame = int(self.mediaPlayer.position() // self.frame_duration)
        if current_frame != 0:
            current_frame += 1
        total_frames = int(self.mediaPlayer.duration() // self.frame_duration)
        self.statusBar.showMessage(f"{current_frame}/{total_frames}")
            
    def update_button_text(self):
        current_position = int(self.mediaPlayer.position() // self.frame_duration)
        if current_position != 0:
            current_position += 1
        # current location = mark frame location
        group_name = None
        for group, frames in self.true_frames.items():
            if current_position in frames:
                group_name = str(group) if group < 10 else chr(ord('A') + group - 10)
                break
        
        if group_name:
            self.markFrameButton.setText(group_name)
        else:
            self.markFrameButton.setText("No Marked")
        
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Space:
            self.play() 
            return 
 
        if event.key() == Qt.Key.Key_Right:
            self.mediaPlayer.pause()
            position = self.mediaPlayer.position()
            new_position = int(position + self.frame_duration)
            self.mediaPlayer.setPosition(new_position)
        elif event.key() == Qt.Key.Key_Left:
            self.mediaPlayer.pause()
            position = self.mediaPlayer.position()
            new_position = int(max(0, position - self.frame_duration))
            self.mediaPlayer.setPosition(new_position)
        frame_keys = [Qt.Key.Key_0, Qt.Key.Key_1, Qt.Key.Key_2, Qt.Key.Key_3,
                      Qt.Key.Key_4, Qt.Key.Key_5, Qt.Key.Key_6, Qt.Key.Key_7,
                      Qt.Key.Key_8, Qt.Key.Key_9, Qt.Key.Key_A, Qt.Key.Key_B,
                      Qt.Key.Key_C, Qt.Key.Key_D, Qt.Key.Key_E, Qt.Key.Key_F]
        
        for i, key in enumerate(frame_keys):
            if event.key() == key:
                current_frame = int(self.mediaPlayer.position() // self.frame_duration)
                if current_frame != 0:
                    current_frame += 1
                if key not in self.frame_range:
                    self.frame_range[key] = []
                    self.frame_range[key].append(current_frame)  # Set start frame
                    self.true_frames[i].append(current_frame)
                else:
                    if len(self.frame_range[key]) >= 2:
                        if current_frame < self.frame_range[key][0]:
                            del self.frame_range[key][0]
                            self.frame_range[key].insert(0, current_frame)
                        else:
                            del self.frame_range[key][1]
                            self.frame_range[key].append(current_frame)
                    else:
                        if current_frame < self.frame_range[key][0]:
                            self.frame_range[key].insert(0, current_frame)
                        else:
                            self.frame_range[key].append(current_frame)
                    start_frame = self.frame_range[key][0]
                    end_frame = self.frame_range[key][1]
                
                    # Update 
                    self.true_frames[i] = list(range(start_frame, end_frame + 1))
                    
                self.update_marked_info()
                self.update_button_text()

    def handleError(self):
        self.playButton.setEnabled(False)
        self.statusBar.showMessage("Error: " + self.mediaPlayer.errorString())

if __name__ == '__main__':
    signal.signal(signal.SIGINT, quit_app)
    
    parser = argparse.ArgumentParser(description='Process arguments.', usage='video.py -g [name] <-s [int]>')
    parser.add_argument('-g', required=True, help='Name for new directory')
    parser.add_argument('-s', type=int, default=10, help='Hash setting, Default = 10')
    parser.add_argument('-p', default="", help='path setting, Default = Video path')
    args = parser.parse_args()
    
    directory_path = args.p if args.p else os.getcwd()
    create_directory(directory_path, args.g)

    app = QApplication(sys.argv)
    app.setStyleSheet("""
        QStatusBar {
            font-size: 12px;
        }
    """)
    player = VideoPlayer(group_name=args.g, directory_path=directory_path)
    player.setWindowTitle("Player")
    player.resize(900, 600)
    player.show()
    sys.exit(app.exec())
