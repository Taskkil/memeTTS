from pathlib import Path
import os
from typing import List, Dict, Tuple, Union, Optional, AnyStr, Iterable, Mapping, Container, Sequence, Hashable, Type, Generator
import json
from io import StringIO
import pyttsx3
import pydub
import pydub.playback
from threading import Lock
import random
import time
from queue import Queue
from threading import Event


def load(dir: str | Path, map:AnyStr | Mapping | Path | None = None, suffixs: List[str] | None = None) -> Dict[str, Path]:
    path = Path(dir)
    files = [file for file in path.rglob("*") if file.is_file()]
    if isinstance(map, dict):
        pass
    elif isinstance(map, str | Path):
        map = Path(map)
        with open(map, 'r', encoding="utf8") as f:
            map = json.load(f)
    else:
        map = {}
    assert isinstance(map, Mapping), "map must be a Mapping"
    data = {}
    if suffixs is None:
        suffixs = [".wav", ".mp3", ".flac", ".m4a"]
    for file in files:
        if file.is_file() and file.suffix in suffixs:
            if file.name in map:
                name = map[file.name]
            elif file.stem in map:
                name = map[file.stem]
            else:
                name = file.stem
            
            if isinstance(name, str):
                data[name] = file
            elif isinstance(name, Iterable):
                for n in name:
                    data[n] = file
            else:
                data[str(name)] = file
    return data

class PTrie:
    "Trie mainly deals with prefixes"
    def __init__(self, seqs: Iterable[Sequence[Hashable]], seqtype = None):
        self.table:Dict[Hashable, PTrie] = {}
        self.seqtype:Type = seqtype
        self.is_seq_end = False
        for seq in seqs:
            if self.seqtype is None:
                self.seqtype = type(seq)
            self.add(seq)
        if self.seqtype is None:
            self.seqtype = list
    
    def add(self, seq: Sequence[Hashable]):
        "Adds a sequence to the trie"
        if not seq:
            self.is_seq_end = True
            return
        w = seq[0]
        _w = seq[1:]
        if w in self.table:
            if _w:
                self.table[w].add(_w)
        else:
            self.table[w] = PTrie([_w], seqtype=self.seqtype)
    
    def walk(self, seq: Sequence[Hashable]) -> Generator[Sequence[Hashable], None, None]:
        "Iterate over all sequence in the trie that start with seq"
        subtree = self[seq]
        for subseq in subtree:
            yield seq + subseq
    
    def final(self, seq: Sequence[Hashable]) -> bool:
        "Whether there are no longer sequences starting with seq"
        subtree = self[seq]
        return subtree.is_seq_end and not subtree.table
    
    def longest(self, seq: Sequence[Hashable], is_seq_end=True) -> Sequence[Hashable] | None:
        "The longest sequence that can serve as the beginning of a seq"
        if not seq:
            return self.seqtype() if (self.is_seq_end or not is_seq_end) else None
        
        current = self
        if self.seqtype == str:
            result = []
        else:
            result = self.seqtype()
        last_valid = None
        length = 0
        for item in seq:
            if item not in current.table:
                break
            current = current.table[item]
            if self.seqtype == str:
                result.append(item)
            else:
                if hasattr(result, "append"):
                    result.append(item)
                elif hasattr(result, "__add__"):
                    result += self.seqtype(item)
                else:
                    raise TypeError("Unsupport type")
            length += 1
            if current.is_seq_end:
                last_valid = length
        if self.seqtype == str:
            result = "".join(result)

        if is_seq_end:
            if last_valid is None:
                return None
            else:
                return result[:last_valid]
        else:
            return result if result else None
    
    def index(self, seq: Sequence[Hashable]) -> int | None:
        "Find the index of the first sequence in the sequence that exists within itself"
        for i in range(len(seq)):
            current = self
            for j in range(i, len(seq)):
                if seq[j] not in current.table:
                    break
                current = current.table[seq[j]]
                if current.is_seq_end:
                    return i
        return None

    
    def is_prefix(self, seq):
        if not seq:
            return True
        w = seq[0]
        _w = seq[1:]
        if w in self.table:
            return self.table[w].is_prefix(_w)
        else:
            return False
    
    def __repr__(self):
        return str([i for i in self.__iter__()])

    def __contains__(self, seq: Sequence[Hashable]):
        if not seq and self.is_seq_end:
            return True
        w = seq[0]
        _w = seq[1:]
        if w in self.table:
            return _w in self.table[w]
        else:
            return False
    
    def __iter__(self):
        for w, sub_trie in self.table.items():
            if sub_trie.is_seq_end:
                yield self.seqtype([w])
            
            for subseq in sub_trie:
                yield self.seqtype([w]) + subseq
    
    def __len__(self):
        return len([i for i in self.__iter__()])
    
    def __getitem__(self, seq: Sequence[Hashable]):
        if not seq:
            return self
        w = seq[0]
        _w = seq[1:]
        if w in self.table:
            return self.table[w][_w]
        else:
            raise KeyError(seq)

    def __bool__(self):
        return bool(self.table)


class Stream:
    def __init__(self, queue: Queue, stop_sign = StopIteration):
        self.queue = queue
        self.stop_sign = stop_sign
    
    def __iter__(self) -> Generator:
        while True:
            try:
                data = self.queue.get()
                if data == self.stop_sign:
                    break
                yield data
            except GeneratorExit:
                break



def split(string:str, words:Iterable[str], ptrie = None) -> Generator[str, None, None] | List[str]:
    """Split a string into words and non-words"""
    if not words:
        yield string
        return
    if ptrie is None:
        ptrie = PTrie(words)
    current = StringIO()
    i = 0
    n = len(string)
    while i < n:
        longest_match = ptrie.longest(string[i:])
        if longest_match:
            if current.tell():
                yield current.getvalue()
                current = StringIO()
            yield longest_match # type: ignore
            i += len(longest_match)
        else:
            current.write(string[i])
            i += 1
    if current.tell():
        yield current.getvalue()

def _split(string, words:Iterable[str]):
    "Simple and error free"
    if not words:
        yield string
        return
    max_len = max(len(w) for w in words)
    current = StringIO()
    last = 0
    for s in range(len(string)):
        if s < last:
            continue
        for e in range(min(s+max_len, len(string)), s, -1):
            # prioritize matching the longest word
            if string[s:e] in words:
                if current.tell():
                    yield current.getvalue()
                    current = StringIO()
                last = e
                yield string[s:e]
                break
        else:
            current.write(string[s])
    if current.tell():
        yield current.getvalue()




def split_stream(stream: Iterable[str], words: Iterable[str], sep = None, ptrie = None) -> Generator[str, None, None]:
    """Split a strem into words and non-words"""
    def single_char(stream: Iterable[str]):
        for string in stream:
            if len(string) == 1:
                yield string
            else:
                for char in string:
                    yield char
    words_set = set(words)
    if not words_set:
        current = StringIO()
        for char in single_char(stream):
            if char == sep:
                yield current.getvalue()
                current = StringIO()
            else:
                current.write(char)
        if current.tell():
            yield current.getvalue()
        return
    
        
    max_len = max(len(word) for word in words_set)
    starts = {word[0] for word in words_set if word}
    if ptrie is None:
        prefix_tree = PTrie(words_set)
    else:
        prefix_tree = ptrie
    
    current = StringIO()
    buffer = []
    for char in single_char(stream): # iterate over the stream
        if char == sep:
            while buffer:
                longest_match = prefix_tree.longest(buffer)
                if longest_match is not None:
                    if current.tell():
                        yield current.getvalue()
                        current = StringIO()
                    yield longest_match # type: ignore
                    buffer = buffer[len(longest_match):]
                else:
                    current.write(buffer.pop(0))
            if current.tell():
                yield current.getvalue()
                current = StringIO()
            continue
        buffer.append(char)
        index = prefix_tree.index(buffer) # find the index of the possible word
        # print(buffer, index)
        if index is not None:
            for i in range(index):
                # print(2)
                current.write(buffer.pop(0))
            if current.tell():
                yield current.getvalue()
                current = StringIO()
        if buffer and buffer[0] in starts: # possible start
            s = ''.join(buffer)
            if len(s) < max_len: # is buffer is too long?
                if prefix_tree.is_prefix(s) and not prefix_tree.final(s):
                    continue # longer word may appear
                else:
                    longest_match = prefix_tree.longest(s)
                    if longest_match is not None:
                        if current.tell():
                            yield current.getvalue()
                        yield longest_match # type: ignore
                        current = StringIO()
                        buffer = buffer[len(longest_match):]
                    else:
                        current.write(buffer.pop(0))
            else:
                longest_match = prefix_tree.longest(s)
                if longest_match is not None:
                    if current.tell():
                        yield current.getvalue()
                    yield longest_match # type: ignore
                    current = StringIO()
                    buffer = buffer[len(longest_match):]
                else:
                    current.write(buffer.pop(0))
        else:
            current.write(buffer.pop(0))

    while buffer:
        longest_match = prefix_tree.longest(buffer)
        if longest_match is not None:
            if current.tell():
                yield current.getvalue()
            yield longest_match # type: ignore
            current = StringIO()
            buffer = buffer[len(longest_match):]
        else:
            current.write(buffer.pop(0))
    if current.tell():
        yield current.getvalue()


def _split_stream(stream: Iterable[str], words: Iterable[str]):
    "Simple and error free"
    words_set = set(words)
    if not words_set:
        current = StringIO()
        for char in stream:
            current.write(char)
        yield current.getvalue()
        return
    
    def single_char(stream: Iterable[str]):
        for string in stream:
            if len(string) == 1:
                yield string
            else:
                for char in string:
                    yield char
        
    max_len = max(len(word) for word in words_set)
    starts = {word[0] for word in words_set if word}
    
    ptrie = PTrie(words_set)
    
    current = StringIO()
    buffer = []
    for char in single_char(stream):
        buffer.append(char)
        if buffer and buffer[0] in starts:
            s = ''.join(buffer)
            if len(s) < max_len:
                if ptrie.is_prefix(s):
                    continue
                else:
                    found = None
                    for e in range(len(s), 0, -1):
                        candidate = s[:e]
                        if candidate in words_set:
                            found = e
                            break
                    if found is not None:
                        if current.tell():
                            yield current.getvalue()
                        yield candidate
                        current = StringIO()
                        buffer = buffer[found:]
                    else:
                        current.write(buffer.pop(0))
            else:
                found = None
                for e in range(min(len(buffer), max_len), 0, -1):
                    candidate = ''.join(buffer[:e])
                    if candidate in words_set:
                        found = e
                        break
                if found is not None:
                    if current.tell():
                        yield current.getvalue()
                    yield candidate
                    current = StringIO()
                    buffer = buffer[found:]
                else:
                    current.write(buffer.pop(0))
        else:
            if buffer:
                current.write(buffer.pop(0))
                
    while buffer:
        if buffer and buffer[0] in starts:
            s = ''.join(buffer)
            if len(s) < max_len:
                if ptrie.is_prefix(s):
                    found = None
                    for e in range(min(len(buffer), max_len), 0, -1):
                        candidate = ''.join(buffer[:e])
                        if candidate in words_set:
                            found = e
                            break
                    if found is not None:
                        if current.tell():
                            yield current.getvalue()
                        yield candidate
                        current = StringIO()
                        buffer = buffer[found:]
                    else:
                        current.write(buffer.pop(0))
                else:
                    found = None
                    for e in range(len(s), 0, -1):
                        candidate = s[:e]
                        if candidate in words_set:
                            found = e
                            break
                    if found is not None:
                        if current.tell():
                            yield current.getvalue()
                        yield candidate
                        current = StringIO()
                        buffer = buffer[found:]
                    else:
                        current.write(buffer.pop(0))
            else:
                found = None
                for e in range(min(len(buffer), max_len), 0, -1):
                    candidate = ''.join(buffer[:e])
                    if candidate in words_set:
                        found = e
                        break
                if found is not None:
                    if current.tell():
                        yield current.getvalue()
                    yield candidate
                    current = StringIO()
                    buffer = buffer[found:]
                else:
                    current.write(buffer.pop(0))
        else:
            current.write(buffer.pop(0))
            
    content = current.getvalue()
    if content:
        yield content


def speak(texts: Iterable[str], data: dict):
    if type(texts) != str:
        for word in texts:
            if word in data:
                obj = pydub.AudioSegment.from_file(data[word])
                pydub.playback.play(obj)
            else:
                os.system("powershell -Command \"Add-Type –AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak('%s')\""%word.replace("'", '"'))
    else:
        if texts in data:
            obj = pydub.AudioSegment.from_file(data[texts])
            pydub.playback.play(obj)
        else:
            os.system("powershell -Command \"Add-Type –AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak('%s')\""%texts.replace("'", '"'))

def main():
    data = load("./audios", "./name.json")

    # print([i for i in data])
    while True:
        words = [i for i in _split(input(">>> "), data)]
        print(words)
        speak(words, data=data)


def stream_test():
    data = load("./audios", "./name.json")
    def _stream_ouput(words: Iterable[str]):
        for word in words:
            print(word)
            speak(word, data=data)
    def _stream_input():
        while True:
            try:
                yield input(">>> ")
            except EOFError:
                break
            except KeyboardInterrupt:
                break
            except GeneratorExit:
                break
    while True:
        _stream_ouput(split_stream(_stream_input(), data, sep="\\"))

def random_data(data_size, min_l, max_l, word_count, ratio = 0.1):
    words = set()
    for i in range(word_count):
        word = StringIO()
        for j in range(random.randint(min_l, max_l + 1)):
            word.write(str(random.randint(0, 10)))
        words.add(word.getvalue())
    words_ = list(words)
    data = StringIO()
    i = 0
    while i < data_size:
        if random.random() < (ratio / (min_l + max_l) * 2):
            w = random.choice(words_)
            data.write(w)
            i += len(w)
            continue
        data.write(str(random.randint(0, 10)))
        i += 1
    data = data.getvalue()
    return data, words

def _time(func, args = [], kwargs = {}):
    t1 = time.time()
    result = len([i for i in func(*args, **kwargs)])
    t2 = time.time()
    return result, t2 - t1


# if __name__ == "__main__":
#     data, words = random_data(1e6, 5, 20, 256)
#     funcs = [_split_stream, split_stream]
#     times = [0. for _ in funcs]
#     for _ in range(10):
#         for i in range(len(funcs)):
#             r, t = _time(funcs[i], args=(data, words))
#             times[i] += t / 10
#     print(times)
#     while True:
#         exec(input(">>> "))

if __name__ == "__main__":
    # ptrie = PTrie(["a", "ab"])
    # print(ptrie.index("a"))
    # main()
    stream_test()
    

# def aaa(s:str):
#     d:set[str] = set()
#     d.add(s)
#     d.add(s.lower())
#     d.add(s.upper())
#     d.add(s.title())
#     d.add(s[0].upper() + s[1:].lower())
#     a = d.copy()
#     d.update({x.replace(" ","") for x in a})
#     return list(d)

# print(json.dumps(aaa("Never Gonna Tell a Lie And Hurt You"), ensure_ascii=False, indent=4))


# if __name__ == "__main__":
#     print([i for i in split_stream("""```
# 庭院深深深几许，
# 杨柳堆烟，帘幕无重数。
# 玉勒雕鞍游冶处，
# 楼高不见章台路。

# 雨横风狂三月暮，
# 门掩黄昏，无计留春住。
# 泪眼问花花不语，
# 乱红飞过秋千去。
# ```

# 这是宋代词人欧阳修的《蝶恋花·庭院深深深几许》词的上阕。如需其他类型的多行文本，请随时告知。""", {"bcdef"}, sep="\n")])