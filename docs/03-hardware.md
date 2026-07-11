# 3. 하드웨어 구성과 배선

![하드웨어 구성도](figures/hardware.png)

## 구성

| 블록 | 부품 | 연결 |
|---|---|---|
| 입력 | ReSpeaker Mic Array v3.0 (4채널) | USB |
| 연산 | NVIDIA Jetson Orin Nano Super | — |
| 화면 | 터치 디스플레이 7~10" | HDMI |
| 저장 | NVMe SSD 500GB | M.2 (내장) |
| 소리 출력 ① | 이어버드 / 보청기 | 블루투스 |
| 소리 출력 ② | 단말 내장 스피커 | **I2S** |
| 전원 | 19V 어댑터 (키트 포함) | DC |

소리 출력이 **두 갈래**인 것이 핵심입니다.

- **이어버드/보청기 (BT)** — 학생 귀로 깨끗한 소리를 전달 (기능 ④)
- **내장 스피커 (I2S)** — TTS 발화를 학생 자리에서 내보내 반 전체가 듣는다 (기능 ⑥)

## I2S 스피커 배선

MAX98357A는 I2S 디지털 입력을 받아 Class-D로 증폭합니다 (3.2W @ 4Ω).

| MAX98357A | Jetson Orin Nano 40핀 헤더 |
|---|---|
| VIN | 5V (Pin 2 또는 4) |
| GND | GND (Pin 6) |
| BCLK | I2S_BCLK |
| LRC (LRCLK/WS) | I2S_LRCLK |
| DIN | I2S_SDOUT |
| GAIN | 미연결 = 9dB (기본) |
| SD | 미연결 = 좌+우 평균 (모노) |

스피커는 4Ω 유닛을 앰프 출력(+/-)에 연결합니다.

### ALSA 등록

`jetson-io`로 40핀 헤더의 I2S 기능을 활성화한 뒤 재부팅하면 사운드카드로 잡힙니다.

```bash
sudo /opt/nvidia/jetson-io/jetson-io.py   # I2S 활성화 → 재부팅
aplay -l                                   # I2S 카드 확인
aplay -D plughw:<card>,0 test.wav          # 발화 테스트
```

`src/config.yaml`의 `tts.output_device`에 위에서 확인한 카드를 지정합니다.

## 안전

내장 스피커는 공기 중으로 소리를 내보내는 일반 스피커라 리미터가 필수는 아닙니다.
다만 블루투스로 **귀에 직접** 보내는 경로(기능 ④)는 세이프티 리미터가 반드시 걸립니다.
자세한 내용은 [05-safety.md](05-safety.md).
