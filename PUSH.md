# Git 사용 가이드 — 소리봄 팀

Git이 처음이어도 그대로 따라 할 수 있게 썼습니다.
**막히면 이 문서의 "자주 나는 에러"부터 보세요.** 대부분 거기에 답이 있습니다.

---

## 0. Git이 뭔지 30초 만에

**Git은 코드의 세이브 파일입니다.**

게임에서 보스전 전에 세이브를 하듯, 코드가 잘 돌아갈 때마다 "지금 상태"를 저장합니다.
나중에 뭘 망가뜨려도 마지막 세이브로 돌아갈 수 있습니다.

**GitHub는 그 세이브 파일을 올려두는 클라우드입니다.**
셋이서 같은 코드를 만드니, 서로의 작업을 주고받는 창구이기도 합니다.

세 가지 동작만 기억하면 됩니다.

| 명령어       | 뜻                     | 게임으로 치면         |
| ------------ | ---------------------- | --------------------- |
| `git add`    | 저장할 파일 고르기     | 세이브할 항목 선택    |
| `git commit` | 저장하기 (내 컴퓨터에) | 세이브                |
| `git push`   | 클라우드에 올리기      | 클라우드 업로드       |
| `git pull`   | 클라우드에서 받아오기  | 클라우드에서 불러오기 |

---

## 1. 브랜치 — 왜 각자 따로 쓰나

**브랜치는 "나만의 작업 공간"입니다.**

셋이 같은 공간에서 동시에 파일을 고치면 서로 덮어씁니다.
Git은 그걸 막으려고 push를 거부하는데, 그때 나오는 에러가 이겁니다:

```
! [rejected]  main -> main (fetch first)
```

**개발보다 이 에러 푸는 데 시간을 더 쓰게 됩니다.** 그래서 각자 자기 브랜치를 씁니다.

우리 저장소의 브랜치:

| 브랜치    | 주인    | 용도                                  |
| --------- | ------- | ------------------------------------- |
| `main`    | 팀 공용 | **동작이 확인된 코드만.** 여기가 정본 |
| `guhyeon` | 강구현  | 음성인식(STT) 작업 공간               |
| `doyu`    | 함도유  | 소리 방향(DOA) + 화면 작업 공간       |
| `jueon`   | 강주언  | TTS + 하드웨어 작업 공간              |

**자기 브랜치에서는 뭘 해도 됩니다.** 코드를 망가뜨려도, 실험하다 다 지워도
다른 사람에게 아무 피해가 없습니다. 그게 브랜치를 쓰는 이유입니다.

`main`에는 **동작하는 코드만** 올립니다.

---

## 2. 처음 한 번만 하는 설정

### 코드 받아오기

터미널을 열고 (`⌘ + 스페이스` → "터미널"):

```bash
cd ~/Desktop
git clone https://github.com/jueonkangg/soribom.git
cd soribom
```

바탕화면에 `soribom` 폴더가 생겼는지 눈으로 확인하세요.

### 내 브랜치로 이동

**본인 것만** 실행하세요.

```bash
git checkout guhyeon      # 강구현
git checkout doyu         # 함도유
git checkout jueon        # 강주언
```

지금 어느 브랜치에 있는지 확인:

```bash
git branch
```

`* guhyeon` 처럼 **별표(`*`)가 붙은 게 지금 있는 브랜치**입니다.

### 내 이름으로 기록되게 설정

```bash
git config user.name  "본인_GitHub_아이디"
git config user.email "본인_GitHub_이메일"
```

> **이건 반드시 해야 합니다.**
> 이 설정을 안 하면 코드를 누가 만들었는지 기록이 엉뚱하게 남습니다.
> 대회에서 **"학생이 직접 만들었다"는 근거**로 쓰이는 기록입니다.

제대로 됐는지 확인:

```bash
git config user.name
git config user.email
```

---

## 3. 매일 하는 일 — 이 순서를 외우세요

### 작업 시작할 때

```bash
cd ~/Desktop/soribom
git checkout <내브랜치>
source .venv/bin/activate
```

터미널 앞에 `(.venv)`가 붙으면 준비 끝입니다.

### 작업 끝났을 때 (하루 1~2번)

```bash
git status
git add -A
git commit -m "무엇을 했는지 한 줄로"
git push
```

`git push`에서 이런 게 뜨면:

```
fatal: The current branch guhyeon has no upstream branch.
```

**처음 한 번만** 이렇게 하면 됩니다:

```bash
git push -u origin guhyeon
```

다음부터는 그냥 `git push`로 충분합니다.

---

## 4. `git status` 읽는 법

`git status`는 **지금 상태를 알려주는 명령어**입니다. 뭘 하기 전에 항상 이걸 먼저 치세요.

```
On branch guhyeon                      ← 지금 guhyeon 브랜치에 있다
Changes not staged for commit:
        modified:   src/stt/transcriber.py     ← 고쳤지만 아직 add 안 함
Untracked files:
        test_audio.wav                          ← 새로 만든 파일
```

| 표시                                    | 뜻                                   |
| --------------------------------------- | ------------------------------------ |
| `modified`                              | 기존 파일을 고쳤다                   |
| `Untracked`                             | 새로 만든 파일이다 (아직 git이 모름) |
| `Changes to be committed`               | `add` 를 마쳐서 commit 준비가 됐다   |
| `nothing to commit, working tree clean` | 저장할 게 없다 (= 다 저장됨)         |

---

## 5. 커밋 메시지 쓰는 법

**"무엇을 했는지" 구체적으로** 씁니다. 나중에 우리 자신이 읽습니다.

| ❌ 나쁜 예 | ✅ 좋은 예                                               |
| ---------- | -------------------------------------------------------- |
| `update`   | `faster-whisper로 한국어 음성 파일 전사 성공`            |
| `수정`     | `자막 지연 시간 측정 코드 추가`                          |
| `ㅇㅇ`     | `마이크에서 방향(DOA) 각도 읽기 구현`                    |
| `fix bug`  | `VAD가 짧은 발화를 놓치던 문제 수정 (threshold 0.5→0.3)` |

**작게, 자주 커밋하세요.** 하루에 한 번씩만 해도 2주 뒤엔 우리가 무엇을 만들었는지가
한눈에 보이는 기록이 됩니다. 이 기록 자체가 **"우리가 직접 만들었다"는 증거**입니다.

---

## 6. 내 기능이 완성되면 — main에 합치기

내가 만든 게 **확실히 동작할 때만** 합칩니다. 2주 동안 서너 번이면 충분합니다.

```bash
# 1) 내 작업을 먼저 다 올린다
git add -A
git commit -m "STT 2-패스 구현 완료"
git push

# 2) main으로 가서 최신 상태를 받는다
git checkout main
git pull

# 3) 내 브랜치를 main에 합친다
git merge guhyeon

# 4) 합친 결과를 올린다
git push

# 5) 다시 내 브랜치로 돌아온다
git checkout guhyeon
```

### ⚠️ 2번의 `git pull`을 절대 건너뛰지 마세요

이걸 안 하면 **다른 사람이 올린 작업을 지울 수 있습니다.**
`main`으로 갔으면 무조건 `git pull` 부터. 습관으로 만드세요.

### 남이 main에 올린 걸 내 브랜치로 가져오기

다른 팀원이 main에 뭔가 합쳤다면, 내 브랜치에도 가져와야 합니다.

```bash
git checkout main
git pull
git checkout guhyeon
git merge main
```

**일주일에 한두 번은 해주세요.** 오래 미룰수록 나중에 합치기가 어려워집니다.

---

## 7. 충돌(conflict)이 났을 때

같은 파일의 **같은 줄**을 두 사람이 다르게 고치면 git이 판단을 못 하고 멈춥니다.

```
CONFLICT (content): Merge conflict in src/main.py
Automatic merge failed; fix conflicts and then commit the result.
```

**당황하지 마세요. 코드가 사라진 게 아닙니다.**

해당 파일을 VS Code로 열면 이렇게 보입니다:

```python
<<<<<<< HEAD
angle = doa.current()        ← main에 있던 코드
=======
angle = doa.get_angle()      ← 내가 고친 코드
>>>>>>> guhyeon
```

**할 일:** 둘 중 맞는 것을 고르고(또는 합치고), `<<<<<<<`, `=======`, `>>>>>>>` **세 줄을 모두 지웁니다.**

```python
angle = doa.get_angle()
```

그다음:

```bash
git add -A
git commit -m "merge 충돌 해결"
git push
```

> **혼자 판단하지 마세요.** 충돌이 났다는 건 **두 사람이 같은 곳을 건드렸다**는 뜻입니다.
> 상대에게 물어보고 정하세요. 잘못 지우면 남의 작업이 날아갑니다.

---

## 8. 자주 나는 에러

### `! [rejected] ... (fetch first)` / `(non-fast-forward)`

**GitHub에 내가 모르는 새 작업이 있습니다.** 받아온 뒤에 올리세요.

```bash
git pull
git push
```

### `Permission to jueonkangg/soribom.git denied to 다른아이디`

**컴퓨터에 다른 GitHub 계정이 저장되어 있습니다.**

- **macOS**: `키체인 접근` 앱 실행 → `github.com` 검색 → 해당 항목 **삭제** → 다시 push
- **Windows**: 제어판 → 자격 증명 관리자 → Windows 자격 증명 → `git:https://github.com` **제거** → 다시 push

### `fatal: not a git repository`

**엉뚱한 폴더에 있습니다.** 지금 어디 있는지 확인:

```bash
pwd
```

`soribom` 폴더가 아니면:

```bash
cd ~/Desktop/soribom
```

### `Your branch is behind 'origin/main' by N commits`

**GitHub가 나보다 최신입니다.** 그냥 받아오면 됩니다.

```bash
git pull
```

### 뭔가 크게 잘못한 것 같을 때

**아직 commit 안 한 변경을 전부 되돌리기** (마지막 저장 시점으로):

```bash
git checkout -- .
```

> ⚠️ 이건 **되돌릴 수 없습니다.** 커밋 안 한 작업이 다 사라집니다. 확실할 때만 쓰세요.

**그 외의 사고는 혼자 고치려 하지 말고 팀에 물어보세요.**
`git reset --hard`, `git push --force` 같은 건 **절대 혼자 쓰지 마세요.** 남의 작업이 날아갑니다.

---

## 9. 절대 올리면 안 되는 것

- **개인정보가 든 파일** — 이름·주소·전화번호가 들어간 서류
- **실험 참가자 데이터** (`.csv` 등) — 친구들에게 "연구 끝나면 폐기한다"고 약속했습니다
- **출처 없는 남의 코드** — 오픈소스는 써도 되지만 **어디서 가져왔는지 반드시 적어야** 합니다.
  출처를 안 밝히면 대회 규정상 부정행위입니다
- **AI 모델 파일** (`.onnx`, `.bin`, `.pt`) — 용량이 너무 큽니다. `.gitignore`가 막아줍니다

`.gitignore`가 대부분 자동으로 막아주지만, **커밋 전에 `git status`로 한 번 더 눈으로 확인**하세요.
한 번 올라간 개인정보는 지워도 기록에 남습니다.

---

## 10. 치트 시트

```bash
# ── 작업 시작 ──
cd ~/Desktop/soribom
git checkout guhyeon          # 내 브랜치로
source .venv/bin/activate     # 가상환경 켜기

# ── 작업 저장 ──
git status                    # 뭐가 바뀌었나 확인
git add -A                    # 전부 담기
git commit -m "한 일"          # 저장
git push                      # GitHub에 올리기

# ── main에 합치기 (기능 완성 시) ──
git checkout main
git pull                      # ← 절대 건너뛰지 말 것
git merge guhyeon
git push
git checkout guhyeon          # 내 브랜치로 복귀

# ── 상태 확인 ──
git branch                    # 지금 어느 브랜치? (별표 확인)
git log --oneline -5          # 최근 커밋 5개
pwd                           # 지금 어느 폴더?
```

---

## 막히면

**에러 메시지를 그대로 복사해서** 팀 대화방에 올리세요.
"안 돼요"만으로는 아무도 도와줄 수 없습니다.

Git 에러는 **메시지 안에 해결 방법이 들어 있는 경우가 대부분**입니다.
`hint:` 로 시작하는 줄이 보이면 거기에 답이 있습니다. 영어라도 천천히 읽어보세요.
