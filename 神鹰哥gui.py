from utils import load, split
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from threading import Thread, Lock
import pyttsx3
import pydub
import pydub.playback
from pathlib import Path
import sys


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        try:
            dir = Path(sys._MEIPASS)
        except:
            dir = Path(".")
        self.setWindowTitle("memeTTS")
        bg_pixmap = QPixmap(str(dir / "略有失重感.png"))
        palette = QPalette()
        palette.setBrush(QPalette.Background, QBrush(bg_pixmap))
        self.setPalette(palette)
        self.setAutoFillBackground(True)
        self.dir = dir
        self.data = load(dir / "audios", dir / "name.json")
        self.engine = pyttsx3.init()
        self.speaking = Lock()
        self.playing = True
        self.play_obj = None
        self.music_vol = -15
        self.voice_vol = 5

        self.layout1 = QVBoxLayout()
        self.layout2 = QHBoxLayout()
        self.message = QTextEdit()
        self.message.setReadOnly(True)
        self.message.setStyleSheet("""
            QTextEdit {
                background: transparent;
                border: 2px solid gray;
                border-radius: 8px;
                padding: 10px;
                color: black;
            }
        """)
        self.music_vol_s = QSlider(Qt.Horizontal)
        self.music_vol_s.setRange(-20, 20)
        self.music_vol_s.setValue(-15)
        self.music_vol_s.valueChanged.connect(self.set_music_vol)
        self.voice_vol_s = QSlider(Qt.Horizontal)
        self.voice_vol_s.setRange(-20, 20)
        self.voice_vol_s.setValue(5)
        self.voice_vol_s.valueChanged.connect(self.set_voice_vol)
        self.input = QLineEdit()
        self.send = QPushButton("发送")
        self.send.clicked.connect(self.send_message)
        self.stop_music_b = QPushButton("停止播放")
        self.stop_music_b.clicked.connect(self._stop)
        self.layout2.addWidget(self.input)
        self.layout2.addWidget(self.send)
        self.layout2.addWidget(self.stop_music_b)
        self.layout1.addWidget(self.message)
        self.layout1.addWidget(self.music_vol_s)
        self.layout1.addWidget(self.voice_vol_s)
        self.layout1.addLayout(self.layout2)
        self.setLayout(self.layout1)
        t = Thread(target = self._play)
        t.daemon = True
        t.start()
    
    def set_music_vol(self, value):
        self.music_vol = value
        if self.play_obj:
            self.play_obj.stop()

    
    def set_voice_vol(self, value):
        self.voice_vol = value
    
    def _play(self):
        while self.playing:
            obj = pydub.AudioSegment.from_file(self.dir / "岁月无声DJ.mp3")
            obj += self.music_vol
            self.play_obj = pydub.playback._play_with_simpleaudio(obj)
            self.play_obj.wait_done()

    def _stop(self):
        self.playing = False
        if self.play_obj:
            self.play_obj.stop()

    def _speak_(self, text: str):
        with self.speaking:
            words = split(text, self.data)
            for word in words:
                if word in self.data:
                    obj = pydub.AudioSegment.from_file(self.data[word])
                    obj += self.voice_vol
                    pydub.playback.play(obj)
                else:
                    self.engine.say(word)
                    self.engine.runAndWait()
    
    def send_message(self) -> None:
        t = Thread(target=self._speak_, args=(self.input.text(),))
        t.daemon = True
        t.start()
        self.message.append(self.input.text())
        self.input.clear()


if __name__ == '__main__':
    app = QApplication([])
    window = MainWindow()
    window.show()
    window.resize(800, 600)
    app.exec_()