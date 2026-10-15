#!/usr/bin/env bash
# 사용자 서비스로 실행해 Codex가 부모 프로세스가 되는 것을 피한다.
set -eu
REPO="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"
export DISPLAY="${DISPLAY:-:1}"
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"
export PYTHONUNBUFFERED=1

# 개발·검증에서는 도구 종료를 생략한다. 바탕화면 실행은 메모리 확보가 기본이다.
ARGS=(--close-development-tools)
if [[ "${1:-}" == "--keep-development-tools" ]]; then
  ARGS=()
fi
ENV_ARGS=(--setenv="DISPLAY=$DISPLAY" --setenv="QT_QPA_PLATFORM=$QT_QPA_PLATFORM"
          --setenv=PYTHONUNBUFFERED=1)
if [[ -n "${XAUTHORITY:-}" ]]; then
  ENV_ARGS+=(--setenv="XAUTHORITY=$XAUTHORITY")
fi
systemd-run --user --quiet --collect --unit="soribom-$(date +%s%N)-$$" \
  --working-directory="$REPO" --property=StandardOutput=null --property=StandardError=null \
  "${ENV_ARGS[@]}" "$REPO/.venv/bin/python" "$REPO/src/main.py" "${ARGS[@]}"
