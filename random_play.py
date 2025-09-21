from utils import load, speak
import random

data = load("./audios")
while True:
    speak(random.choice(list(data.keys())), data)