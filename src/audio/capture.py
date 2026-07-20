"""4채널 마이크 어레이에서 오디오를 읽어 큐에 넣는다.

큐에 넣는 것은 '모노 float32 블록' 하나다.
- 다운스트림(VAD → STT)은 모노 16kHz 만 필요하다.
- 화자 방향(DOA)은 ReSpeaker 칩이 USB로 따로 알려주므로(→ doa.py),
  캡처 단계에서 4채널을 모두 들고 다닐 이유가 없다.
그래서 여기서 바로 모노로 줄여 큐를 단순하게 유지한다.
"""
import sys
import queue

import numpy as np
import sounddevice as sd


def find_input_device(name_hint: str):
    """이름에 name_hint(예: "ReSpeaker")가 든 '입력' 장치의 번호를 찾는다.

    개발 중엔 ReSpeaker가 안 꽂혀 있을 수 있다. 그럴 땐 None을 돌려주고,
    호출한 쪽에서 기본 마이크로 넘어가게 한다. 이렇게 해야 하드웨어가
    없어도 코드를 돌려보며 검증할 수 있다.
    """
    for index, dev in enumerate(sd.query_devices()):
        if dev["max_input_channels"] > 0 and name_hint.lower() in dev["name"].lower():
            return index
    return None


class MicArray:
    def __init__(self, cfg: dict, sink) -> None:
        self.cfg = cfg
        self.sink = sink          # queue.Queue — 여기에 모노 오디오 블록을 넣는다
        self.stream = None

    def start(self) -> None:
        device = find_input_device(self.cfg["device"])   # 부분 문자열 매칭
        channels = self.cfg["channels"]

        # ReSpeaker를 못 찾았으면 기본 마이크로 대체한다.
        # 기본 마이크는 보통 1~2채널이라 4채널을 요청하면 실패하므로,
        # 장치가 허용하는 채널 수로 줄인다.
        if device is None:
            default_in = sd.query_devices(kind="input")
            channels = min(channels, default_in["max_input_channels"])
            print(f"[capture] '{self.cfg['device']}' 못 찾음 → 기본 입력 "
                  f"'{default_in['name']}', {channels}채널")
        else:
            print(f"[capture] 장치 #{device} 사용, {channels}채널")

        # block_ms 만큼의 프레임을 한 블록으로 모아서 콜백에 넘긴다.
        blocksize = int(self.cfg["sample_rate"] * self.cfg["block_ms"] / 1000)

        def callback(indata, frames, time_info, status):
            if status:
                # 오버플로/언더런 같은 문제는 흘리지 말고 눈에 보이게 남긴다.
                print(f"[capture] 경고: {status}", file=sys.stderr)
            # indata: (frames, channels) float32.
            # 채널 0 하나만 쓴다. ReSpeaker에선 채널 0이 칩이 빔포밍·에코제거를
            # 끝낸 '처리된' 채널이라 음성인식에 가장 깨끗하다. 기본 마이크에서도
            # 채널 0이면 충분하다. (4채널 평균은 정렬 없이 섞여 오히려 흐려진다)
            mono = indata[:, 0].copy()   # copy: 콜백 버퍼는 재사용되므로 반드시 복사
            self.sink.put(mono)

        self.stream = sd.InputStream(
            samplerate=self.cfg["sample_rate"],
            blocksize=blocksize,
            device=device,
            channels=channels,
            dtype="float32",
            callback=callback,
        )
        self.stream.start()

    def stop(self) -> None:
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None


# ---------------------------------------------------------------------------
# 자체 테스트: `python src/audio/capture.py` 로 몇 초 녹음해서
# 블록이 들어오는지, 음량이 잡히는지 확인하고 wav로 저장해 귀로 들어본다.
# (하드웨어/배선이 맞는지 가장 빠르게 확인하는 방법이다.)
# ---------------------------------------------------------------------------
def _selftest() -> None:
    import wave
    from pathlib import Path

    import yaml

    cfg_path = Path(__file__).resolve().parents[1] / "config.yaml"
    with open(cfg_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)["audio"]

    q: queue.Queue = queue.Queue()
    mic = MicArray(cfg, sink=q)

    seconds = 3
    print(f"[selftest] {seconds}초 녹음 시작... 마이크에 대고 말해보세요.")
    mic.start()

    collected = []
    import time
    end = time.time() + seconds
    while time.time() < end:
        try:
            collected.append(q.get(timeout=0.5))
        except queue.Empty:
            pass
    mic.stop()

    if not collected:
        print("[selftest] 블록이 하나도 안 들어왔습니다. 장치를 확인하세요.")
        return

    audio = np.concatenate(collected)
    rms = float(np.sqrt(np.mean(audio ** 2)))
    peak = float(np.max(np.abs(audio)))
    print(f"[selftest] 블록 {len(collected)}개, 샘플 {len(audio)}개")
    print(f"[selftest] RMS={rms:.4f}  peak={peak:.4f}  "
          f"(거의 0이면 소리가 안 들어온 것)")

    out = Path(__file__).resolve().parents[2] / "capture_test.wav"
    pcm16 = np.clip(audio, -1.0, 1.0)
    pcm16 = (pcm16 * 32767).astype(np.int16)
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(cfg["sample_rate"])
        w.writeframes(pcm16.tobytes())
    print(f"[selftest] 저장: {out}  (재생: aplay '{out}')")


if __name__ == "__main__":
    _selftest()
