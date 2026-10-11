# 3. 하드웨어 구성과 배선

> 현재 구성 확인: 2026-10-11. 블루투스 스피커 전환 경위는
> [개발 로그](conversation_log.md), 현재 동작은 [시스템 설계](02-system-design.md) 참고.

![하드웨어 구성도](figures/hardware.png)

위 그림은 초기 구성으로 현재 화면·스피커 구성과 다릅니다.

## 구성

| 블록 | 부품 | 연결 |
|---|---|---|
| 입력 | ReSpeaker Mic Array v3.0 (4채널) | USB |
| 연산 | NVIDIA Jetson Orin Nano Super | — |
| 화면 | 15.6" FHD 터치 디스플레이 | DisplayPort→HDMI 변환, 터치는 별도 USB |
| 저장 | NVMe SSD 500GB | M.2 (내장) |
| 현재 소리 출력 | 블루투스 스피커 (기록상 Bose BT) | 시스템 기본 출력 |
| 초기 제작 시도 | MAX98357A + 스피커 | I2S, 정상 동작하지 않아 현재 미사용 |
| 전원 | 19V 어댑터 (키트 포함) | DC |

현재 TTS는 `src/config.yaml`의 `tts.output_device: null`에 따라 시스템 기본 출력을 사용합니다.
블루투스 스피커를 연결한 뒤 OS의 출력 장치를 확인합니다. 이어버드/보청기로 교실 음성을
전달하는 기능 ④는 미구현이며, BT 스피커의 TTS 재생과 별개입니다.

## 기기 설치 순서

1. PC 케이스의 구멍 있는 팬 부분이 위를 향하도록 테이블에 둡니다.
2. 화면·터치·마이크 등 케이블을 연결합니다.
3. 전원 케이블은 연결 즉시 전원이 들어오므로 마지막에 연결합니다.
4. 블루투스 스피커를 켜고 컴퓨터에 연결한 뒤 기본 출력으로 선택합니다.
5. 소리봄을 실행하고 상단 마이크/방향 상태와 타이핑 말하기 출력을 확인합니다.

마이크는 ReSpeaker만 사용하고 연결 실패 시 자동/수동 재연결을 시도합니다. 스피커의 BT 연결은
OS에서 관리하며 마이크 복구 기능이 대신 처리하지 않습니다.

## 초기 I2S 스피커 배선 기록 (현재 사용하지 않음)

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

현재 BT 스피커는 공기 중으로 TTS를 재생합니다. 초기 구상의 귀에 직접 전달하는 기능 ④와
리미터는 아직 구현되지 않았습니다. 보청기·인공와우에 직접 소리를 보내는 실험은 하지 않습니다.
자세한 내용은 [05-safety.md](05-safety.md).
