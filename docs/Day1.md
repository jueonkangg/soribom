# Day 1 — 첫날 할 일

**팀 제주 BTS · 소리봄 프로젝트**

> **🍎 = 맥 / 🪟 = 윈도우** — 자기 컴퓨터에 맞는 쪽만 보세요.
> 명령어는 **복사해서 붙여넣으세요.** 직접 타이핑하면 오타가 납니다.

---

## 오늘의 목표

1. **Jetson이 켜지고 초기 설정이 끝난다**
2. **마이크가 컴퓨터에 인식된다**
3. **각자 자기 파트의 "가장 작은 성공" 하나씩**
4. 오늘 한 걸 GitHub에 올린다

> 오늘은 완벽한 프로그램을 만드는 날이 아닙니다.
> **"어? 되네?"를 한 번씩 경험하는 날**입니다.

---

# 준비물 — 없으면 하루가 날아갑니다

전자부품 말고 **조립·설정에 필요한 물건**들입니다. 실제로 이것 때문에 하루를 잃었습니다.

## 반드시 필요한 것

| 물건 | 왜 필요한가 |
|---|---|
| **유선 USB 키보드** ⚠️ | **블루투스 키보드는 쓸 수 없습니다.** 페어링을 하려면 이미 키보드가 있어야 하는데, 초기 설정 화면에서는 그게 없습니다. 다이소 5천원짜리면 충분합니다 |
| **유선 USB 마우스** | 위와 같은 이유 |
| **정밀 십자 드라이버 (PH00 / PH0)** ⚠️ | M.2 나사는 아주 작습니다. **SSD에 동봉된 드라이버는 품질이 나빠 나사머리가 뭉갭니다.** 안경 수리용 정밀 드라이버 세트를 쓰세요 |
| **19V 전원 어댑터** | Jetson 박스 동봉품. 모니터용 USB-C 충전기와 **다릅니다** |
| **DP→HDMI 변환젠더** | Jetson에는 HDMI 단자가 없습니다 |

## 있으면 좋은 것

- 나사가 뭉갰을 때: **고무줄**을 드라이버와 나사 사이에 끼우면 마찰이 생겨 돌아갑니다
- 정전기 방지: 만지기 전에 금속(수도꼭지 등)을 한 번 짚기

> **Jetson은 부품이 아니라 "작은 PC 한 대"입니다.**
> PC를 새로 조립할 때 필요한 건 전부 필요하다고 생각하세요.

## 역할

| | 오늘 맡을 일 |
|---|---|
| **강주언** | Jetson 부팅·초기설정 (최우선) + TTS 첫 소리 |
| **함도유** | 마이크 인식 확인 + 화면(UI) 첫 창 |
| **강구현** | 음성인식 첫 성공 |

---

# 1부. Jetson 부팅 — 강주언

⏱️ 예상 2~3시간 (이미지 다운로드·굽기가 대부분)

## 1-0. 어떤 JetPack을 받나 — 먼저 읽으세요

| | **JetPack 6.2.1** ← 우리가 쓸 것 | JetPack 7.2 (r39) |
|---|---|---|
| 설치 | **microSD에 바로 굽기** | USB 메모리로 ISO 부팅 (복잡) |
| 우분투 | 22.04 (Python 3.10) | 24.04 (Python 3.12) |
| AI 라이브러리 | **자료가 많음** | 너무 최신이라 자료 부족 |
| NVIDIA 공식 | **첫 설치는 이 방법 권장** | 고급 사용자용 |

> ❌ **`jetsoninstaller-r39.2.0-...` 파일은 받지 마세요.** JetPack 7.2용입니다.

**받을 것:** [JetPack 6.2.1 — Jetson Orin Nano Developer Kit **SD Card Image**](https://developer.nvidia.com/embedded/jetpack-sdk-621)

약 10GB입니다. **먼저 다운로드를 걸어두고** 아래 1-1을 진행하세요.

---

## 1-1. balenaEtcher 설치

microSD에 운영체제를 "굽는" 프로그램입니다.

**🍎 맥**
```bash
brew install --cask balenaetcher
```

**🪟 윈도우** (PowerShell: `Win` + `X` → **터미널**)
```powershell
winget install Balena.Etcher
```

안 되면 [etcher.balena.io](https://etcher.balena.io/)에서 직접 받으세요.

---

## 1-2. microSD에 굽기

1. microSD를 컴퓨터에 꽂습니다
2. balenaEtcher 실행
3. **Flash from file** → 받은 `.zip` 선택 (**압축 풀지 마세요**)
4. **Select target** → microSD 선택

> ⚠️ **잘못 고르면 컴퓨터 하드가 통째로 지워집니다.**
> **용량이 64GB인지** 확인하세요. 🪟 `C:` 드라이브가 보이면 절대 고르지 마세요.

5. **Flash!** → 비밀번호 입력 (🪟 "허용" → 예)
6. **20~30분.** 중간에 뽑지 마세요
7. 끝나면 경고창이 뜹니다 — **정상입니다**
   - 🍎 "디스크를 읽을 수 없습니다" → **꺼내기**
   - 🪟 "디스크를 포맷해야 합니다" → **취소** (절대 포맷 누르지 마세요)

---

## 1-3. NVMe SSD 장착 — 전원 켜기 전에

SSD는 보드 바닥에 나사로 고정합니다. **전원을 넣기 전에** 하세요.

### 방열판은 붙인 채로 OK

떼지 않아도 보드에 들어갑니다. (케이스에 넣을 때만 나중에 확인)

### 장착

1. **전원 어댑터가 빠져 있는지 확인**
2. Jetson을 뒤집어 **바닥면**을 봅니다
3. **M.2 슬롯이 2개** 있습니다
   - **긴 쪽 (Key M)** = SSD 자리 ✅
   - 짧은 쪽 (Key E) = 와이파이 카드 자리 ❌
4. 슬롯 끝 **고정 나사를 풀어** 빼둡니다 (아주 작으니 분실 주의)
5. SSD를 **비스듬히(30도)** 꽂습니다 — 홈이 맞는 방향으로만 들어갑니다
6. 눌러 눕히고 **나사로 고정** — **살짝만** 조이세요

> ⚠️ **정밀 드라이버(PH00)를 쓰세요.** 동봉 드라이버는 나사머리를 뭉갭니다.
> 이미 뭉갰다면 **고무줄을 드라이버와 나사 사이에 끼우면** 돌아갑니다.

---

## 1-4. 🔍 펌웨어 확인 — 건너뛰지 마세요

NVIDIA가 **"건너뛰지 말라"**고 명시한 단계입니다. 오래된 공장 펌웨어면 JetPack 6이 부팅되지 않습니다.

1. microSD를 **아직 꽂지 말고** 모니터·키보드·전원만 연결해 켜기
2. 부팅 중 화면 왼쪽 위 **펌웨어 버전** 확인 (빠르면 휴대폰으로 촬영)
3. **36.x 이상** → 진행 ✅
4. **36.0 미만** → [펌웨어 업데이트](https://docs.nvidia.com/jetson/orin-nano-devkit/user-guide/latest/update_firmware.html)를 먼저

> Super 개발자 키트는 대부분 36.x 이상입니다. 확인만 하고 넘어가면 됩니다.

---

## 1-5. 선 연결

**전원은 맨 마지막**입니다.

1. **microSD**를 모듈 아랫면 슬롯에 꽂기 (딸깍)
2. Jetson **DisplayPort** → **DP→HDMI 젠더** → HDMI 케이블 → 모니터
3. 모니터에 **USB-C 충전기** 연결
4. **유선 키보드·마우스**를 Jetson USB 포트에
5. 마지막에 **19V 전원 어댑터** → 자동으로 켜집니다

> USB-C 옆 **초록 LED**가 켜지면 전원이 들어온 것입니다.

---

## 1-6. 초기 설정 (oem-config)

1. NVIDIA 로고 → 설정 화면
2. EULA 동의
3. 언어: **English 권장** (한글로 하면 터미널 경로에서 문제가 생깁니다)
4. 키보드·시간대
5. **와이파이 연결** ← 반드시 하세요. 다음 단계에 필요합니다
6. 계정 이름·비밀번호 → **팀이 공유할 것으로 정하고 메모** 📝
7. 우분투 바탕화면이 뜨면 완료

---

## 1-7. ⭐ SSH 켜기 — 가장 먼저 하세요

**이걸 하면 키보드·모니터를 다시 붙일 일이 없어집니다.** 맥에서 원격 접속해 작업하게 됩니다.

터미널을 열고 (`Ctrl` + `Alt` + `T`):

```bash
sudo apt update
sudo apt install -y openssh-server
sudo systemctl enable --now ssh
hostname -I
```

마지막 줄이 **Jetson의 IP 주소**입니다 (예: `192.168.0.15`). **꼭 메모하세요.**

이제 자기 노트북에서:

**🍎 맥 / 🪟 윈도우 (PowerShell) 공통**
```bash
ssh 계정이름@192.168.0.15
```

비밀번호를 넣고 접속되면 성공입니다. 앞으로는 이렇게 작업합니다.

---

## 1-8. ⚡ MAXN SUPER 켜기

기본은 **25W 제한**입니다. 이걸 안 켜면 "Super"의 성능을 못 씁니다.
**음성인식 속도가 눈에 띄게 달라집니다.**

1. 바탕화면 **위쪽 막대**의 전력 모드 클릭
2. **Power Mode** → **MAXN SUPER**

---

## 1-9. 확인

```bash
lsblk
```

**결과 읽는 법:**
```
NAME         SIZE TYPE MOUNTPOINT
mmcblk0     59.5G disk            ← microSD (부팅용)
├─mmcblk0p1 58.4G part /
nvme0n1    465.8G disk            ← SSD ✅ 이게 보이면 성공
```

SSD는 아직 포맷 전이라 **용량만 보이고 마운트는 안 된 게 정상**입니다.

```bash
# 펌웨어 추가 업데이트 예약 확인
sudo systemctl status nv-l4t-bootloader-config

# 모니터링 도구
sudo apt install -y python3-pip
sudo pip3 install jetson-stats
sudo reboot
# 재부팅 후
jtop
```

> 펌웨어 업데이트가 예약돼 있으면 **재부팅 중 전원을 절대 빼지 마세요.**

### 👉 다음: [SSD 설정 (11-ssd.md)](11-ssd.md)

`nvme0n1` 이 보였다면 이어서 진행하세요. 코드·모델·가상환경을 전부 SSD에 둡니다.

---

## ⚠️ 안 될 때

| 증상 | 해결 |
|---|---|
| 화면이 안 나옴 | DP→HDMI 젠더 확인. 모니터 입력을 HDMI로 전환 |
| 키보드가 안 먹힘 | **블루투스 키보드는 안 됩니다.** 유선으로 교체 |
| NVIDIA 로고 후 멈춤 | 펌웨어가 36.0 미만이거나 굽기 실패 |
| SSD가 `lsblk`에 없음 | Key M(긴 슬롯)에 꽂았는지, 끝까지 밀었는지, 나사 고정됐는지 |
| 부팅은 되는데 느림 | **MAXN SUPER**를 안 켠 것 |
| 나사가 안 돌아감 | 정밀 드라이버(PH00) 사용. 뭉갰으면 고무줄 끼우기 |

**30분 넘게 막히면 팀 대화방에 사진과 함께 올리세요.**

---

# 2부. 마이크 인식 — 함도유

⏱️ 15분

## 2-1. 인식 확인

마이크를 USB에 꽂고:

**🍎 맥**
```bash
system_profiler SPAudioDataType | grep -i -A 3 respeaker
```

**🪟 윈도우**
```powershell
Get-PnpDevice | Where-Object {$_.FriendlyName -match "ReSpeaker|SEEED"}
```

또는 **설정 → 시스템 → 소리 → 입력**에서 `ReSpeaker`가 보이면 됩니다.

## 2-2. 5초 녹음 테스트

**🍎 맥**
```bash
brew install sox
rec test.wav trim 0 5      # 5초간 말하기
play test.wav
```

**🪟 윈도우**

가장 쉬운 방법 — 시작 메뉴에서 **음성 녹음기** 실행 → 입력 장치를 ReSpeaker로 → 녹음 → 재생

터미널로 하려면:
```powershell
winget install ChrisBagwell.SoX
sox -d -t wav test.wav trim 0 5
sox test.wav -d
```

내 목소리가 들리면 **성공**입니다.

## 2-3. 방향(DOA) 읽기 — 도전 과제

우리 핵심 기능 "누가·어디서"의 기반입니다.

**🍎 맥 — 드라이버 불필요**
```bash
cd ~/Desktop
git clone https://github.com/respeaker/usb_4_mic_array.git
cd usb_4_mic_array
pip install pyusb
python tuning.py DOAANGLE
```

**🪟 윈도우 — 드라이버 먼저**

1. [zadig.akeo.ie](https://zadig.akeo.ie/)에서 **Zadig** 다운로드 (실행만, 설치 불필요)
2. **마이크를 꽂은 상태로** Zadig 실행
3. **Options → List All Devices** 체크
4. 목록에서 **ReSpeaker 4 Mic Array (Interface 3)** 선택

> ⚠️ **반드시 Interface 3**을 고르세요. 다른 걸 고르면 마이크가 먹통이 됩니다.

5. 드라이버를 **libusb-win32**로 → **Replace Driver**
6. 그다음:
```powershell
cd ~\Desktop
git clone https://github.com/respeaker/usb_4_mic_array.git
cd usb_4_mic_array
pip install pyusb
python tuning.py DOAANGLE
```

숫자(0~359)가 나오면 성공입니다. **손뼉을 방향 바꿔가며 쳐보세요.** 숫자가 따라 바뀝니다.

> 안 되면 오늘은 넘어가도 됩니다.

---

# 3부. 각자 "가장 작은 성공"

## 공통 — 시작하는 법

**🍎 맥**
```bash
cd ~/Desktop/soribom
git checkout guhyeon          # 본인 브랜치: guhyeon / doyu / jueon
source .venv/bin/activate
```

**🪟 윈도우**
```powershell
cd ~\Desktop\soribom
git checkout guhyeon
.venv\Scripts\activate
```

> 줄 맨 앞에 **`(.venv)`** 가 붙어야 합니다. 안 붙으면 다음으로 가지 마세요.

Claude Code를 켤 때:
```bash
claude
```

**첫 메시지 예시** (이름·파트만 바꿔서):
```
이 저장소의 CLAUDE.md 와 CONTEXT.local.md 를 읽고 시작해줘.

나는 강구현이고 음성인식(STT) 파트를 맡았어. 프로그래밍은 거의 처음이야.
오늘 목표는 docs/Day1.md 의 3부에 적힌 내 파트를 끝내는 거야.

CLAUDE.md 1장에 적힌 대로, 코드를 한꺼번에 주지 말고
한 걸음씩 설명하면서 같이 만들어줘.
```

---

## 🎙️ 강구현 — 음성인식 첫 성공

**목표:** 한국어 음성 파일 → 텍스트

### 1단계. 음성 파일 준비

- 🍎 **음성 메모** 앱 / 🪟 **음성 녹음기** 앱으로 5~10초 녹음
- 내용: *"안녕하세요. 오늘은 광합성의 과정을 배웁니다."*
- 파일을 `soribom` 폴더에 **`test.m4a`** 로 저장

### 2단계. 설치

```bash
pip install faster-whisper
```

ffmpeg가 없으면 오디오를 못 읽습니다. 확인:
```bash
ffmpeg -version
```
없으면 — 🍎 `brew install ffmpeg` / 🪟 `winget install Gyan.FFmpeg` **후 터미널 껐다 켜기**

### 3단계. 코드 작성

`stt_test.py` 파일을 만들고:

```python
from faster_whisper import WhisperModel

# small = 빠르지만 덜 정확 / medium = 느리지만 정확
# 첫 실행 때 모델이 자동으로 다운로드됩니다 (약 500MB)
model = WhisperModel("small", device="cpu", compute_type="int8")

segments, info = model.transcribe("test.m4a", language="ko")

print(f"감지된 언어: {info.language}")
for segment in segments:
    print(f"[{segment.start:.1f}s → {segment.end:.1f}s] {segment.text}")
```

### 4단계. 실행

```bash
python stt_test.py
```

**처음에는 모델 다운로드로 몇 분 걸립니다.** 그 뒤 내가 말한 문장이 글자로 나오면 **성공** 🎉

### 미리 알아둘 것

- 노트북에는 NVIDIA GPU가 없어 **CPU로 돌아갑니다.** 10초 음성에 10~30초 걸리는 게 정상
- 정확도가 아쉬우면 `"small"` → `"medium"` 으로 바꿔보세요 (더 느리지만 정확)
- `language="ko"` 를 빼면 영어로 잘못 인식할 수 있습니다

---

## 🖥️ 함도유 — 화면(UI) 첫 창

**목표:** 창이 뜨고 자막처럼 생긴 글자가 보이는 것

### 1단계. 설치

```bash
pip install PySide6
```

용량이 큽니다 (약 200MB). 몇 분 걸립니다.

### 2단계. 코드 작성

`ui_test.py` 파일을 만들고:

```python
import sys
from PySide6.QtWidgets import QApplication, QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

app = QApplication(sys.argv)

label = QLabel("오늘은 광합성의 과정을 배웁니다")
label.setAlignment(Qt.AlignCenter)

# 자막은 멀리서도 읽혀야 하므로 크게, 어두운 배경에 흰 글씨
label.setStyleSheet("background-color: #111111; color: white;")
label.setFont(QFont("", 36))
label.resize(900, 250)

label.show()

# 이 줄이 없으면 창이 떴다가 바로 꺼집니다
sys.exit(app.exec())
```

### 3단계. 실행

```bash
python ui_test.py
```

검은 창에 흰 글씨로 문장이 뜨면 **성공** 🎉

### 미리 알아둘 것

- 지금은 **가짜 글자를 박아둔 것**입니다. 그게 맞습니다. 나중에 구현이 만든 STT 결과를 여기 연결합니다
- 창이 떴다 바로 꺼지면 → `sys.exit(app.exec())` 를 빠뜨린 것
- 🪟 한글이 네모(□□□)로 보이면 폰트를 지정하세요:
  ```python
  label.setFont(QFont("Malgun Gothic", 36))
  ```

---

## 🔊 강주언 — TTS 첫 소리

### ⚠️ 중요한 변경 — Piper를 쓰지 않습니다

원래 계획은 Piper였는데, **Piper는 한국어를 지원하지 않습니다.**
[공식 저장소](https://github.com/rhasspy/piper/discussions/680)에서 확인된 사실이고, 한국어 음성 모델 자체가 없습니다.

**대신 MeloTTS를 씁니다.**

| | MeloTTS |
|---|---|
| 한국어 | ✅ 공식 지원 (KR) |
| 라이선스 | **MIT** (자유롭게 사용 가능) |
| 속도 | **CPU에서 실시간** — Jetson에 적합 |
| 만든 곳 | MIT 대학 + MyShell.ai |

> 이 변경은 **발표에서 오히려 좋은 소재**입니다.
> "처음엔 Piper를 쓰려 했으나 한국어 미지원을 확인하고 MeloTTS로 교체했다"는 건
> **직접 조사하고 판단했다는 증거**입니다. 개발 일지에 기록해 두세요.

**목표:** 글자를 넣으면 스피커에서 한국어로 들리는 것

### 1단계. 설치

```bash
pip install git+https://github.com/myshell-ai/MeloTTS.git
python -m unidic download
```

**10~15분 걸립니다.** 용량이 큽니다.

> 설치 중 에러가 나면 **바로 아래 "안 되면" 항목**으로 가세요. 오래 붙들지 마세요.

### 2단계. 코드 작성

`tts_test.py` 파일을 만들고:

```python
from melo.api import TTS

# 한국어 모델 로드 (첫 실행 시 자동 다운로드)
tts = TTS(language='KR', device='cpu')
speaker_ids = tts.hps.data.spk2id

text = "안녕하세요. 저는 소리봄입니다. 질문 있어요."

tts.tts_to_file(text, speaker_ids['KR'], 'output.wav', speed=1.0)
print("output.wav 생성 완료")
```

### 3단계. 실행하고 들어보기

```bash
python tts_test.py
```

**🍎 맥**
```bash
afplay output.wav
```

**🪟 윈도우**
```powershell
start output.wav
```

한국어 음성이 들리면 **성공** 🎉

### 안 되면 — espeak-ng 대체 (비상용)

MeloTTS 설치가 30분 넘게 씨름이 되면 **미련 없이 이걸로 넘어가세요.**
음질은 로봇 같지만 **한국어가 나오고 설치가 1분**입니다. 오늘은 "소리가 난다"만 확인하면 됩니다.

**🍎 맥**
```bash
brew install espeak-ng
espeak-ng -v ko "안녕하세요. 저는 소리봄입니다." -w output.wav
afplay output.wav
```

**🪟 윈도우**
```powershell
winget install espeak-ng
espeak-ng -v ko "안녕하세요. 저는 소리봄입니다." -w output.wav
start output.wav
```

> MeloTTS는 내일 다시 시도하면 됩니다. **오늘 막혀서 하루를 날리는 게 더 손해입니다.**

### 미리 알아둘 것

- 오늘은 **본인 노트북에서만** 하면 됩니다. Jetson·I2S 스피커 배선은 다음 주에
- 소리가 안 나면 시스템 설정에서 **출력 장치**를 확인하세요

---

# 4부. 마무리 — GitHub에 올리기

⏱️ 10분

**아무리 작아도 오늘 한 건 올리세요.** 이 기록이 "우리가 직접 만들었다"는 증거입니다.

```bash
git status          # 뭐가 바뀌었는지 눈으로 확인
git add -A
git commit -m "STT: faster-whisper로 한국어 음성 파일 전사 성공"
git push
```

첫 push에서 `no upstream branch` 에러가 나면 **한 번만**:
```bash
git push -u origin guhyeon      # 본인 브랜치
```

## 커밋 메시지

| ❌ | ✅ |
|---|---|
| `update` | `STT: faster-whisper로 한국어 음성 파일 전사 성공` |
| `수정` | `UI: PySide6 창에 자막 텍스트 표시` |
| `ㅇㅇ` | `TTS: MeloTTS 한국어 음성 출력 성공 (Piper는 한국어 미지원이라 교체)` |

---

# 오늘의 체크리스트

## 전원 공통
- [ ] 준비물 확인 (**유선 키보드**, 정밀 드라이버)
- [ ] 오늘 한 것 GitHub에 push
- [ ] 팀 대화방에 결과 공유 (스크린샷이면 더 좋음)

## 강주언
- [ ] **JetPack 6.2.1** SD Card Image 다운로드 (r39 아님!)
- [ ] balenaEtcher로 microSD에 굽기
- [ ] SSD를 **Key M 슬롯**에 장착 + 나사 고정 (전원 켜기 전)
- [ ] 펌웨어 **36.x 이상** 확인
- [ ] 선 연결 (DP→HDMI 젠더 포함)
- [ ] **초기 설정 완료 — 바탕화면 보기** ⭐
- [ ] **SSH 켜고 IP 주소 메모** ⭐ (이후 원격 작업)
- [ ] **MAXN SUPER** 전력 모드 켜기
- [ ] `lsblk`에 **`nvme0n1`** 확인
- [ ] [SSD 설정](11-ssd.md) 완료
- [ ] **MeloTTS로 한국어 음성 재생** (안 되면 espeak-ng)

## 함도유
- [ ] 마이크 인식 확인
- [ ] 5초 녹음 → 재생 성공
- [ ] (도전) `tuning.py DOAANGLE` 각도 읽기
- [ ] **PySide6 창에 자막 표시** ⭐

## 강구현
- [ ] 한국어 음성 파일 녹음 (`test.m4a`)
- [ ] faster-whisper 설치 + 모델 다운로드
- [ ] **음성 파일 → 한국어 텍스트 성공** ⭐

---

# 막히면

1. **에러 메시지를 그대로 복사**해서 Claude Code에 물어보세요
2. 안 되면 **팀 대화방에 에러 전문 + 스크린샷**
3. "안 돼요"만 쓰면 아무도 못 도와줍니다. **무엇을 하려다 어떤 메시지가 나왔는지** 쓰세요

**30분 이상 같은 곳에서 막히면 반드시 도움을 요청하세요.**
혼자 붙들고 있는 게 팀 전체에 가장 큰 손해입니다.

---

# 내일 미리보기

- 강구현: 파일이 아니라 **마이크로 실시간** 자막
- 함도유: 방향 각도를 화면에 **화살표로 표시**
- 강주언: Jetson에 **I2S 스피커 배선**

주말에 기반을 다져두면 다음 주가 훨씬 수월합니다. 
