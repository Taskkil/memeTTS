from openai import OpenAI
from utils import load
import os
from io import StringIO
import pyttsx3
from tts import Speaker

client = OpenAI(base_url="https://api.deepseek.com/v1", api_key=os.getenv("DEEPSEEK_API_KEY"))
words = load("./audios", "./name.json", suffixs=[".mp3", ".wav"])
names = [i for i in load("./audios", suffixs=[".mp3", ".wav"]).keys()]
messages = [{"role": "system", "content": f"""你是deepfuck,一个在B站多年的网友,喜欢玩梗
你经常玩的梗有:
{names}
根据情况适当使用这些梗
不要过度使用,除用户特殊要求外,一句话最多使用一个梗
使用梗时必须保持语义连贯,必须与上下文匹配,不能为了凑数而使用
"""}]
engine = pyttsx3.init()
speaker = Speaker(words, engine, "\n")

print(messages[0]["content"])


while True:
    prompt = StringIO()
    while True:
        try:
            d = input(">>> ")
        except EOFError:
            break
        prompt.write(d + "\n")
    prompt = prompt.getvalue()
    
    response = StringIO()
    messages.append({"role": "user", "content": prompt})
    request = client.chat.completions.create(
        messages=messages,
        model="deepseek-chat",
        stream=True,
    ) # type: ignore
    for chunk in request:
        if not chunk:
            continue
        content = chunk.choices[0].delta.content
        if not content:
            continue
        response.write(content)
        speaker.speak(content)
        try:
            print(content, end="", flush=True)
        except KeyboardInterrupt:
            break
    response = response.getvalue()
    speaker.finish()
    print()
    messages.append({"role": "assistant", "content": response})