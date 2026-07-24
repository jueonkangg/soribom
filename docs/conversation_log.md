# 소리봄 대화 로그 (TTS / sherpa-onnx)

이 파일은 Claude 와의 대화를 세션이 바뀌어도 잃지 않도록 남기는 로그다.
규칙: **Claude 는 사용자에게 답할 때마다 그 발언을 이 파일 맨 아래에 append 한다.**
사용자 발언도 요지를 같이 남긴다.

---

## ▶ 다음 작업 (새 세션은 여기부터 — 2026-07-23 마지막 갱신)

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

## 확정 사실 (까먹지 말 것)

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
