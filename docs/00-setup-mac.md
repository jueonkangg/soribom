# 개발 환경 설치 가이드 (macOS)

프로그래밍이 처음이어도 그대로 따라 할 수 있게 썼습니다.
**순서대로** 하세요. 중간을 건너뛰면 뒤에서 반드시 막힙니다.

전체 30~50분 걸립니다. 인터넷 속도에 따라 다릅니다.

---

## 0단계 — 터미널이 뭔지 먼저 알기

### 터미널이란

평소 우리는 마우스로 아이콘을 클릭해서 컴퓨터를 씁니다.
**터미널은 마우스 대신 글자로 명령을 내리는 창**입니다.

개발자들이 굳이 이걸 쓰는 이유는, 마우스로는 못 하거나 너무 번거로운 일을
한 줄로 끝낼 수 있기 때문입니다. 처음엔 낯설지만 몇 번 하면 익숙해집니다.

### 터미널 여는 법

1. 키보드에서 **`⌘`(커맨드) + `스페이스바`** 를 동시에 누릅니다
2. 화면 가운데 검색창이 뜹니다
3. **`터미널`** 이라고 칩니다 (영어 키보드면 `terminal`)
4. **`엔터`** 를 누릅니다

흰색 또는 검은색 창이 하나 뜨고, 이런 글자가 보일 겁니다:

```
사용자이름@MacBook-Pro ~ %
```

맨 끝의 **`%`** 뒤에 커서가 깜빡이고 있습니다. **여기에 명령어를 칩니다.**

### 명령어 치는 법

이 가이드에 이렇게 회색 상자로 된 것들이 나옵니다:

```bash
python3 --version
```

이걸 터미널에 **그대로 치고 엔터**를 누르면 됩니다.
직접 타이핑해도 되고, **복사해서 붙여넣어도 됩니다** (`⌘ + V`).

> **오타 주의.** 컴퓨터는 글자 하나만 틀려도 못 알아듣습니다.
> 되도록 복사·붙여넣기를 쓰세요.

### 알아두면 편한 것 3가지

| 상황 | 방법 |
|---|---|
| 명령어가 계속 실행 중이고 멈추고 싶을 때 | `Control` + `C` |
| 화면이 지저분해졌을 때 | `clear` 치고 엔터 |
| 방금 쳤던 명령어를 다시 쓰고 싶을 때 | `↑` (위쪽 화살표) |

### ⚠️ 비밀번호를 칠 때 화면에 아무것도 안 나옵니다

설치 중에 이런 게 나올 수 있습니다:

```
Password:
```

여기에 **맥 로그인 비밀번호**를 칩니다. 그런데 **아무 글자도 안 보입니다.**
별표(`****`)조차 안 나옵니다.

**고장난 게 아닙니다.** 원래 그렇게 만들어져 있습니다(보안 때문).
그냥 안 보이는 채로 끝까지 치고 **엔터**를 누르면 됩니다.

---

## 1단계 — Homebrew 설치

### 이게 뭔가요

맥에는 앱스토어가 있죠. **Homebrew는 개발 도구 전용 앱스토어**라고 생각하면 됩니다.
앞으로 설치할 것들(Python, Git, ffmpeg…)을 전부 이걸로 한 줄씩 설치합니다.

**이걸 먼저 깔아야 나머지가 다 됩니다.**

### 설치

터미널에 아래를 통째로 복사해서 붙여넣고 엔터:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

그러면 이런 일이 벌어집니다:

1. `Press RETURN to continue` → **엔터**를 누릅니다
2. `Password:` → **맥 비밀번호**를 칩니다 (안 보이는 게 정상, 위 참고)
3. 글자가 쭉쭉 올라갑니다. **5~15분 걸립니다.** 기다리세요
   (`Xcode Command Line Tools`를 같이 설치하느라 오래 걸립니다)

### ⚠️ 여기가 제일 중요합니다 — 설치가 끝나면 화면을 읽으세요

설치가 끝나면 마지막에 이런 안내가 나옵니다:

```
==> Next steps:
- Run these commands in your terminal to add Homebrew to your PATH:
    echo >> /Users/본인이름/.zprofile
    echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> /Users/본인이름/.zprofile
    eval "$(/opt/homebrew/bin/brew shellenv)"
```

**여기 적힌 3줄을 그대로 복사해서 터미널에 붙여넣고 엔터를 눌러야 합니다.**

이걸 안 하면 **`brew: command not found`** 라는 에러가 계속 나옵니다.
(Homebrew는 설치됐는데, 맥이 그게 어디 있는지 모르는 상태입니다.)

화면에 나온 그대로 복사하세요. 사람마다 이름이 달라서 경로가 다릅니다.

### 확인

```bash
brew --version
```

`Homebrew 4.x.x` 같은 게 나오면 성공입니다.

---

## 2단계 — Python 3.11 설치

### 왜 3.11인가요

맥에는 Python이 이미 깔려 있긴 합니다. 하지만 **버전이 안 맞습니다.**

우리가 쓸 음성인식 라이브러리(faster-whisper)는 **최신 버전(3.13)에서 아직 제대로 안 돌아갑니다.**
그래서 일부러 **3.11**을 따로 깝니다.

```bash
brew install python@3.11
```

2~5분 걸립니다.

### 확인

```bash
python3.11 --version
```

`Python 3.11.x` 가 나오면 성공입니다.

> **`python` 이 아니라 `python3.11` 입니다.** 맥에서는 그냥 `python` 이라고 치면
> 옛날 버전이 잡히거나 아무것도 안 나옵니다. 헷갈리지 마세요.

---

## 3단계 — Git 설치

### 이게 뭔가요

**코드의 저장 기록을 남기는 도구**입니다.
게임의 세이브 파일 같은 겁니다. 뭔가 잘못돼도 예전으로 되돌릴 수 있고,
셋이서 같은 코드를 고쳐도 안 꼬이게 해줍니다.

```bash
brew install git
```

### 확인

```bash
git --version
```

---

## 4단계 — ffmpeg 설치

### 이게 뭔가요

**소리·영상 파일을 다루는 도구**입니다.
음성인식이 오디오를 읽으려면 반드시 필요합니다.

> **이걸 빼먹는 사람이 제일 많습니다.**
> 없으면 나중에 프로그램을 돌릴 때 첫 줄부터 에러가 납니다.
> 지금 깔아두세요.

```bash
brew install ffmpeg
```

용량이 커서 **5~10분** 걸립니다.

### 확인

```bash
ffmpeg -version
```

---

## 5단계 — VS Code 설치

### 이게 뭔가요

**코드를 쓰는 프로그램**입니다. 메모장의 개발자용 버전이라고 보면 됩니다.
글자에 색깔을 입혀주고, 오타를 잡아주고, 자동완성도 해줍니다.

1. [code.visualstudio.com](https://code.visualstudio.com/) 접속
2. **Download for macOS** 클릭
3. 받은 파일을 열고, **응용 프로그램(Applications) 폴더로 드래그**
4. 실행

### 확장 프로그램 3개 설치

VS Code를 켜고:

1. 왼쪽 세로 막대에서 **네모 4개 모양 아이콘** 클릭 (Extensions)
2. 검색창에 아래를 하나씩 치고, 각각 **Install** 클릭

| 검색어 | 만든 곳 |
|---|---|
| `Python` | Microsoft |
| `Pylance` | Microsoft |
| `Jupyter` | Microsoft |

---

## 6단계 — GitHub 계정 만들고 코드 받기

### 계정 만들기

1. [github.com](https://github.com) → **Sign up**
2. 이메일·비밀번호·아이디를 정합니다
3. **아이디와 이메일을 메모해 두세요.** 나중에 씁니다

계정을 만들었으면 팀에 알려주세요. 저장소에 초대해야 합니다.

### 코드 내려받기

터미널에서:

```bash
cd ~/Desktop
git clone https://github.com/jueonkangg/soribom.git
cd soribom
```

세 줄이 각각 이런 뜻입니다:

| 명령어 | 뜻 |
|---|---|
| `cd ~/Desktop` | 바탕화면으로 이동 |
| `git clone ...` | 팀 코드를 통째로 내려받기 |
| `cd soribom` | 방금 받은 폴더 안으로 들어가기 |

> `cd` 는 **c**hange **d**irectory, 즉 "폴더 이동"입니다.
> 터미널은 항상 "어느 폴더에 서 있는지"가 중요합니다.

바탕화면에 `soribom` 폴더가 생겼는지 눈으로 확인하세요.

### 내 브랜치로 이동

각자 자기 작업 공간(브랜치)이 따로 있습니다. **본인 것만** 실행하세요.

```bash
git checkout guhyeon      # 강구현
git checkout doyu         # 함도유
git checkout jueon        # 강주언
```

지금 어디 있는지 확인:

```bash
git branch
```

별표(`*`)가 붙은 게 지금 있는 브랜치입니다.

### 내 이름으로 기록되게 설정

```bash
git config user.name  "본인_GitHub_아이디"
git config user.email "본인_GitHub_이메일"
```

> **따옴표 안만 본인 것으로 바꾸세요.** 따옴표는 지우지 마세요.
>
> 이 설정을 안 하면 코드를 누가 썼는지 기록이 엉뚱하게 남습니다.
> 대회 규정상 **학생이 직접 만들었다는 기록**이 중요하니 꼭 하세요.

---

## 7단계 — Python 패키지 설치

### 가상환경이 뭔가요

프로젝트마다 필요한 라이브러리가 다릅니다.
전부 한 곳에 섞어 깔면 서로 충돌합니다.

**가상환경은 이 프로젝트 전용 상자를 하나 만드는 것**입니다.
여기 깔린 건 다른 프로젝트에 영향을 주지 않습니다.

### 만들기

**반드시 `soribom` 폴더 안에서** 실행하세요.
(터미널을 새로 켰다면 `cd ~/Desktop/soribom` 부터)

```bash
python3.11 -m venv .venv
```

### 켜기

```bash
source .venv/bin/activate
```

성공하면 터미널 맨 앞에 **`(.venv)`** 가 붙습니다:

```
(.venv) 사용자이름@MacBook-Pro soribom %
```

> **이게 안 보이면 가상환경이 안 켜진 겁니다.** 다음 단계로 가지 마세요.
>
> 그리고 **터미널을 새로 켤 때마다 이 명령어를 다시 쳐야 합니다.**
> 앞으로 작업 시작할 때마다:
> ```bash
> cd ~/Desktop/soribom
> source .venv/bin/activate
> ```

### 라이브러리 설치

```bash
pip install --upgrade pip
pip install -r src/requirements.txt
```

**10~20분 걸립니다.** 용량이 큽니다(2GB 정도). 와이파이 좋은 곳에서 하세요.
글자가 계속 올라가는 건 정상입니다. 끝날 때까지 창을 닫지 마세요.

### VS Code에도 알려주기

1. VS Code에서 `soribom` 폴더를 엽니다 (File → Open Folder)
2. 아무 `.py` 파일을 하나 엽니다
3. **오른쪽 아래**에 Python 버전이 표시됩니다. 그걸 클릭
4. 목록에서 **`.venv` 라고 적힌 것**을 고릅니다

---

## 8단계 — Zoom 설치

8월 1~2일 **심사가 ZOOM 화상으로 진행**됩니다.

1. [zoom.us/download](https://zoom.us/download) → Zoom Desktop Client 설치
2. **혼자서 회의를 하나 만들어 미리 테스트하세요:**
   - 마이크로 말했을 때 소리가 잡히는지
   - 카메라에 얼굴이 나오는지
   - **화면 공유가 되는지** (발표 때 PPT를 직접 띄워야 합니다)

> 운영사무국이 테스트 링크를 따로 주지 않습니다.
> **세팅이 안 돼서 생기는 불이익은 참가자 책임**이라고 공지에 명시돼 있습니다.
> 심사 당일에 처음 켜보면 늦습니다.

---

## 9단계 — 내 파트 추가 설치

### 음성인식(STT) 담당 — 강구현

추가 설치 없습니다.

다만 프로그램을 처음 돌릴 때 **AI 모델이 자동으로 다운로드**됩니다 (1~2GB).
시간이 걸리니 미리 한 번 돌려서 받아두세요.

### 소리 방향(DOA) + 화면 담당 — 함도유

맥은 **추가 드라이버가 필요 없습니다.** 마이크를 USB에 꽂으면 바로 인식됩니다.

방향 값을 읽는 도구는 이렇게 받습니다:

```bash
cd ~/Desktop
git clone https://github.com/respeaker/usb_4_mic_array.git
```

### TTS + 하드웨어 + 영상 담당 — 강주언

```bash
brew install --cask balenaetcher   # Jetson SD카드 굽기
brew install --cask obs            # 화면 녹화 (시연 영상의 핵심)
```

- **MeloTTS**: 한국어 TTS. 설치는 `pip install git+https://github.com/myshell-ai/MeloTTS.git`
  (Piper는 한국어를 지원하지 않아 교체했습니다)
- 영상 편집은 **DaVinci Resolve**(무료, 앱스토어) 또는 맥 기본 **iMovie**

---

## 최종 확인

터미널에 하나씩 치세요. **전부 버전이 나오면 완료**입니다.

```bash
brew --version
python3.11 --version
git --version
ffmpeg -version
```

그리고 `soribom` 폴더에서:

```bash
source .venv/bin/activate
pip list
```

`faster-whisper`, `melotts`, `sounddevice` 같은 이름들이 보이면 성공입니다.

---

## 자주 나는 에러

### `zsh: command not found: brew`

Homebrew 설치 후 **PATH 설정 3줄을 안 친 것**입니다.
1단계의 "여기가 제일 중요합니다"로 돌아가세요.

급하면 이걸 쳐보세요 (Apple Silicon 맥 기준):

```bash
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
source ~/.zprofile
```

### `zsh: command not found: python`

맥에서는 **`python`이 아니라 `python3.11`** 입니다.

### `No such file or directory`

**엉뚱한 폴더에 서 있는 것**입니다. 지금 어디 있는지 확인:

```bash
pwd
```

`/Users/이름/Desktop/soribom` 이 아니면:

```bash
cd ~/Desktop/soribom
```

### `pip: command not found` 또는 설치가 엉뚱한 곳에 됨

**가상환경이 안 켜져 있습니다.** 터미널 앞에 `(.venv)` 가 있는지 보세요.

```bash
source .venv/bin/activate
```

### ffmpeg 관련 에러가 뜬다

4단계를 건너뛴 것입니다.

```bash
brew install ffmpeg
```

설치 후 **터미널을 껐다 켜세요.**

---

## 막히면

**에러 메시지를 그대로 복사해서** 팀 대화방에 올리세요.
"안 돼요"만으로는 아무도 도와줄 수 없습니다.

에러 메시지 안에 답이 들어있는 경우가 대부분입니다.
겁먹지 말고 **일단 읽어보세요.** 영어라도 천천히 보면 무슨 말인지 감이 옵니다.
