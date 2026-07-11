# GitHub에 올리기

## 먼저: OneDrive 밖으로 옮기기

이 폴더는 OneDrive 안에 있습니다. OneDrive가 `.git` 폴더를 실시간 동기화하면
저장소가 깨질 수 있습니다(흔한 문제). **OneDrive 바깥으로 복사한 뒤** 시작하세요.

또한 이 폴더에 만들다 만 `.git` 폴더가 남아 있을 수 있으니 **먼저 지우세요.**

PowerShell:

```powershell
# 1) 남아있는 .git 제거
Remove-Item -Recurse -Force "C:\Users\nobin\OneDrive\Desktop\textbooks\08_대회준비\한국코드페어 2026\soribom\.git" -ErrorAction SilentlyContinue

# 2) OneDrive 밖으로 복사
New-Item -ItemType Directory -Force "C:\Users\nobin\projects" | Out-Null
Copy-Item -Recurse "C:\Users\nobin\OneDrive\Desktop\textbooks\08_대회준비\한국코드페어 2026\soribom" "C:\Users\nobin\projects\soribom"
cd C:\Users\nobin\projects\soribom
```

## 커밋 작성자를 학생 계정으로

대회 규정상 **학생 주도 개발**이어야 합니다. 커밋 author가 학생 계정이어야
"학생이 직접 만들었다"는 근거로 쓸 수 있습니다. 반대로 팀원이 아닌 사람의 이름으로
커밋이 쌓이면 제3자 개입으로 보일 수 있습니다.

```bash
git config user.name  "<학생 GitHub 사용자명>"
git config user.email "<학생 GitHub 이메일>"
```

## 초기 커밋

```bash
git init -b main
git add -A
git status     # ← 반드시 눈으로 확인 (아래 체크리스트)
git commit -m "소리봄: 초기 설계 문서, 하드웨어 구성, 소스 구조"
```

## GitHub 저장소 생성 후 push

GitHub에서 **학생 계정으로** 새 저장소 `soribom`을 만든 뒤:

```bash
git remote add origin https://github.com/<학생계정>/soribom.git
git push -u origin main
```

## 첫 커밋 전 체크리스트

`.gitignore`가 아래 항목을 이미 막고 있지만, `git status`로 한 번 더 확인하세요.

- [ ] 참가신청서 · 지도교사확인서 · 연구참가동의서가 **없는가**
- [ ] 실험 원자료(`experiments/data/*.csv`)가 **없는가**
- [ ] 운영요강 · 작품설명서 예시 · 역대 수상작 포스터 등 **주최 측 저작물이 없는가**
- [ ] 커밋 author가 **학생 계정**인가

## 앞으로

개발이 진행되면 `src/`의 각 모듈(TODO 표시)을 학생들이 채워 나가고,
커밋을 쌓아 나가면 됩니다. 커밋 히스토리 자체가 "우리가 5주 동안 이만큼 만들었다"는
가장 강력한 증거가 됩니다.
