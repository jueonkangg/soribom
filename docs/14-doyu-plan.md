# 함도유 작업 계획 — 소리 방향(DOA) + 화면(UI)

담당: **DOA(누가·어디서) + UI(화면)**. 파일: `src/audio/doa.py`, `src/ui/app.py`.
브랜치: `doyu`. 원칙: **작은 단위로 만들고 그때그때 검증**(CLAUDE.md 1장), 측정 코드도 같이(8장).

전제: **주언이 DOA 캘리브레이션을 이미 했다.** `config.yaml`의 `doa:` 값과
`docs/13-doa-calibration.md`를 재사용한다. 처음부터 다시 재지 말 것.

> ⚠️ **케이스 관련 중요**: 마이크(ReSpeaker)가 **아직 케이스에 고정되지 않았다.**
> "앞(front)"이 어디인지는 케이스에 넣은 뒤 물리적 방향으로 확정된다. 그래서
> **방향 calibration 상수(`front_offset` 등)는 지금은 잠정값**이다.
> - calibration 관련 값은 반드시 **`config.yaml`에만** 두고 코드에 박지 않는다.
> - 재조정이 쉽도록 **캘리브레이션 자체 테스트 스크립트**를 만들어 둔다.
> - **케이스 조립 → 최종 테스트 → 상수 재조정**을 정식 단계로 남긴다(Phase 2, Phase 8).

전체 8단계(Phase 0~7) + 케이스 후 마무리(Phase 8).

---

## Phase 0 — 준비/확인 (코드 쓰기 전)
막힘의 대부분이 여기서 갈린다. 안 되는 걸 만들기 전에 환경부터.
- `pyusb` 설치 여부 확인 (없으면 CLAUDE.md대로 상의 후 설치). PySide6는 이미 있음.
- USB 제어 권한: pyusb로 ReSpeaker 접근 되는지. 안 되면 udev 규칙(권장) 또는 임시 sudo.
- 디스플레이: PySide6 창이 뜨는 환경인지(DISPLAY/Wayland).
- 주언 자료 읽기: `docs/13-doa-calibration.md` + `config.yaml` `doa:`.
- ✅ 검증: 위 4개 OK.

## Phase 1 — DOA 각도 읽기 (`doa.py` 최소 기능)
- pyusb로 ReSpeaker(XVF-3000)의 **DOAANGLE** 읽기. **출처 명기(§9)**:
  `respeaker/usb_4_mic_array`의 `tuning.py`. `config.doa`의 vendor_id/product_id 사용.
- `DoaTracker.current()` → raw 각도(0~359°).
- ✅ 검증: 자체 테스트로 마이크 주위를 돌며 말하면 각도가 바뀌는지 콘솔 출력.

## Phase 2 — 좌표 변환 + 평활화 + 측정
- `front_offset`로 화면 각도 변환(앞=0°, 시계방향): `screen_angle = (front_offset - mic_angle) % 360`.
- `require_voice`: 목소리 있을 때만 갱신. `smoothing(0.3)` 지수이동평균으로 떨림 제거.
- **측정 코드(§8 DOA 오차)**: 실제 방향 vs 추정 방향(도).
- **캘리브레이션 자체 테스트**를 만들어 둔다(케이스 후 재조정에 재사용).
- ✅ 검증: 값이 안정적이고 방향이 맞음. (단, 케이스 전이라 front_offset은 잠정)

## Phase 3 — UI 뼈대 (`ui/app.py` 최소 창)
- PySide6 전체화면 창(`config.ui`: font_size 36, max_lines 3).
- `show_caption(text, ...)` → 최신 N줄 표시. `run()` 이벤트 루프.
- ⚠️ 단일패스라 `tentative` 구분 불필요 — 최종 자막만.
- ✅ 검증: 창이 뜨고 테스트 문장이 보임.

## Phase 4 — 방향 표시 (누가·어디서)
- 화살표/나침반으로 angle 표시. `show_caption(text, angle)`의 angle 반영.
- ✅ 검증: 방향 바뀌면 화살표가 돎.

## Phase 5 — 말하기 입력 (기능 ⑥ 연결부)
- 텍스트 입력창 + 엔터/버튼 → `self.on_speak(text)`. (실제 발화는 주언 speaker.py)
- ✅ 검증: 콜백 호출 확인. 터치로도 입력되는지.

## Phase 6 — 통합 (`main.py` 한 화면, §10)
- 자막 + 방향 + 말하기를 한 화면에. main.py는 이미 배선됨.
- ⚠️ 메모리 주의: STT(small)+UI+TTS 동시 = 8GB 공유메모리 빠듯. OOM 모니터링.
- ✅ 검증: 말하면 자막+방향 동시, 타이핑하면 발화.

## Phase 7 — 측정 마무리 (§8)
- 자막 지연(말 끝→화면), DOA 오차 숫자화.
- ✅ 검증: 지표 측정됨.

## Phase 8 — 케이스 조립 후 최종 캘리브레이션 (마이크를 케이스에 고정한 뒤)
- 케이스에 넣어 "앞" 방향을 물리적으로 확정.
- Phase 2의 캘리브레이션 자체 테스트로 **`front_offset` 등 상수 재측정 → config 갱신**.
- ✅ 검증: 실제 케이스 상태에서 앞/좌/우/뒤 방향이 화면과 일치.
