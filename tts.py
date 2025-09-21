import pyttsx3
from queue import Queue
from utils import load, split_stream, speak
from threading import Thread
import os

class Speaker:
    def __init__(self, data, engine: pyttsx3.Engine, sep = None):
        if type(data) == str:
            self.data = load(data)
        else:
            self.data = data
        self.engine = engine
        self.speak_thread = None
        self.queue = Queue()
        self.sep = object() if sep is None else sep
        self.stop_sign = object()
    
    def speak(self, text: str, sep = False):
        self.queue.put(text)
        if sep:
            self.queue.put(self.sep)
        if self.speak_thread is None or not self.speak_thread.is_alive():
            self.speak_thread = Thread(target = self._speak)
            self.speak_thread.daemon = True
            self.speak_thread.start()
    
    def finish(self):
        self.queue.put(self.sep)
    
    def stop(self):
        self.queue.put(self.stop_sign)

    def _speak(self):
        for i in split_stream(self._get(), self.data, sep=self.sep):
            speak(i, data=self.data)

    def _get(self):
        while True:
            data = self.queue.get()
            if data is self.stop_sign:
                break
            else:
                yield data



# if __name__ == '__main__':

#     speaker = Speaker(load("./audios", "./name.json"), pyttsx3.init(), sep="\n")
#     while True:
#         speaker.speak(input(">>> ") + "\n")

