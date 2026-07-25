#!/usr/bin/env bash
# 소리봄 통합 앱 실행 런처 (바탕화면 아이콘 → 이 스크립트)
#
# 하는 일:
#   1) 메모리 확보 — 브라우저를 종료한다. (Jetson 은 CPU/GPU 가 8GB 를 공유해서,
#      브라우저가 떠 있으면 GPU 초기화가 실패(OOM)할 수 있다.)
#   2) 전체화면 Qt 앱이라 DISPLAY 를 지정한다.
#   3) 저장소 루트에서 통합 앱(src/main.py)을 실행한다. 종료 후 창을 열어 둬(로그 확인).
set -u

REPO="/data2/code/soribom"
export DISPLAY="${DISPLAY:-:1}"
export QT_QPA_PLATFORM=xcb
export PYTHONUNBUFFERED=1   # 진행 메시지가 즉시 보이게(버퍼링 방지)

echo "======================================"
echo "        소리봄 (SoundSight)           "
echo "======================================"

echo "[1/3] 메모리 확보 — 브라우저를 종료합니다..."
pkill -f chrome    2>/dev/null
pkill -f chromium  2>/dev/null
pkill -f firefox   2>/dev/null
sleep 1
echo "      현재 여유 메모리:"
free -m | awk 'NR==1{print "      "$0} /Mem/{print "      "$0}'

echo "[2/3] 준비 확인 — 마이크(ReSpeaker USB)와 블루투스 스피커 연결을 확인하세요."
echo "                마이크 윗면(LED·구멍)이 케이스 밖으로 보이게 두세요(방향 정확도)."

echo "[3/3] 소리봄을 시작합니다. 종료하려면 앱 화면에서 ESC 를 누르세요."
echo "      (자막·말하기 모델을 올리는 동안 5~10초쯤 화면이 안 보일 수 있습니다. 기다리세요.)"
echo "--------------------------------------"

cd "$REPO" || { echo "[오류] 저장소를 찾을 수 없습니다: $REPO"; read -r -p "엔터로 닫기..."; exit 1; }

.venv/bin/python src/main.py
CODE=$?

echo "--------------------------------------"
echo "소리봄이 종료되었습니다. (종료 코드 $CODE)"
if [ "$CODE" -ne 0 ]; then
  echo "[알림] 오류로 종료된 것 같습니다. 위의 메시지를 확인하세요."
  echo "       메모리 부족(GPU)이면 다른 무거운 프로그램을 끄고 다시 실행하세요."
fi
read -r -p "이 창을 닫으려면 엔터를 누르세요..."
