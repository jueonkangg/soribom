"""짧은 음성에서 생성된 비정상적인 연속 구절 반복만 줄인다."""
import math
import re


def trim_repetition_loops(text, audio_seconds):
    # 실제로 길게 반복한 설명은 보존한다. 밀도가 비정상적일 때만 검사한다.
    if not math.isfinite(audio_seconds) or audio_seconds <= 0:
        return text, 0
    words = list(re.finditer(r"[^\W_]+", text, re.UNICODE))
    letters = sum(len(word.group()) for word in words)
    if letters / audio_seconds <= 35:
        return text, 0
    values = [word.group().casefold() for word in words]
    pieces = []
    cursor = index = removed = 0
    while index < len(words):
        found = False
        for width in range(1, min(20, (len(words) - index) // 4) + 1):
            unit = values[index:index + width]
            unit_letters = sum(len(word) for word in unit)
            end = index + width
            repeats = 1
            while values[end:end + width] == unit:
                repeats += 1
                end += width
            # 한 글자 감탄사도 수십 번 쏟아지면 차단하되 짧은 실제 반복은 남긴다.
            minimum_repeats = 16 if unit_letters < 4 else 4
            if repeats < minimum_repeats or unit_letters * (repeats - 1) < 32:
                continue
            # 앞뒤 설명과 첫 구절은 남기고 같은 구절의 두 번째 이후만 제거한다.
            pieces.append(text[cursor:words[index + width - 1].end()])
            cursor = words[end - 1].end()
            removed += repeats - 1
            index = end
            found = True
            break
        if not found:
            index += 1
    if not removed:
        return text, 0
    pieces.append(text[cursor:])
    return "".join(pieces), removed
