# 개발 환경 설치 가이드 (Windows)

프로그래밍이 처음이어도 그대로 따라 할 수 있게 썼습니다.
**순서대로** 하세요. 중간을 건너뛰면 뒤에서 반드시 막힙니다.

전체 30~50분 걸립니다. 인터넷 속도에 따라 다릅니다.

---

## 0단계 — PowerShell이 뭔지 먼저 알기

### PowerShell이란

평소 우리는 마우스로 아이콘을 클릭해서 컴퓨터를 씁니다.
**PowerShell은 마우스 대신 글자로 명령을 내리는 창**입니다. (맥의 "터미널"과 같은 것)

개발자들이 굳이 이걸 쓰는 이유는, 마우스로는 못 하거나 너무 번거로운 일을
한 줄로 끝낼 수 있기 때문입니다. 처음엔 낯설지만 몇 번 하면 익숙해집니다.

### PowerShell 여는 법

**방법 1 (가장 쉬움)**
1. 키보드에서 **`Win` + `X`** 를 동시에 누릅니다
2. 메뉴에서 **터미널** 또는 **Windows PowerShell** 클릭

**방법 2**
1. **`Win`** 키를 누릅니다
2. **`powershell`** 이라고 칩니다
3. **엔터**

파란색 또는 검은색 창이 뜨고 이런 글자가 보일 겁니다:

```
PS C:\Users\사용자이름>
```

**`>`** 뒤에 커서가 깜빡입니다. **여기에 명령어를 칩니다.**

### 관리자 권한으로 여는 법

일부 설치는 **관리자 권한**이 필요합니다. 그때는:

1. **`Win` + `X`**
2. **터미널(관리자)** 또는 **Windows PowerShell(관리자)** 클릭
3. "이 앱이 장치를 변경하도록 허용하시겠어요?" → **예**

창 제목에 **"관리자"**라고 뜨면 맞게 연 것입니다.

### 명령어 치는 법

이 가이드에 이렇게 회색 상자로 된 것들이 나옵니다:

```powershell
python --version
```

이걸 PowerShell에 **그대로 치고 엔터**를 누르면 됩니다.
직접 타이핑해도 되고, **복사해서 붙여넣어도 됩니다** (`Ctrl + V` 또는 마우스 오른쪽 클릭).

> **오타 주의.** 컴퓨터는 글자 하나만 틀려도 못 알아듣습니다.
> 되도록 복사·붙여넣기를 쓰세요.

### 알아두면 편한 것 3가지

| 상황 | 방법 |
|---|---|
| 명령어가 계속 실행 중이고 멈추고 싶을 때 | `Ctrl` + `C` |
| 화면이 지저분해졌을 때 | `cls` 치고 엔터 |
| 방금 쳤던 명령어를 다시 쓰고 싶을 때 | `↑` (위쪽 화살표) |

---

## 1단계 — winget 확인

### 이게 뭔가요

**winget은 윈도우에 내장된 프로그램 설치 도구**입니다.
앞으로 설치할 것들을 한 줄씩 자동으로 깔아줍니다.

Windows 10 최신 버전 이상이면 **이미 들어 있습니다.**

```powershell
winget --version
```

`v1.x.x` 같은 게 나오면 준비 완료입니다.

> **`winget을 인식할 수 없습니다`** 라고 나오면:
> Microsoft Store에서 **앱 설치 관리자**(App Installer)를 검색해 설치하세요.
> 그 뒤 PowerShell을 껐다 켜면 됩니다.

---

## 2단계 — Python 3.11 설치

### 왜 3.11인가요

우리가 쓸 음성인식 라이브러리(faster-whisper)는
**최신 버전(3.13)에서 아직 제대로 안 돌아갑니다.**
그래서 일부러 **3.11**을 깝니다.

```powershell
winget install Python.Python.3.11
```

설치가 끝나면 **PowerShell을 껐다가 다시 여세요.** (중요)

### ⚠️ 직접 설치할 때 주의할 것

winget이 안 되어 [python.org](https://www.python.org/downloads/release/python-3119/)에서
직접 받아 설치한다면, 설치 첫 화면에서

**☑ Add python.exe to PATH**

이 체크박스를 **반드시 켜세요.**

이걸 놓치면 PowerShell에서 `python`을 인식하지 못해서,
"왜 안 되지" 하며 한 시간을 날리게 됩니다. 가장 흔한 실수입니다.

### 확인

```powershell
python --version
```

`Python 3.11.x` 가 나오면 성공입니다.

> 다른 버전이 나온다면 여러 개가 깔려 있는 것입니다. 이렇게 확인하세요:
> ```powershell
> py -0
> ```
> 목록에 `3.11`이 있으면, 앞으로 `python` 대신 **`py -3.11`** 을 쓰면 됩니다.

---

## 3단계 — Git 설치

### 이게 뭔가요

**코드의 저장 기록을 남기는 도구**입니다.
게임의 세이브 파일 같은 겁니다. 뭔가 잘못돼도 예전으로 되돌릴 수 있고,
셋이서 같은 코드를 고쳐도 안 꼬이게 해줍니다.

```powershell
winget install Git.Git
```

설치 후 **PowerShell을 껐다 켜세요.**

### 확인

```powershell
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

```powershell
winget install Gyan.FFmpeg
```

**설치 후 반드시 PowerShell을 껐다 켜야 합니다.** 안 그러면 인식이 안 됩니다.

### 확인

```powershell
ffmpeg -version
```

---

## 5단계 — VS Code 설치

### 이게 뭔가요

**코드를 쓰는 프로그램**입니다. 메모장의 개발자용 버전이라고 보면 됩니다.
글자에 색깔을 입혀주고, 오타를 잡아주고, 자동완성도 해줍니다.

```powershell
winget install Microsoft.VisualStudioCode
```

또는 [code.visualstudio.com](https://code.visualstudio.com/)에서 직접 받아 설치.

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

### ⚠️ 코드를 받을 위치 — OneDrive를 피하세요

**OneDrive가 동기화하는 폴더(바탕화면, 문서 등)에 코드를 두면 Git이 깨집니다.**
실제로 이 프로젝트에서 두 번 깨졌습니다.

그래서 **OneDrive 바깥에** 폴더를 새로 만들어 씁니다.

```powershell
mkdir C:\Users\$env:USERNAME\projects
cd C:\Users\$env:USERNAME\projects
```

> 내 바탕화면이 OneDrive 안인지 확인하려면:
> ```powershell
> [Environment]::GetFolderPath('Desktop')
> ```
> 결과에 `OneDrive`가 들어 있으면 동기화되는 폴더입니다.

### 코드 내려받기

```powershell
git clone https://github.com/jueonkangg/soribom.git
cd soribom
```

두 줄이 각각 이런 뜻입니다:

| 명령어 | 뜻 |
|---|---|
| `git clone ...` | 팀 코드를 통째로 내려받기 |
| `cd soribom` | 방금 받은 폴더 안으로 들어가기 |

> `cd` 는 **c**hange **d**irectory, 즉 "폴더 이동"입니다.
> PowerShell은 항상 "어느 폴더에 서 있는지"가 중요합니다.

### 내 브랜치로 이동

각자 자기 작업 공간(브랜치)이 따로 있습니다. **본인 것만** 실행하세요.

```powershell
git checkout guhyeon      # 강구현
git checkout doyu         # 함도유
git checkout jueon        # 강주언
```

지금 어디 있는지 확인:

```powershell
git branch
```

별표(`*`)가 붙은 게 지금 있는 브랜치입니다.

### 내 이름으로 기록되게 설정

```powershell
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

```powershell
python -m venv .venv
```

> Python이 여러 개 깔려 있다면: `py -3.11 -m venv .venv`

### 켜기

```powershell
.venv\Scripts\activate
```

성공하면 줄 맨 앞에 **`(.venv)`** 가 붙습니다:

```
(.venv) PS C:\Users\사용자이름\projects\soribom>
```

> **이게 안 보이면 가상환경이 안 켜진 겁니다.** 다음 단계로 가지 마세요.
>
> 그리고 **PowerShell을 새로 켤 때마다 이 명령어를 다시 쳐야 합니다.**

### ⚠️ "스크립트를 실행할 수 없습니다" 에러가 뜬다면

윈도우는 기본적으로 스크립트 실행을 막아둡니다. 이렇게 한 번 풀어주세요:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

`Y` 를 눌러 확인한 뒤, 다시 `.venv\Scripts\activate` 를 실행하세요.

### 라이브러리 설치

```powershell
pip install --upgrade pip
pip install -r src\requirements.txt
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

```powershell
winget install Zoom.Zoom
```

설치 후 **혼자서 회의를 하나 만들어 미리 테스트하세요:**
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

**⚠️ 윈도우는 드라이버 설치가 필요합니다.** (맥·리눅스는 불필요)

마이크에서 방향 값을 읽으려면 `libusb-win32` 드라이버를 넣어야 합니다.

1. [zadig.akeo.ie](https://zadig.akeo.ie/) 에서 **Zadig** 다운로드 (설치 불필요, 실행만)
2. **마이크를 USB에 꽂은 상태로** Zadig 실행
3. 상단 메뉴 **Options → List All Devices** 체크
4. 목록에서 **ReSpeaker 4 Mic Array (Interface 3)** 선택

> ⚠️ **반드시 Interface 3을 고르세요.**
> 다른 걸 고르면 마이크가 소리를 못 내게 됩니다.

5. 오른쪽 드라이버를 **libusb-win32** 로 맞추고 **Replace Driver** 클릭

그다음 방향 읽기 도구를 받습니다:

```powershell
cd C:\Users\$env:USERNAME\projects
git clone https://github.com/respeaker/usb_4_mic_array.git
cd usb_4_mic_array
pip install pyusb
python tuning.py DOAANGLE
```

숫자(0~359)가 나오면 성공입니다.

### TTS + 하드웨어 + 영상 담당 — 강주언

```powershell
winget install Balena.Etcher          # Jetson SD카드 굽기
winget install OBSProject.OBSStudio   # 화면 녹화 (시연 영상의 핵심)
```

- **MeloTTS**: 한국어 TTS. 설치는 `pip install git+https://github.com/myshell-ai/MeloTTS.git`
  (Piper는 한국어를 지원하지 않아 교체했습니다)
- 영상 편집은 **Clipchamp**(윈도우 기본) 또는 **DaVinci Resolve**(무료)

---

## 최종 확인

PowerShell에 하나씩 치세요. **전부 버전이 나오면 완료**입니다.

```powershell
python --version
git --version
ffmpeg -version
```

그리고 `soribom` 폴더에서:

```powershell
.venv\Scripts\activate
pip list
```

`faster-whisper`, `melotts`, `sounddevice` 같은 이름들이 보이면 성공입니다.

---

## 자주 나는 에러

### `'python'은(는) 내부 또는 외부 명령... 이(가) 아닙니다`

Python 설치 시 **"Add python.exe to PATH" 체크를 놓친 것**입니다.
Python을 다시 설치하면서 그 체크박스를 켜세요.

또는 `py -3.11` 로 대신 쓸 수 있습니다.

### `이 시스템에서 스크립트를 실행할 수 없으므로...`

7단계의 실행 정책 설정을 하세요:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

### `'git'은(는) 내부 또는 외부 명령...`

Git 설치 후 **PowerShell을 껐다 켜지 않은 것**입니다. 창을 닫고 새로 여세요.

### ffmpeg 관련 에러가 뜬다

4단계를 건너뛰었거나, 설치 후 PowerShell을 안 껐다 켠 것입니다.

```powershell
winget install Gyan.FFmpeg
```

그다음 **PowerShell을 반드시 껐다 켜세요.**

### `fatal: not a git repository`

**엉뚱한 폴더에 서 있는 것**입니다. 지금 어디 있는지 확인:

```powershell
pwd
```

`...\projects\soribom` 이 아니면 그 폴더로 이동하세요.

### `remote: Permission to ... denied to 다른아이디`

컴퓨터에 **다른 GitHub 계정이 저장되어 있습니다.**

**제어판 → 자격 증명 관리자 → Windows 자격 증명** 에서
`git:https://github.com` 항목을 **제거**한 뒤 다시 시도하세요.

### 한글이 네모(□□□)로 깨져 보인다

PowerShell 창에서:

```powershell
chcp 65001
```

파일을 만들 때는 항상 **UTF-8**로 저장하세요.

---

## 막히면

**에러 메시지를 그대로 복사해서** 팀 대화방에 올리세요.
"안 돼요"만으로는 아무도 도와줄 수 없습니다.

에러 메시지 안에 답이 들어있는 경우가 대부분입니다.
겁먹지 말고 **일단 읽어보세요.** 영어라도 천천히 보면 무슨 말인지 감이 옵니다.
