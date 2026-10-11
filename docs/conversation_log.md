# 소리봄 통합 개발 현황·문제 수정·대화 로그

이 파일은 팀이 다음 세션에서도 개발 현황과 결정의 이유를 이어볼 수 있도록 관리한다.
**최신 현황은 맨 위에 갱신하고, 중요한 작업·사용자 확인은 아래 로그에 추가한다.**
7월 Claude 기록은 당시 상태를 보존한다. 10월 Codex 기록은 실제 코드·커밋·사용자 보고를 근거로 한다.


## 최신 현황 — 2026-10-12

**공유 완료:** `521776d`를 origin/jueon에 푸시하고 main에 fast-forward 병합·푸시했다.
원격 main/jueon이 같은 커밋인 것을 직접 조회해 확인했다. 작성자는 강주언이다.
이후 doyu에서 방향 시점 개선을 구현하고 사용자 실기기 정상 동작 확인을 받았다.
방향 개선은 `38279b6`으로 origin/doyu와 origin/main에 공유 완료했고 원격 조회로 확인했다.
자막 필터 개선 `98d9856`도 origin/guhyeon과 origin/main에 공유하고 원격 조회로 확인했다.
guhyeon에서 이름 알림 대상·부분 일치와 hotwords 잘림을 수정했다.
2026-10-12 사용자 요청으로 개선 코드·테스트·발견 기록을 함께 커밋·푸시하고 main에 통합한다.
사용자가 00:44:39 화면과 함께 호칭·과학 문장에서 이름 인식이 해결됐다고 확인했다.
이름 알림 표시·무음 오탐·다른 과목·장시간 결과는 별도 확인 대상이며 다른 팀원의 stash는 보존했다.
이 현황은 로컬 코드·Git 이력·이 대화의 사용자 확인을 대조해 갱신했다.

### 현재 구현과 확정된 선택

| 영역 | 구현·결정 | 근거 |
|---|---|---|
| 목적 | 청각장애·난청 학생의 수업 참여를 지원하는 오프라인 자막·화자 방향·타이핑 말하기 | [프로젝트 안내](../CLAUDE.md) |
| 자막 | faster-whisper small / CUDA / int8 단일 패스. medium 2-패스는 메모리·비교 측정으로 폐기 | [STT](../src/stt/transcriber.py), [설정](../src/config.yaml) |
| 수음·VAD | ReSpeaker 6채널 중 ch0 사용, 16kHz. faster-whisper 내장 Silero ONNX 사용 | [수음](../src/audio/capture.py), [VAD](../src/audio/vad.py) |
| 인식 보강 | 이름·호칭 우선, 과목/공통 교대·실제 토큰 제한 내 선택. hotwords 잘림 수정 후 사용자 이름 인식 해결 확인 | [용어 사전](../src/stt/vocab.py), [STT](../src/stt/transcriber.py), [발견 기록](19-name-alerts.md) |
| 방향 | 주기적 원본 표본을 VAD 음성 구간과 연결. 주된 원형 방향 집계·표본 부족/상충 시 미확정. front_offset=90; 신원 식별은 아님 | [DOA](../src/audio/doa.py), [연결 관리](../src/audio/recovery.py), [방향 안내](17-direction-timing.md) |
| 말하기 | sherpa-onnx + Supertonic v3 int8, CUDA 사용. GPU 초기화 실패 시 CPU 대체. 중복 실행 방지·출력 오류 안내·실패 시 입력 보존·200자 제한 | [TTS](../src/tts/speaker.py), [화면](../src/ui/app.py) |
| 출력 | I2S 제작 시도 후 BT 스피커로 전환. 현재 시스템 기본 출력(output_device=null) | [설정](../src/config.yaml), 아래 7/25 기록 |
| UI | 자막·방향·이름 호명 알림·말하기·과목·기록·이메일·연결 상태. 밝은/어두운 테마, 대화 공백 구분 | [화면](../src/ui/app.py) |
| 기록 | 전체 전사 보기·공백/연속 중복 정리·30초 자동/종료 저장. 실행별 고유 파일·임시 파일 교체·저장 상태 안내; 요약은 아님 | [기록](../src/summary/notes.py) |
| 이메일 | 현재 기록 미리보기, 단일 수신 주소, 동일한 한글 본문/TXT 첨부, Gmail SMTP/TLS. 사용자 전송 시에만 인터넷 사용 | [이메일](../src/summary/email_sender.py), [설정·검증](15-note-email.md) |
| 연결 복구 | 마이크와 방향 워커 각 하나, 녹음 프로세스 최대 하나. 모델을 재로딩하지 않고 장치만 재연결 | [연결 관리](../src/audio/recovery.py), [진입점](../src/main.py) |
| 자원 제한 | 자동 재시도 5초, 오디오 수신 중단 감지 2초, 연결 대기 5초, USB 요청 300ms, 큐 100블록, 발화 약 30초 | [설정](../src/config.yaml) |
| 미구현 | 비음성 종소리·경보 분류, 수업 음성의 이어버드/보청기 전달, 화자 신원 식별·화자별 노트 | [이벤트](../src/events/sound_events.py), [진입점](../src/main.py) |

### 최근 변경과 해결한 문제

| 코드 커밋 | 작업 | 해결·변경 내용 |
|---|---|---|
| `3051b0b` | 밝은/어두운 테마·대화 공백 | 교실 조명에 맞춰 테마 전환, 30초 이상 대화 공백을 빈 줄로 구분 |
| `e8a4af5` | 경제 용어 사전 보강 | 재정정책·통화정책 관련 hotwords 추가 |
| `0593e9a` | 노트 이메일 발송 | 미리보기·전송 워커·주소/계정/권한 검증·중복 전송 및 전송 중 닫기 방지. 설정 실패 원인 안내 세분화 |
| `7922632` | 마이크 복구·상태 안내 | 장치 부재로 앱 시작이 막히거나 방향 USB 오류로 자막이 중단되는 경로 분리. 기본 마이크 자동 대체 제거 |
| `7922632` | 재연결 자원 정리 | 종료 확인 후 녹음 프로세스 교체. 강제 종료에도 멈추지 않는 제한된 파이프 전송·종료 신호 사용 |
| `7922632` | 버퍼·오래된 결과 관리 | 유한 큐·발화 길이 제한, 연결 세대별 VAD 초기화·끊기기 전 진행 중 전사 결과 차단 |
| `7922632` | 화면·시작/종료 | 모델 준비 중에도 화면 표시, 연결 상태·자동/수동 재연결, 방향 실패 시 화살표 제거, 종료 후 뒤늦은 녹음 시작 방지 |
| `521776d` | 기록 보존·말하기 안정성 | 주기적 안전 저장·파일명 충돌 방지·실패 안내, TTS 단일 실행·출력 스트림 정리·입력 보존·길이 제한·요일·과목 표시 |
| 이번 변경 | 방향 시점 연결 | 수음 시각 전달·발화 중 방향 표본 선택·자원 제한·표본 부족/상충 미확정 |

`7922632`는 `0593e9a`를 포함하며, 2026-10-11 사용자 요청으로 main에 fast-forward 병합·푸시했다.

### 검증 결과와 확인 범위

- 최근 doyu 자동 테스트 **55개 통과**: 이전 main 44개 + 방향 시점 10개·통합 경로 1개. 이번 실행은 9.185초.
- 별도 모의 기록 프로세스를 강제 종료한 뒤 자동 저장 TXT가 보존되는지 확인했다. 저장 중 자막 추가,
  저장 오류 시 이전 파일 유지·임시 파일 정리, 중복 말하기 요청 100회 차단·출력 오류 후 재시도도 통과했다.
- 밝은/어두운 테마의 1920×1080 화면을 렌더링해 저장·말하기 오류 안내와 입력칸 표시를 확인했다.
  사용자가 기록·말하기 개선을 테스트했다고 보고했고, BT 재연결 후 실제 Speaker.say 재생도 완료했다.
  실제 GPU·USB·BT를 함께 사용하는 장시간 수업 시험의 조건·결과는 아직 기록되지 않았다.
- 모의 녹음 프로세스 **4회 강제 종료·재연결**에서 이전 프로세스 정리와 메모리 증가 여부를 확인했다.
  이번 실행에서 부모 RSS는 209,976 KiB로 일정했고 자식 RSS는 약 158,244~160,284 KiB였다.
  실제 GPU 모델·USB 드라이버를 포함한 장시간 메모리 검증은 아니다.
- 300ms 방향 읽기 지연 중에도 음성 수신이 지속되는 자동 테스트가 통과했다.
- 사용자 보고: 마이크 연결 복구 작업을 테스트했고 **정상 작동**하여 커밋·푸시를 요청했다.
  개별 장치·조건·시험 시간의 상세 기록은 받지 않았으므로 장시간 검증으로 확대 해석하지 않는다.
- 이메일 UI·로컬 설정 형식/권한/Git 제외는 확인됐다. **실제 Gmail 인증·본문/TXT 수신 확인은 미기록**이다.
- 과거 CER·전사/합성 시간·DOA 수치는 [측정 기록](phase_c_measurements.md)에 있다.
  제한된 조건의 결과이며 전체 체감 지연·모든 교실 환경의 정확도를 뜻하지 않는다.

### 이전에 지적한 14가지 문제의 현재 상태

'코드'는 파일에서 확인한 동작, '기록'은 저장된 실험·개발 기록, '판단'은 그 근거에 대한 검토 의견이다.

| # | 문제·현재 상태 | 출처 구분과 근거 | 남은 해결 방향 |
|---|---|---|---|
| 1 | 장치 부재/방향 오류가 앱·자막을 중단: **복구 처리 구현, 사용자 정상 동작 확인** | 코드: [연결 관리](../src/audio/recovery.py), [진입점](../src/main.py); 사용자 보고 | 실제 장치·조건을 적은 장시간 시험 |
| 2 | TTS 연속 입력 중복: **단일 실행·버튼 제한 구현, 자동 테스트 통과** | 코드: [화면의 _on_enter](../src/ui/app.py), [Speaker.say](../src/tts/speaker.py) | 실기기에서 자막과 동시 사용·연속 입력 확인 |
| 3 | 종료 시만 저장·파일명 충돌: **30초 자동 저장·고유 파일·안전 교체 구현, 자동 테스트 통과** | 코드: [notes.save](../src/summary/notes.py) | 실수업 저장 확인. 마지막 저장 이후 강제 종료 구간 유실은 남음 |
| 4 | 무제한 큐·긴 발화 메모리 증가: **제한 적용** | 코드: [AudioBuffer](../src/audio/recovery.py), [VAD](../src/audio/vad.py) | 과부하 시 누락을 실기기에서 확인·한도 조정 |
| 5 | **정상 용어 나열 필터 수정·hotwords 잘림 수정·사용자 이름 인식 해결 확인**. 빠른 자연발화·사전 과편향은 남음 | 기록: [CER](phase_c_measurements.md); 코드: [STT 필터](../src/stt/transcriber.py); 사용자 확인: [발견 기록](19-name-alerts.md) | 참가자 발화·무음·다른 이름/과목 회귀 검증 |
| 6 | 발화 뒤 다음 화자 방향 연결: **발화 시각·표본 연결 구현, doyu 자동 테스트 통과·사용자 실기기 정상 동작 확인** | 코드: [caption_lane](../src/main.py), [연결 관리](../src/audio/recovery.py); 사용자 보고·스크린샷: [방향 안내](17-direction-timing.md) | 위치별 각도 오차·교대 발화별 정량 결과·장시간 시험 |
| 7 | DOA 오차 원인 설명 불일치·LED 위치 보정의 평가 편향 가능성: **재검증 필요** | 기록: 아래 7/25 로그(케이스)와 [측정 문서](phase_c_measurements.md)(위치)의 설명이 다름; 편향은 판단 | 독립적인 바닥 각도 기준으로 반복 측정 |
| 8 | 전사/합성 시간과 전체 지연 혼용: **문서 설명 정정**, 전체 지연 측정은 남음 | 코드: [phase_c_eval](../phase_c_eval.py), [TTS](../src/tts/speaker.py); 기록: [측정 문서](phase_c_measurements.md) | 말 끝→자막, Enter→실제 소리 시작까지 측정 |
| 9 | 한 수업 동안 동시 사용·재연결 안정성: **미검증** | 기록: [스모크](../integration_smoketest.py)는 동시 상주·순차 추론; 판단: 장시간 보장 불가 | 약 50분 실사용·메모리·누락 기록 |
| 10 | 영어 수업 모드 통합: **미반영** | 코드: 현재 config.language=ko; 이전 검토와 doyu stash 기록 | 담당자와 stash를 복원·통합하고 영어 발화 검증. stash 자동 적용 금지 |
| 11 | 환경/설치 설명과 실제 환경 차이: **현재 안내 정정, 설치 재현 정리는 남음** | 환경: Python 3.10.12; 코드: [requirements](../src/requirements.txt), ONNX VAD; 과거 문서는 3.11 | CUDA 빌드·분석 의존성·불필요한 torch 항목 정리 후 설치 검증 |
| 12 | 2-패스·MeloTTS·스텁 등 오래된 문서: **이번 갱신으로 주요 안내 정정** | 파일: README·CLAUDE·시스템 설계·이 로그 | 초기 도식·7월 계획·제출물은 역사 자료로 구분, 재사용 때 최신화 |
| 13 | 출력 오류 처리: **오류 안내·입력 보존·스트림 정리·재시도 구현**. BT 자동 연결·OS 기본 출력 전환 감지는 남음 | 코드: [Speaker.say](../src/tts/speaker.py), [화면](../src/ui/app.py), output_device=null | 실기기 오류·재시도 확인, OS 출력 선택 확인 |
| 14 | 공유 상태: **기록·말하기 개선 `521776d` 원격 main/jueon 통합 완료; 방향 개선도 사용자 요청으로 공유 진행** | Git: 원격 조회 확인; doyu stash 보존 | 방향 개선의 커밋·푸시·main 통합 결과를 Git 이력에서 확인. 제출물 공개 범위는 팀 판단 필요 |

기록 자동 저장과 TTS 중복 실행 방지는 구현·자동 검증을 마쳤다. 방향 시점 개선도 사용자에게
실기기 정상 동작 확인을 받았다. 실제 Gmail 수신·방향 정량 측정·장시간 실사용은 별도 확인 항목으로 유지한다.
구현 범위·팀 테스트 순서는 [기록·말하기 안정성 안내](16-recording-speech-stability.md)에 있다.

### 문서를 읽는 순서

1. 이 최신 현황 → [README](../README.md) → [CLAUDE](../CLAUDE.md).
2. 처리 흐름은 [시스템 설계](02-system-design.md), 실제 출력 구성은 [하드웨어](03-hardware.md).
3. 지표의 조건·한계는 [측정 기록](phase_c_measurements.md), 이메일 확인 절차는 [이메일 문서](15-note-email.md).
4. 아래 7월 대화·일정·체크리스트는 당시 개발 경위로 읽는다. 현재 완료 여부로 사용하지 않는다.

---

## 과거 인수인계 — 2026-07-23 당시 상태 (현재 상태는 위 최신 현황 참고)

**현재 상태:** 세 기능(①자막 ②방향/UI ⑥말하기) 코드 완성 + **main 병합 완료** (main HEAD = `c8a289f`).
통합 스모크 테스트 **통과** — STT(GPU)+TTS(GPU) 동시 상주해도 OOM 없음(여유 3GB).

**사용자가 하려던 것:** 세션 종료 → **스피커 연결** → 재시작 → 아래 Phase B 부터.

**다음 할 일 = Phase B: `main.py` 라이브 실행 (스피커 연결 후):**
1. 재생 장치 확인 → `src/config.yaml` 의 `tts.output_device` 에 지정:
   `.venv/bin/python -c "import sounddevice as sd; print(sd.query_devices())"` (또는 `aplay -l`).
   I2S(MAX98357A) 아직이면 ReSpeaker 3.5mm 잭이나 USB 스피커로.
2. 데모 전 **브라우저 등 메모리 큰 프로그램 다 끄기** (Jetson 8GB 공유메모리 — 안 그러면 GPU OOM).
3. 라이브: `cd /data2/code/soribom && .venv/bin/python src/main.py`
   확인 → ① 말하면 자막+방향 화살표 ② 타이핑+Enter 하면 스피커 발화.
4. 되면 **Phase C(§8 측정)**: WER 은 `test_clean.wav`/`test_noisy.wav` 로 `stt_eval.py` 바로 가능.

**빠른 참조:**
- 통합 스모크 도구: `integration_smoketest.py` (STT+TTS OOM/지연 확인, 마이크·UI 불필요).
- 브랜치: **main 이 통합 기준.** feature 브랜치(jueon=주언TTS/doyu=도유DOA·UI)는 뒤처짐 →
  이어 작업 시 각 브랜치에서 `git merge main` 먼저. (TTS=jueon/주언, DOA·UI=doyu/함도유, STT=구현)
- 남은 큰 일: Phase B 라이브 → Phase C 4지표 측정 → (여유) 케이스 조립 후 DOA front_offset 재캘리브(Phase 8).
- 사람별 할 일 상세: 이 파일 아래 "[2026-07-23] 남은 일 계획" 항목 참조.

---

## 2026-07-23 당시 확정 사실 (mimic3는 이후 Supertonic으로 교체)

- TTS 엔진: **sherpa-onnx 로 간다 (확정).**
- **MeloTTS 폐기. Kokoro 폐기.** (되돌리자고 제안하지 말 것)
  - Kokoro: 받아둔 모델(v1.0)에 한국어 음성이 아예 없음 → 탈락.
  - MeloTTS: 원래 CLAUDE.md 선택이었으나 팀이 폐기함.
- 현재 sherpa-onnx 로 쓰는 한국어 모델: `vits-mimic3-ko_KO-kss_low`
  (경로: `/data2/piper-venv/models/vits-mimic3-ko_KO-kss_low/`)
- 실험/작업 장소: `/data2/piper-venv/` (sherpa_onnx 1.13.4 설치돼 있음, .venv 아님)

## 지난 세션 TTS 실험 결과

- `sherpa_variants.py` 로 A/B/C/D wav 4개 생성 (`~/sherpa_{A_default,B_slow,C_clean,D_slower}.wav`).
  전부 같은 mimic3 low 모델, noise_scale/length_scale/speed 파라미터만 다름.
  - A_default: noise=0.667 nw=0.8 len=1.0 speed=1.0
  - B_slow:    noise=0.667 nw=0.8 len=1.0 speed=0.85
  - C_clean:   noise=0.4   nw=0.6 len=1.0 speed=0.85
  - D_slower:  noise=0.4   nw=0.6 len=1.15 speed=0.8
- 사용자 청취 평가: **넷 다 비슷. 알아들을 수는 있지만 아주 깔끔하진 않음.**
- 진단(Claude): 파라미터 손잡이는 떨림/속도만 바꿀 뿐 모델 음질 한계는 못 올림.
  이 모델은 이름에 `_low` 가 박힌 저품질 모델(mimic3, 2024-01). 원래 받으려던 최신 모델은
  다운로드 404 로 실패해서 이 low 모델로 폴백된 상태였음(`sherpa_setup.log`).

## 목표

- sherpa-onnx 를 유지하면서 한국어 자막-읽어주기 TTS **음질을 더 깔끔하게** 개선.
- MeloTTS/Kokoro 는 빼고 방법을 찾는다.

---

## 로그

### [2026-07-23] 사용자
- 지난 세션에 sherpa-onnx 로 테스트한 wav 4개(A/B/C/D) 기억하냐고 물음.
- 넷 다 비슷하게 애매하니 **개선 방법을 알아보라**고 지시. sherpa-onnx 전환은 확정.

### [2026-07-23] Claude
- `/data2/piper-venv/` 에서 지난 실험 재구성 완료. A/B/C/D 는 mimic3 low 모델의 파라미터 변형이었음을 확인.
- 진단: 파라미터가 아니라 모델이 음질 병목. Kokoro 한국어 음성 없음(탈락) 확인.
- (이 시점에 MeloTTS→ONNX 변환을 제안하려다 사용자가 중단시킴)

### [2026-07-23] 사용자
- **화냄**: 이전 세션 대화를 다 까먹어서 짜증남.
- 지시 ①: 대화를 전부 텍스트 파일로 남겨라. 내가(Claude가) 말할 때마다 로그로 남겨라.
- 지시 ②: **MeloTTS, Kokoro 전부 폐기했다.** (다시 꺼내지 말 것)

### [2026-07-23] Claude
- 이 로그 파일(`docs/conversation_log.md`) 생성. 앞으로 답변마다 여기 append 하기로 함.
- MeloTTS/Kokoro 폐기 확정을 메모리에 기록.
- 다음: MeloTTS/Kokoro 없이 mimic3 계열로 음질 올릴 방법을 사용자와 확정할 차례.

### [2026-07-23] 사용자
- 음질 개선 방향: **"후처리 샘플부터"** 선택.

### [2026-07-23] Claude
- ffmpeg 로 `~/sherpa_C_clean.wav`(mimic3 원음) 후처리 3종 생성. 전부 22050Hz·16bit:
  - `~/sherpa_P1_clean.wav`: highpass 90 + afftdn(nr12) + loudnorm → 저역/잡음 제거, 볼륨 균일
  - `~/sherpa_P2_warm.wav`:  + lowpass 7500 → 고역 쉬쉬음/거친음 완화(부드럽게)
  - `~/sherpa_P3_crisp.wav`: + eq 2.8kHz +3dB → 자음 명료도 강조
- 사용자에게 `aplay` 로 청취 비교 요청. 결과 대기 중.
  - 하나가 확실히 나으면 → 그 레시피를 speaker.py 에 상시 적용 확정.
  - 다 비슷하면 → 후처리 한계, "다른 기성 sherpa 한국어 모델 재수색"으로 전환.

### [2026-07-23] 사용자
- 도유 브랜치 다음 작업 플랜을 요청(이것도 예전에 했는데 컨텍스트 유실로 재작업).
- 작업 방식: **phase 단위. 도유 작업을 phase로 세분화하고, 어떤 phase가 다른 작업자
  (구현=guhyeon/STT, 주언=jueon/TTS)에 의존하면 그 브랜치로 옮겨가 그 일을 한 뒤
  적절한 브랜치로 돌아와 이어간다.**
- 후처리 3종은 들어보고 결과 알려주겠다고 함.

### [2026-07-23] Claude — 도유 다음 작업 플랜
- 현황 파악: 브랜치 doyu(Phase1~5 완료, push됨), main=jueon=guhyeon=bd4318c.
  - doyu 완료분: doa.py(읽기+화면각변환+평활), ui/app.py(자막+DirectionDial+입력창).
  - **guhyeon STT는 이미 doyu 바탕(merge bd4318c)에 포함** → STT 통합은 브랜치 이동 불필요.
  - **jueon TTS speaker.py는 아직 스텁(raise NotImplementedError)**, sherpa로 교체 중 → Phase6의 유일한 외부 의존.
  - 통합시 주의: main.py의 lane_events(events.stream→NotImplementedError)와 finally의
    notes.save()(NotImplementedError)가 스텁이라 예외남 → 안전가드 필요.
- 남은 Phase 정의:
  - **6a** STT+DOA+UI 통합(+스텁 레인 가드) — 브랜치 doyu, **의존 없음, 지금 가능**.
  - **★TTS** speaker.py sherpa 구현(모델+후처리 레시피+output_device 재생), config tts: 갱신,
    §8 TTS지연 측정 — 브랜치 **jueon**, 선행=후처리 청취결과.
  - **6b** 말하기 포함 완전통합(자막+방향+말하기 동시, §10) — doyu, 의존=★TTS.
  - **7** 측정 마무리(DOA오차·자막지연=doyu 단독, TTS지연=★후) — doyu.
  - **8** 케이스 조립 후 front_offset 재캘리브 — doyu, **하드웨어 대기(코드 불가)**.
- 추천 순서: ①지금 doyu Phase6a → ②청취결과 후 jueon으로 hop해 ★TTS → ③jueon→doyu로 speaker.py 반영해 6b → ④doyu Phase7 → ⑤케이스 후 8.
- 사용자에게 "지금 Phase 6a 시작할까?" 물음(후처리 결과 기다리는 동안 의존없는 6a가 생산적). 답 대기.

### [2026-07-23] 사용자
- 후처리 P1~P3 다 들어봤는데 **차이 없음.** "생각 안 하고 일한다, 근본적 개선을 하라"고 질책.

### [2026-07-23] Claude — 근본 원인 재진단 + 모델 교체 조사
- 근본 원인: ① mimic3가 low 티어 ② **더 결정적: 프론트엔드 G2P가 espeak-ng라 한국어 발음이 이미 뭉개짐.** 후처리로는 절대 못 고침. → 모델(+G2P) 교체가 답.
- 조사 결과(웹 다중출처): sherpa-onnx는 이제 VITS/Matcha/Kokoro/Kitten/Zipvoice/PocketTTS/**Supertonic** 지원.
  - **Supertonic v3** = Supertone(한국 오디오AI사) 최신 on-device TTS. 한국어 네이티브, 다화자(10명), 44.1kHz, flow-matching, int8 ~96MB. 품질 "Kokoro급"인데 경량. sherpa-onnx v1.12.29+ 지원(우리 1.13.4 OK).
  - 후보2: neurlang/piper-onnx-kss-korean(=이미 있는 kss.onnx) + 제대로 된 한국어 G2P.
  - 후보3: neurlang/coqui-vits-kss-korean.
- **실행:** Supertonic v3 int8 다운로드(`/data2/piper-venv/models/sherpa-onnx-supertonic-3-tts-int8-2026-05-11/`).
  API: OfflineTtsSupertonicModelConfig(duration_predictor/text_encoder/vector_estimator/vocoder/tts_json/unicode_indexer/voice_style=voice.bin).
  generate(text, GenerationConfig(sid, speed, num_steps, extra["lang"]="ko")). num_speakers=10, sr=44100.
- 한국어 샘플 생성: `~/super_sid0..sid5.wav`(화자6명), `~/super_sid0_hq.wav`(sid0, 32스텝). 문장 동일.
- **속도 주의(정직):** 이 기기=Jetson(tegra). CPU 합성 ~1.9x 실시간(2.7s 오디오에 5.16s). 실시간 발화엔 느림.
  해결: num_steps 낮추기(16→8) 또는 provider="cuda"(Jetson GPU). 속도는 음질 확정 후 최적화.
- 사용자 청취/판단 대기: 음질 mimic3보다 확실히 나으면 Supertonic 확정→화자선택→속도최적화→speaker.py. 아니면 후보2/3.

### [2026-07-23] 사용자
- **"이번엔 다 많이 좋아졌다. 특히 sid0/sid1/sid5가 괜찮다"** → Supertonic 음질 합격.
- 이어서 **"sid0_hq가 제일 괜찮다"** (sid0, 32스텝).

### [2026-07-23] Claude — Supertonic 확정 + 속도 벤치
- **Supertonic v3 = TTS 모델 확정.** 남은 것: ①최종 화자 ②속도 최적화.
- 벤치(Jetson Orin Nano, CPU, 문장 2.7s, threads=4):
  steps 8→2.34s(0.88x·실시간), 12→3.6s, 16→5.0s, 32→9.4s(3.5x).
  threads=6은 오히려 느림(int8 6코어 경합). → threads=4 유지.
- **GPU 상황: 설치된 sherpa_onnx 휠은 CPU 전용(SHERPA_ONNX_ENABLE_GPU=OFF).** provider=cuda도 CPU 폴백.
  PyPI aarch64 휠도 CPU. GPU 쓰려면 **소스 빌드 필요**. 환경: JetPack6.2/L4T R36.4.7/CUDA12.6/py3.10.
  GPU면 32스텝도 <1s 기대 → 품질·속도 동시 해결(단 빌드 1~2h+위험, 마감 내일).
- 스텝별 샘플 저장: `~/super_sid0_s{8,12,16,20,24,32}.wav`.
- 속도 전략 질문(AskUserQuestion)에 사용자가 되물음: "내가 좋다던 다른 파일들은 상황이 다르냐?"
  답변: **속도는 sid 무관, 오직 num_steps로 결정.** 처음 들은 sid0/1/5=16스텝(~5s), sid0_hq=sid0의 32스텝.
- sid1/sid5도 32스텝(hq)으로 생성: `~/super_sid1_hq.wav`, `~/super_sid5_hq.wav` (sid0_hq는 기존).
- 대기: ①최종 화자(sid0/1/5 중, 32스텝 비교) ②속도전략(추천=CPU저스텝 데모보장→GPU빌드 업그레이드).

### [2026-07-23] 사용자
- **확정: 목소리 = sid0. 속도전략 = CPU 저스텝 먼저 → 그다음 GPU 빌드.**
- (중간에 "세 후보 파일명·위치를 알려줘야 듣지" 지적 → 절대경로로 안내함:
  /home/soribom/super_sid{0,1,5}_hq.wav)

### [2026-07-23] Claude — speaker.py 구현(jueon 브랜치)
- **TTS 확정: sherpa-onnx + Supertonic v3, sid0, CPU num_steps=12(저스텝, ~3.6s).**
- 브랜치 jueon 에서:
  - `.venv` 에 `sherpa-onnx==1.13.4` 설치(앱 환경. 기존엔 piper-venv 에만 있었음).
  - 모델을 프로젝트로 복사: `models/supertonic-3-int8/` (.gitignore 의 models/ 로 커밋 제외).
  - `src/config.yaml` tts 섹션 교체: engine=supertonic, model_dir, sid=0, num_steps=12,
    speed=1.0, num_threads=4, language=ko, output_device=null.
  - `src/tts/speaker.py` 재작성: Supertonic 로드 + synthesize()/say() 분리(테스트 용이),
    §8 TTS지연 로그 출력. 모델경로는 repo루트 기준으로 해석.
- 검증: .venv 에서 Speaker(cfg["tts"]) 생성→synthesize("질문 있는 사람은...") = 4.11s(12스텝, 오디오 3.0s).
  결과 `/home/soribom/speaker_selftest.wav` 저장(사용자 청취 대기).
- 재생장치: sounddevice 기본출력 `default` 존재. ReSpeaker에 3.5mm 출력([0])도 있어 I2S 배선 전 테스트 가능.
  최종은 I2S(MAX98357A) 배선 후 config output_device 인덱스 지정.
- ⚠️ 아직 커밋 안 함(사용자 직접 커밋 선호). jueon 변경분: config.yaml, tts/speaker.py.
- 다음: ①사용자 12스텝 청취 확인 ②GPU 빌드(provider=cuda→32스텝 실시간) ③doyu Phase6 통합.

### [2026-07-23] 사용자
- ①12스텝 들어보니 괜찮음(CPU 기본값 확정) ②GPU 빌드 진행 승인.

### [2026-07-23] Claude — GPU 빌드 착수(백그라운드)
- 레시피 확정: JetPack6.2/CUDA12.6 → onnxruntime-gpu **cuda12-1.18.1** (cmake가 자동 다운로드).
  플래그: `-DSHERPA_ONNX_ENABLE_GPU=ON -DSHERPA_ONNX_LINUX_ARM64_GPU_ONNXRUNTIME_VERSION=1.18.1`.
- 소스: `/data2/build/sherpa-onnx` (git master = **버전 1.13.4로 우리 것과 동일 → speaker.py API 그대로 OK**).
- 안전策: .venv 를 안 깨게 **wheel 로 빌드**(`pip wheel . --no-deps --no-build-isolation -w /data2/build/wheel`),
  성공 후 .venv 에 설치. 실패시 `pip install sherpa-onnx==1.13.4` 로 CPU 복구.
- 메모리 빠듯(가용 2.2Gi) → `CMAKE_BUILD_PARALLEL_LEVEL=2` 로 OOM 회피.
- 빌드 로그: `/data2/build/build.log`. 백그라운드 실행(완료시 자동 알림). 20~40분 예상.
- 빌드 성공 후 할 일: (1) throwaway 환경/직접 GPU provider 로 Supertonic 로드 테스트 →
  (2) 32스텝 지연 측정(GPU) → (3) config num_steps=32 + speaker.py provider="cuda" 로 전환 →
  (4) 재측정. 실패시 CPU 12스텝 유지.

### [2026-07-23] 사용자
- "빌드는 기다리고, 그동안 Phase 6a 시작하자."

### [2026-07-23] Claude — Phase 6a 코드(doyu 브랜치)
- 브랜치 hop: jueon TTS 미커밋분(config,speaker)을 `git stash` (stash@{0}) → `git checkout doyu`.
  (untracked conversation_log.md 등은 유지됨. jueon 복귀 시 stash pop 예정.)
- `src/main.py` 통합 가드 추가(Phase 6a):
  - lane_events(기능③, 스텁)는 `cfg["events"].enabled` 일 때만 시작 → 지금 false 라 안 뜸.
  - `notes.save()`(기능⑤, 스텁)는 `cfg["summary"].enabled` 일 때만 호출 → 종료 크래시 방지.
  - lane_caption 독스트링 medium 2패스→small 단일패스로 정정.
- 검증(가벼움, 모델 로드 없이): py_compile OK. events/summary 둘 다 false 확인
  → 통합앱은 [자막(STT)+방향(DOA)+UI] 3레인만, 스텁 건너뜀.
- **라이브 실행(마이크→자막+방향)은 GPU 빌드와 메모리 경합(OOM) 우려로 빌드 완료 후로 미룸.**
- 커밋 대상(doyu): `src/main.py` (사용자 직접).
- 대기: GPU 빌드 완료 알림 → ①GPU Supertonic 테스트 ②Phase6a 라이브 실행.

### [2026-07-23] GPU 빌드 완료 + 성공
- wheel 빌드 성공: `sherpa_onnx-1.13.4+cuda-cp310-cp310-linux_aarch64.whl` (91M, GPU libs 포함).
  위치 `/data2/build/wheel/`. 소스 `/data2/build/sherpa-onnx`.
- 1차 GPU 테스트 실패: `CUBLAS_STATUS_ALLOC_FAILED`/`NvMap error 12(ENOMEM)`. 원인 = **메모리 부족**.
  Jetson은 CPU/GPU가 8GB RAM 공유. 범인 = **Chromium(portable) ~2.7GB**.
  → 사용자가 Chromium 닫음(free 330MB→2.6GB). **교훈: 데모 땐 브라우저 등 끄고 lean 하게.**
- 2차 GPU 테스트 성공(provider=cuda, 격리 testvenv):
  warmup 4.3s(1회), 이후 **steps16=0.88s(0.33x), steps32=1.55s(0.58x)**. CPU였으면 5.0/9.4s.
  → **32스텝(최고품질) GPU로 1.5초 = 실시간.** 품질·속도 동시 해결. 샘플 `~/super_gpu_s32.wav`.
- **.venv 에 GPU wheel 설치 완료**: CPU판 제거 후 `1.13.4+cuda` 설치. .venv에서 32스텝 1.79s 확인.
  복구 필요시 `pip install sherpa-onnx==1.13.4`(CPU).
- 남은 TTS 마무리(jueon): config num_steps 12→32 + provider 키 추가(cuda), speaker.py provider 설정화
  (+ cuda 실패시 cpu 폴백 권장). 지금 doyu 브랜치라 jueon 복귀 필요(stash@{0} pop).

### [2026-07-23] Phase 6a 커밋+푸시 (doyu)
- 사용자가 커밋 메시지 확정("쉬운 표현"). author=함도유로 커밋.
- commit b2ac810 "Phase 6a: 자막·방향·말하기 입력을 한 화면에서 함께 작동하도록 main.py 정리".
  committer=강주언, author=함도유. `git push origin doyu` 완료 (d718b9f..b2ac810).

### [2026-07-23] TTS 마무리 (jueon) — GPU 32스텝 확정
- jueon 체크아웃 + stash pop 으로 TTS 변경 복원.
- `src/config.yaml` tts: `provider: cuda` 추가, `num_steps 12→32` (주석에 GPU/CPU 실측 정리).
- `src/tts/speaker.py`: __init__ 을 provider 설정화 + **GPU 초기화 실패 시 CPU 자동 폴백**
  (Jetson 공유메모리라 CUBLAS_ALLOC 대비). num_steps 기본값 32.
- 검증(.venv, GPU): Speaker(cfg) provider=cuda steps=32 sid0 sr44100.
  긴 문장 합성 1.73s(오디오 3.0s) = 실시간. 결과 `~/speaker_gpu_selftest.wav`.
- 후속(미정): CLAUDE.md §4·§5 가 아직 MeloTTS 로 적혀있음 → Supertonic 으로 갱신 필요.
  requirements.txt 도 확인 필요(melotts 잔재).

### [2026-07-23] TTS 커밋 — 브랜치 확정: jueon, author 주언
- 사용자: TTS 는 doyu 아니라 **jueon 브랜치, author=주언**. (잠깐 doyu로 옮겼다 다시 jueon으로 되돌림)
- commit **3bb1e26** (jueon) "말하기 기능의 TTS를 sherpa-onnx + Supertonic으로 교체 (GPU 32스텝, 실시간)".
  author=강주언 <jueonk10@gmail.com>. `git push origin jueon` 완료 (bd4318c..3bb1e26).
- 현재 원격 상태:
  - jueon: 3bb1e26 (TTS Supertonic) — 주언 담당(⑥ 말하기)
  - doyu:  b2ac810 (Phase 6a 통합) — 함도유 담당(② 방향 + UI)
- 브랜치 규칙 정리: **TTS=jueon(주언), DOA/UI/통합=doyu(함도유), STT=guhyeon(구현, 이미 main에 병합됨).**
- 남은 일: Phase6b(TTS를 통합앱에 연결, doyu에 jueon speaker 병합 필요) / Phase6a 라이브실행 /
  Phase7 측정 / CLAUDE.md·requirements 문서갱신 / I2S 스피커 배선후 output_device.

### [2026-07-23] 전체 main 병합
- 사용자 요청: 지금까지 한 것 전부 remote main 에 병합.
- 겹치는 파일 없음 확인(jueon=config/speaker, doyu=main/doa/app/docs/tests/.gitignore) → 충돌 없음.
- `git checkout main` → `merge --no-ff jueon`(f280441) → `merge --no-ff doyu`(d9a606b) → `push origin main`.
- 결과 remote main = **bd4318c..d9a606b**. 세 기능(①자막 기존 + ②DOA/UI + ⑥TTS) + Phase6a 통합 전부 포함.
  main:config.yaml = engine:supertonic / provider:cuda / num_steps:32 확인.
- 주의: 병합 후 jueon/doyu 브랜치는 main 보다 뒤처짐(다음 작업 시 main 기준으로 새로 파생 or main 병합).

### [2026-07-23] 남은 일 계획 + 준비작업(1,2,3) + Phase A
- 사용자에게 사람별(구현/도유/주언) 남은 일 + 진행순서 제안함. 마감 내일(7/24) 강조.
  순서: PhaseA(통합 OOM 제거) → PhaseB(세 기능 한 화면) → PhaseC(§8 측정) → PhaseD(문서/케이스).
- **① 문서 갱신** (main 커밋 c8a289f, author=주언): CLAUDE.md §4·§5 MeloTTS→Supertonic,
  requirements.txt melotts 제거+sherpa-onnx 추가(GPU wheel 빌드법 주석). push 완료.
- **② 스모크 테스트 스크립트** 작성: `/data2/code/soribom/integration_smoketest.py` (untracked).
  STT(GPU)+TTS(GPU) 동시상주 OOM/지연 측정. 마이크/UI 없이 핵심만.
- **③ 측정도구 정리**: WER=record_test.py→stt_eval.py(CER/WER/시간). 녹음 `test_clean.wav`(조용)/
  `test_noisy.wav`(시끄러움) 이미 있음 → Phase C 즉시 가능. DOA=도유도구, TTS지연=speaker로그.
  ⚠️ experiments/analysis.py(이해도 실험, 대응표본 t검정)는 scipy·pandas 미설치+참가자데이터 필요 → 별개.
- **Phase A 통과 ✅** (`integration_smoketest.py test_clean.wav`):
  STT 로드 2.7s + TTS 로드 1.6s, 둘 다 cuda 상주. STT추론 3.09s(정확), TTS합성 2.11s(5.6s문장).
  **테스트 중 최저 여유메모리 3051MB** — OOM 없음, 여유 충분. → 최대 리스크(통합 OOM) 해소.
- 다음: Phase B = main.py 실제 라이브 실행(마이크→자막+방향, 타이핑→발화). 사람이 기기 앞에서 확인 필요.

### [2026-07-24] Phase B 라이브 확인 + Phase C 측정 (스피커 연결 후, 사용자 6시간 부재 중 자율작업)
- 사용자: **블루투스 스피커(Bose SoundLink Mini) 연결.** 시연도 이걸로 진행. Chrome 닫음.
- 재생 장치: Bose = PipeWire 기본 싱크 `bluez_output.C8_7B_23_EF_4E_9A.a2dp-sink`.
  → `sd.play(device=None)` 이 기본 싱크로 나가므로 **config `output_device: null` 그대로 OK** (인덱스 지정 불필요).
  `paplay` 로 기존 TTS wav 재생 → 사용자가 Bose에서 소리 들림 확인.
- **Phase B 통과:** `main.py` 라이브 실행. 전체화면 UI + 마이크 6채널 캡처 + STT/DOA/TTS 상주.
  사용자가 입력창 타이핑→Enter→**TTS "안녕하세요" 정상 발화 확인**, ESC로 정상 종료.
  → 세 기능 한 화면 동작(§10 완료조건) 충족.
- **Phase C 측정(§8) — 결과는 `docs/phase_c_measurements.md` 에 정리:**
  - 자막: **clean CER 0.0% / noisy CER 0.7%** (실제 파이프라인=VAD+small+prompt). WER 16.7%는
    대부분 띄어쓰기 차이(오인식 아님). 새 측정도구 `phase_c_eval.py` 작성(stt_eval.py는 prompt 미적용이라 불리).
  - 자막 지연: 발화당 전사 **중앙 ~0.62s**.
  - TTS 지연: 타이핑→소리 **중앙 ~1.79s (1.5~2.0s)**, 문장 길이 무관.
  - 동시상주: 스모크 재실행 최저여유 3,666MB, OOM 없음.
  - **DOA 오차만 미측정** — 알려진 각도에서 실제 발성 필요(사람 손). 측정법은 measurements 문서에.
- 남은 사람 손 필요: ① DOA 오차 측정 ② (케이스 조립 후) front_offset 재캘리브 ③ I2S 스피커 쓸 거면 배선(지금은 BT라 불필요).
- 이후 자율작업: 개발 경험 없는 사람용 100페이지 설명서 작성 시작(task #3).

### [2026-07-24] 커밋+푸시: Phase B·C 산출물 (main, author 주언)
- 사용자: "현재까지 작업은 주언 주도 공동작업. 커밋하고 푸시하자."
- commit **7166cf3** (main, author 강주언) → push 완료 (c8a289f..7166cf3).
  포함: integration_smoketest.py, phase_c_eval.py, docs/phase_c_measurements.md, docs/conversation_log.md, modelAdvice.txt.

### [2026-07-24] 역할·브랜치 리마인드 + 하드웨어 담당 조사
- 세 사람 역할 재확인(git 대조): **강구현=STT(guhyeon), 함도유=DOA·UI·통합(doyu), 강주언=TTS·하드웨어·통합(jueon, 리더)**. 셋 다 main 병합됨.
- 현재 위치: **main** 브랜치(통합/측정/문서 단계라 feature 브랜치 아님). 진행 파일은 전부 untracked였음.
- **하드웨어 주문·조립(3D프린팅 케이스 포함) 조사 주도 = 강주언** 확정. 근거: hardware/BOM.md(조달·품절대응 조사, author jueonkangg=주언) + Day1 역할표(Jetson 조립·I2S 배선=주언). 사용자 확인함.

### [2026-07-24] 100페이지 초보자용 설명서 작성 (자율작업, 사용자 6시간 부재)
- 결정사항(사용자 확답): 형식=**인쇄용 A4 HTML**, 성격=**교육+작품설명서 겸용**, **실명+팀명(제주 BTS)** 사용·설치장소는 "아파트 커뮤니티실"로 일반화, 하드웨어 조달 크레딧=강주언.
- 배경 반영: 셋이 함께 방향 결정 / 아파트 커뮤니티실에 허가받고 Jetson 설치 / 매일 한 명씩 번갈아 개발 / 케이스 품절→3D프린팅(주언 주도 조사, 조립은 다같이).
- 산출물: **`docs/소리봄-설명서.html`** (표지·일러두기·목차·한눈에요약·1~14부·개발일지·더알아보기①~⑤·부록A~G). 콜아웃 상자 색코딩, 실측 수치, 기존도식(ui-mockup·hardware·system-flow.svg) 임베드.
- **자가점검(사용자 요청)**: check.py로 태그균형·그림경로 검증(무결), chromium headless로 PDF 렌더→**실제 77페이지** 확인, PDF 페이지 직접 열람해 한글폰트·상자·표·그림 렌더 정상 확인. stray </p>·</strong> 몇 건 발견·수정.
- 현황: **77페이지**(목표 100엔 못 미침 — 패딩 대신 진짜 내용 우선). 구조·렌더 이슈 0. **아직 커밋 안 함**(사용자 자가 검토·커밋 선호 존중; 파일은 디스크에 안전).
- 남은 여지: 원하면 각 부 심화로 100p까지 확장 가능. DOA오차 측정·케이스후 보정은 여전히 하드웨어 대기.
- 사용자 결정: 설명서 확장은 **내일(토=7/25) 개발 완료 후** / 설명서는 **.gitignore로 GitHub 제외**(미커밋 유지).

### [2026-07-25] .gitignore 복구 + 개인정보 커밋 점검
- `.gitignore` 상단 개인정보 패턴이 **mojibake(인코딩 손상)로 무시가 안 걸리던** 것을 발견 → **UTF-8로 재작성**(역복구는 literal `?` 손실로 불가, 문맥 유추 재작성). 개인정보 패턴 작동 검증 완료.
- **remote 개인정보 커밋 점검: 이력 전체(모든 브랜치) 깨끗함** — 패턴이 깨졌어도 팀이 그런 파일을 애초에 안 올림. 규정 위반 없음.
- 설명서·micTest.txt도 무시 처리.

### [2026-07-25] DOA 오차 측정 완료 (§8 4종 전부 완료)
- 스피커=Bose BT 확정(I2S 배선 불필요, output_device=null).
- **doa.py `_selftest` 개선(Phase 8):** 4초 raw 수집 → 원형 최빈 클러스터(`_robust_center`)로 반사음·잡값 제거 + 안정/불안정 판정 + 불안정시 재측정. 순수함수 로직 테스트·실기기 사전점검 통과. front_offset(90)은 측정전용이라 안 건드림.
- **★핵심 발견: 케이스가 마이크 면을 덮으면 DOA 붕괴.** 덮인 상태 28~64°+잴때마다 다름(앞 raw 90→270 뒤집힘). **마이크 면(LED·구멍4개) 노출하니 평균 1.5°**(앞1/오2/뒤3/왼0°, 퍼짐0~3°, 채택100%). → 최종 케이스는 마이크 윗면 개구부/노출 필수.
- **§8 지표 4종 전부 완료:** 자막 CER 0.0/0.7% · 자막지연 ~0.6s · TTS지연 ~1.8s · **DOA 1.5°**. → `docs/phase_c_measurements.md` 갱신.
- 미커밋 변경: .gitignore, docs/conversation_log.md, docs/phase_c_measurements.md, src/audio/doa.py, doyu/tests/*phase8.txt(신규). (사용자 자가커밋 선호)

### [2026-07-25] ▶ 대기 중인 후속 작업 (구현 완료 후)
- **설명서 확장·갱신 필요**: 마지막 설명서 작성 이후 구현분(경량③ 이름호명, ⑤수업요약→전사기록 전환, UI 밝은테마 개편, hotwords+과목별 사전, 환각 방어)을 설명서에 반영.
- **UI mockup 교체**: 설명서의 ui-mockup.svg(가짜)를 **실제 UI 스크린샷**으로 저장·교체. (실제 UI가 mockup과 다름)
- 진행 중: hotwords 전환 + 과목별 용어사전(src/vocab/) + UI 과목 드롭다운. summary→transcript 전환도 남음.

### [2026-07-25] ▶ 설명서에 추가할 '개발 중 힘들었던 상황' 3가지 (테스트 후 반영)
1. **케이스 조달·조립**: Jetson Orin Nano 기성 케이스가 모든 웹사이트 품절 → GitHub 오픈소스 3D프린팅 설계도로 주문 제작. 조립법이 GitHub에 없어 **생성형 AI에 물어가며 조립**.
2. **M3 인서트 너트 삽입**: 인두기로 3D프린팅한 마이크·PC 케이스에 삽입. 예상보다 어려움 — **작은 너트로 실패 → 구멍 커진 곳에 더 큰 너트 삽입해 결국 성공**.
3. **온보드 스피커**: 부품 구매 후 납땜으로 전부 연결·장착했으나 제대로 작동 안 함 → **블루투스 스피커로 전환**(현재 데모도 BT).
   (→ 12부 함정 또는 8부 하드웨어 이야기에 추가. 설명서 확장 시 함께.)

### [2026-07-26] 실측 CER 5과목+자연발화+수식 테스트 (설명서 반영 예정)
- 5과목 또박또박 라이브 CER: 국어3.6 수학3.8 과학1.8 영어2.3 경제4.4 → 평균 3.2%(숫자표기·띄어쓰기 제외 시 ~1.5%).
- 자연스러운 빠른 반말(경제): CER 15.3% → 자연발화 한계 확인. hotword 과편향(팔려는→탄력은), 이름 실패(도유야→토요약)도 관찰.
- 수학 이차방정식(수식 발화): raw 10.4%지만 대부분 표기차이(엑스→X, 육은영→6은0), 실질 오류 ~1%. 수식을 표준표기로 변환.
- ▶ 설명서에 'rigorous testing 노력'(불완전 발화 고려: 자연발화·수식 테스트) + 실측 CER 병기 + 자연발화 한계를 정직하게 추가할 것.


### [2026-10-10~11] Codex 전환 후 기능 추가·안정성 개선·main 통합
- `3051b0b` 화면 테마·대화 공백, `e8a4af5` 경제 용어 사전 보강 내용을 확인해 공유 이력을 정리했다.
- 강주언 작업 브랜치 `jueon`에 최신 main을 반영하고 작성자 설정을 확인했다.
- `0593e9a`: 현재 기록 미리보기·Gmail 본문/TXT 전송·설정 도구·권한 검증·메일 UI와 자동 테스트 구현.
  사용자가 설정·UI를 확인했으나 실제 Gmail 수신 결과는 기록되지 않았다.
- `7922632`: 마이크/방향 오류 분리, 상태 줄·재연결 버튼, 5초 재시도, 단일 녹음 프로세스,
  음성 버퍼 제한·연결 세대 처리·모델 준비 중 화면·종료 처리 구현. 자동 테스트 26개 통과.
- 반복 테스트에서 강제 종료 시 공유 큐·종료 잠금으로 수신/정리가 멈출 수 있는 경로를 발견해
  작은 오디오 프레임의 원자적 파이프 전송과 파이프 종료 신호로 변경했다. 방향 USB 대기가
  수음을 막지 않도록 방향 워커도 분리했다.
- 사용자 정상 동작 확인 후 `jueon` 커밋·푸시, 10/11 요청에 따라 main에 충돌 없이 병합·푸시했다.
  다른 팀원 stash는 보존했다.

### [2026-10-11] 문서와 실제 구현 대조·최신 현황 갱신
- README·CLAUDE·시스템 설계에 남은 2-패스/MeloTTS/I2S/스텁 설명을 현재 코드 기준으로 정정했다.
- 통합 로그 상단에 기능·수정 이력·검증 범위·14가지 문제의 현재 상태와 근거를 정리했다.
- 이메일 문서의 jueon 전용 상태를 main 통합 완료로 갱신하되 실제 Gmail 수신은 미검증으로 유지했다.
- 기존 측정값은 보존하고 전사/합성 시간과 전체 지연의 차이, DOA 평가 한계를 명시했다.
- 과거 일정·체크리스트는 당시 기록으로 표시했다. 이번 문서 갱신은 사용자 요청에 따른 로컬 수정이며
  별도 커밋·푸시 여부는 Git 상태에서 확인한다.

### [2026-10-11] 기록 자동 저장·말하기 중복 및 출력 오류 보호
- 사용자 요청으로 우선순위 높은 기록 보존·말하기 안정성을 구현했다. jueon에 최신 main을
  반영했으며 다른 팀원 stash를 변경하지 않았다. 새 구현은 현재 커밋·푸시 전이다.
- 주기적 저장 워커 하나를 추가했다. 실행별 고유 TXT를 갱신하고 권한 600 임시 파일의 쓰기·fsync가
  끝난 뒤 교체한다. 실패 시 이전 파일과 메모리 기록을 유지하고 화면에서 안내·다음 주기 재시도한다.
- 말하기 작업 중 입력·버튼을 잠그고 중복 요청을 무시한다. Speaker에도 동시 호출 잠금을 적용했다.
  성공 시 입력을 지우고 실패 시 입력 보존·출력 스트림 정리·재시도가 가능하다. 기본 200자 제한을 적용했다.
- 자동 테스트 41개 통과. 모델 준비 중 종료해도 저장 워커 정리와 마지막 기록 저장을 확인했다.
  밝은/어두운 화면을 렌더링해 상태 안내를 확인했다. 새 기능의 실제
  GPU 모델·ReSpeaker·BT 통합 확인은 아직 수행하지 않았다. 실제 메일도 발송하지 않았다.
- 방향의 시점 문제는 수음 시각 전달·제한된 방향 표본 보관과 발화 연결이 필요함을 확인했다.
  이번에는 기존 방향 코드 유지, 다음 설계와 실기기 확인 순서를 문서로 남겼다.

### [2026-10-11] 기록의 요일·과목 추가와 스피커 잡음 조사·복구
- 사용자가 직전 기록·말하기 개선을 테스트했다고 보고하고, 요일·과목 표시와 말하기 잡음 해결을 요청했다.
- 기록 보기·저장 TXT·메일 본문에 시작 날짜의 한국어 요일과 과목을 표시했다. UI 과목 변경을
  기록에 연결하고, 각 발화의 과목을 보존해 중간 변경으로 이전 내용을 재분류하지 않는다.
  여러 과목은 한 파일에서 구간별로 구분한다. 전사 시작 시 과목을 복사한다.
- 실제 GPU 파형 두 문장의 peak는 0.241/0.391, 음량 초과·NaN/무한대는 없었다. A2DP/SBC 연결을 확인했다.
  기본 sounddevice 재생 비교는 시작 시간 초과로 실패해 청취 비교로 사용하지 않았다.
- PulseAudio/PipeWire 직접 재생, 순수 톤, GPU/CPU 음성에서 사용자가 같은 잡음을 확인했고,
  유튜브에서도 같다고 보고했다. 모델 합성만의 문제보다 공통 출력 경로 문제로 범위를 좁혔다.
- Bose 스피커의 Bluetooth 연결을 끊고 같은 장치로 재연결했다. 사용자가 “이제 소리가 깔끔하다”고
  확인했다. 이어 기존 Speaker.say 경로로 실제 합성·재생도 정상 완료됐다.
- 원인은 기존 Bluetooth 연결 세션과 관련된 것으로 판단한다. 내부 무선 간섭·버퍼·드라이버 원인은
  확정하지 않았다. TTS 모델·파형 필터는 변경하지 않았고, 페어링 삭제·OS 설정 파일 수정도 하지 않았다.
- 요일·과목·변경 중 과목 보존 테스트 3개를 추가해 총 44개 통과. 사용자가 새 기능의 커밋·푸시·
  main 병합 후 doyu 브랜치로 이동해 다음 우선순위의 개발을 진행하도록 요청했다.

### [2026-10-11] 기록·말하기 main 공유 및 doyu 방향 시점 개선
- `521776d`(강주언): “수업 기록 자동 저장·요일·과목 표시 및 말하기 안정성 개선” 커밋을
  origin/jueon에 푸시하고 main에 fast-forward 병합·푸시했다. 원격 main과 jueon이 동일한
  `521776d00cbba6fce3bffe251f89ce6bfc8d110e`인 것을 직접 조회해 확인했다.
- doyu로 이동하고 최신 main을 반영했다. 다른 팀원의 영어 모드 등 stash는 적용·삭제하지 않았다.
- 방향 워커가 원본 표본의 USB 시작·완료 시각을 제한된 버퍼에 저장한다. VAD에 수음 시각을
  전달하고 음성으로 판정한 시간의 표본만 해당 자막에 연결했다. STT 처리 중 다음 화자 방향이
  들어와도 앞 자막·노트의 방향으로 사용하지 않는다.
- 발화별 주된 원형 방향을 집계하고, 최소 표본·70% 합의에 못 미치면 오래된 화살표를 지워
  미확정으로 표시한다. 기본 60초·602개 표본 한도, 동일 워커·USB 제한·연결 세대 처리를 유지했다.
- 총 55개 자동 테스트 통과(9.185초). 실제 교대 발화 확인은 남았으며 새 방향 코드는 현재 doyu
  로컬 변경으로 커밋·푸시 전이다. 범위와 확인 순서는 `docs/17-direction-timing.md`에 기록했다.

### [2026-10-11] doyu 작업 유지·최종 자동 검증
- 사용자가 guhyeon 전환을 취소하고 doyu 작업부터 마무리하도록 요청했다. 전환 전 stash 명령은
  실행되지 않았으며, 브랜치·미커밋 변경·기존 팀원 stash가 그대로 보존된 것을 확인했다.
- 방향 시점 개선 코드를 재검토하고 전체 자동 테스트 55개를 다시 실행해 모두 통과했다(9.336초).
  모의 재연결 4회에서 부모 RSS는 209,908 KiB로 일정했다. 실제 GPU·USB 장시간 시험과 구분한다.
- 최신 현황의 기록·말하기 시험 설명을 사용자 테스트 보고·실제 재생 확인과 맞도록 정정했다.
  방향 개선의 실제 교대 발화 확인은 아직 남았고, 새 변경은 커밋·푸시 전이다.

### [2026-10-11] 방향 개선 실기기 확인
- 사용자가 22:06:42~22:07:55의 스크린샷 4장을 제공하고 “예상한 대로 작동하고 있어”라고 확인했다.
- 화면에서 연결 장애 안내·기존 자막 유지·화살표 제거·재연결 후 방향 표시 복귀를 확인했다.
  실제 위치별 각도·교대 발화별 정량 결과·장시간 시험 수치는 제공되지 않았다.
- 방향 제목의 “누가, 어디서”를 삭제하고 “화자 방향”으로 단순화하는 방안을 제안했다.
  이 확인은 작동 결과에 대한 사용자 보고이며, 문구 변경은 아직 적용하지 않았다.
- doyu의 새 변경은 커밋·푸시 전이며 다른 팀원의 stash는 보존했다.

### [2026-10-11] 방향 제목 간소화
- 사용자 승인으로 기본·정상 방향 제목을 “화자 방향”으로 변경했다.
- “화자 방향 (미확정)”·“방향 확인 불가” 등 상태 안내는 유지한다.

### [2026-10-11] 방향 개선 공유·guhyeon 자막 누락 개선
- `38279b6` “발화 시점에 맞춘 화자 방향 표시 및 문구 간소화”(작성자 강주언)를
  origin/doyu에 푸시하고 main에 fast-forward 병합·푸시했다. 원격 두 브랜치가 같은 커밋임을 확인했다.
- 사용자 요청으로 guhyeon에 이동하고 origin/main을 fast-forward 반영했다. 기존 doyu stash는 보존했다.
- 정상 용어 나열을 텍스트 형태만으로 삭제하는 경로를 수정했다. 나열과 낮은 신뢰도가 함께
  나타나는 세그먼트만 제외해 다른 정상 설명을 보존한다. 무음·매우 낮은 신뢰도 방어는 유지한다.
- 전사 시작 시 사전을 복사해 hotwords와 검사 기준을 고정했다. 새 모델·의존성은 추가하지 않았다.
- 참가자 실패 문장의 원자료·새 필터의 실기기 결과는 아직 없어, 초기 기준의 적합성은 별도 확인이 필요하다.
  범위·근거·테스트 순서는 `docs/18-subtitle-filter.md`에 기록했다. 새 작업은 커밋·푸시 전이다.
- 기존 55개와 STT 필터 회귀 8개를 포함해 전체 63개 자동 테스트 통과(9.157초).
  STT 출력 모의 검증이며 실제 GPU 인식률·수업 CER 개선을 측정한 결과는 아니다.

### [2026-10-12] 자막 필터 개선 공유 요청
- 사용자 요청으로 guhyeon의 자막 필터 개선 코드·설정·회귀 테스트·문서를 커밋·푸시한다.
- 작성자는 기존 Git 설정인 강주언으로 유지한다. 실기기 결과는 아직 보고받지 않았다.
- 기존 63개 자동 테스트 통과 결과를 확인했고, 다른 팀원의 doyu stash는 보존했다.

### [2026-10-12] 자막 필터 main 통합·이름 알림 개선
- `98d9856`을 main에 fast-forward 병합·푸시했다. 원격 main/guhyeon이 같은 커밋임을 확인했다.
- guhyeon으로 돌아와 이름 알림이 등록 목록 전체의 최단 이름을 표시하던 경로를 수정했다.
  실제 전사에서 찾은 이름으로 표시하고 단어 경계·한국어 호격/조사로 부분 일치 오탐을 줄인다.
- 여러 이름이 나오면 첫 언급 한 건만 알리고 같은 위치는 긴 이름을 우선한다.
- 이름 알림 회귀 9개를 추가해 전체 72개 자동 테스트 통과(9.108초). 실제 음성 전사·의미상
  호명 판별 검증은 아니다. 상세 범위·제약은 `docs/19-name-alerts.md`에 기록했다.
- 새 이름 알림 작업은 로컬 변경이며 커밋·푸시 전이다. doyu의 팀원 stash는 보존했다.

### [2026-10-12] 호명 표현·공통 수업 hotwords 보강
- 사용자 스크린샷과 보고에서 “함도유”, “도유야”, “도유 학생”, “함도유 학생”의 STT 오인식을 확인했다.
  이름 알림 로직의 자동 테스트와 실제 이름 음성 인식 문제를 구분한다.
- 사용자 선택에 따라 등록 이름에서 호격·학생 호칭을 생성해 STT hotwords에 연결했다.
  과목 변경 후에도 유지하며, 알림 등록 이름은 변경하지 않는다. 오인식 텍스트 자동 치환은 하지 않는다.
- 기존 공통 65개·5개 과목 사전을 확인하고 공통 사전에 빠진 기본 수업 표현 15개를 추가했다.
  공통 80개, 국어 52개, 수학 54개, 과학 48개, 영어 45개, 경제 162개다.
- 실제 인식 개선 여부는 재시험이 필요하다. 이번 hotwords 변경과 이전 이름 알림 변경은
  guhyeon의 미커밋 작업이며 팀원 stash는 보존했다. 상세 내용은 `docs/19-name-alerts.md` 참고.
- 호명 표현과 사전 전달 회귀 4개를 추가해 전체 76개 테스트 통과(8.970초).
  모델 출력의 실제 정확도 개선을 측정한 결과는 아니다.

### [2026-10-12] 호명 재시험 실패·hotwords 잘림 수정
- 사용자가 00:38:38 화면과 함께 오인식 지속 및 이전에는 없던 문제라고 보고했다.
- 설치된 faster-whisper 코드와 실제 small 토크나이저에서 최대 223토큰만 사용함을 확인했다.
  과학 490·경제 1,112토큰 문자열의 뒤에 있는 이름은 실제 모델 힌트에서 제외되고 있었다.
  직전 main도 이름이 잘려 있어 전체 회귀의 원인을 최근 변경 하나로 단정하지 않는다.
- 앞선 문자열 포함 검사만으로 실제 힌트 전달을 보장하지 못했던 검증 누락을 인정하고 수정했다.
  이름·호칭 우선, 과목/공통 용어 교대, 실제 토큰 제한 내 완전한 항목 선택을 적용했다.
- 5개 과목 모두 기본 8개 호칭이 실제 라이브러리 프롬프트에 포함됨을 확인했다.
  전체 79개 테스트 통과(9.953초), GPU 음성 인식 개선은 재시험이 필요하다.
- 작업은 guhyeon의 미커밋 변경이다. 상세 측정과 한계는 `docs/19-name-alerts.md` 참고.

### [2026-10-12] 이름 인식 해결 확인·핵심 발견 기록
- 사용자 제공 00:44:39 화면에 “함도유학생”, “도유야”, “도유야, 오늘 광합성 잘 이해했어?”,
  “함도유야”가 정확히 표시됐고 사용자가 “해결됐다”고 확인했다.
- 설치된 faster-whisper 1.2.1의 223토큰 제한·앞부분 잘림, 첫 검증이 놓친 점,
  이름 우선·완전한 용어 선택·실제 프롬프트 회귀 검증을 `docs/19-name-alerts.md`와 CLAUDE에 남겼다.
- 이 결과는 해당 호칭·문장의 인식 해결 확인이다. 화면에 알림이 보이지 않아 이름 알림 표시까지
  검증한 것으로 확대하지 않는다. 전체 CER·무음 오탐·다른 과목·장시간 시험은 별도 확인 대상이다.
- 문서만 갱신했고 직전 코드 검증은 79개 통과다. 새 작업은 guhyeon의 커밋·푸시 전 변경이다.

### [2026-10-12] 이름 알림·hotwords 개선 공유 요청
- 사용자 요청으로 이름 알림 대상 수정·호명 표현 생성·공통 수업 사전 보강·실제 토큰 제한
  적용과 발견 기록을 함께 guhyeon에 커밋·푸시하고 main에 통합한다.
- 코드 검증은 79개 테스트 통과이고, 사용자가 실기기에서 이름 인식 해결을 확인했다.
- 작성자는 기존 설정인 강주언을 유지하며 다른 팀원의 doyu stash는 보존한다.
