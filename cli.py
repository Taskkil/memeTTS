from utils import load, split, main
import sys
import pydub
import pyttsx3
import pydub.playback

if __name__ == "__main__":
    string = " ".join(sys.argv[1:])
    if not string:
        main()
    else:
        engine = pyttsx3.init()
        data = load("./audios", "./name.json")
        words = split(string, data)
        for word in words:
            if word in data:
                obj = pydub.AudioSegment.from_file(str(data[word]))
                pydub.playback.play(obj)
            else:
                engine.say(word)
                engine.runAndWait()