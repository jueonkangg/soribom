"""기본 진단 로그에서 마지막 세션의 수치·오류를 요약한다. 추가 패키지 없이 실행한다."""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import statistics


def summarize(rows):
    if not rows:
        return "진단 기록이 없습니다."
    session = rows[-1]["session"]
    rows = [row for row in rows if row.get("session") == session]
    resources = [row for row in rows if row["event"] == "resources"]
    captions = [row for row in rows if row["event"] == "caption"]
    events = Counter(row["event"] for row in rows)
    lines = [f"세션: {session}", f"기록 범위: {rows[0]['time']} ~ {rows[-1]['time']}"]
    ended = [row for row in rows if row["event"] == "session_end"]
    lines.append("종료: " + ("정상" if ended and ended[-1].get("clean") else
                            "비정상 종료 기록" if ended else "종료 기록 없음 (실행 중·강제 종료 가능)"))
    if not any(row["event"] == "session_start" for row in rows):
        lines.append("주의: 앞부분 기록이 순환 삭제되어 전체 세션 결과가 아닙니다.")
    for key, title in [("rss_kib", "앱 RSS"), ("capture_rss_kib", "녹음 RSS"),
                       ("available_kib", "시스템 가용 메모리")]:
        values = [row[key] for row in resources if isinstance(row.get(key), (int, float))]
        if values:
            lines.append(f"{title} MiB: 처음 {values[0]/1024:.1f}, 마지막 {values[-1]/1024:.1f}, "
                         f"최소 {min(values)/1024:.1f}, 최대 {max(values)/1024:.1f}")
    lines.append(f"자막 처리 {len(captions)}건, 빈 결과 {sum(not row.get('has_text') for row in captions)}건")
    for key, title in [("duration_s", "전사·게시 처리"), ("stt_duration_s", "전사만"), ("inference_wait_s", "공유 추론 대기"), ("speech_age_s", "발화 끝→전사 시작"),
                       ("dispatch_delay_s", "발화 끝→UI 전달"), ("audio_s", "전사 오디오 길이")]:
        values = sorted(row[key] for row in captions if isinstance(row.get(key), (int, float)))
        if values:
            lines.append(f"{title} 초: 중앙 {statistics.median(values):.3f}, "
                         f"95백분위 {values[math.ceil(len(values)*0.95)-1]:.3f}, 최대 {max(values):.3f}")
    for key in ["queue_dropped_blocks", "queue_overflows", "stale_input_blocks", "stale_results", "audio_gaps", "callback_jitters", "capture_overflows", "pipe_dropped_blocks", "utterance_dropped", "mic_starts", "dropped_log_events"]:
        values = [row[key] for row in rows if isinstance(row.get(key), (int, float))]
        if values:
            lines.append(f"{key}: {max(values)}")
    for key in ["no_speech_filtered", "low_confidence_filtered", "echo_filtered"]:
        lines.append(f"{key}: {sum(row.get(key, 0) for row in captions)} 세그먼트")
    lines.append(f"마이크 장애 {events['mic_failure']}건, 수동 재시도 {events['retry']}건")
    failures = Counter(row.get("failure_reason", "unknown") for row in rows if row["event"] == "mic_failure")
    for reason, count in failures.items():
        lines.append(f"마이크 장애 원인 {reason}: {count}건")
    tts = [row for row in rows if row["event"] == "tts_end"]
    lines.append(f"말하기 완료 {len(tts)}건, 실패 {sum(not row.get('success') for row in tts)}건")
    for event, title in [("tts_synthesis", "말하기 합성"), ("tts_playback", "말하기 요청→재생 제출")]:
        values = [row["duration_s"] for row in rows if row["event"] == event and "duration_s" in row]
        if values:
            lines.append(f"{title} 초: 중앙 {statistics.median(values):.3f}, 최대 {max(values):.3f}")
    errors = Counter((row.get("stage", row["event"]), row["error_type"])
                     for row in rows if "error_type" in row)
    for (stage, error), count in errors.items():
        lines.append(f"오류 {stage}/{error}: {count}건")
    categories = Counter((row.get("operation", "unknown"), row.get("error_category", "unknown"))
                         for row in rows if row["event"] == "error")
    for (operation, category), count in categories.items():
        lines.append(f"오류 위치/분류 {operation}/{category}: {count}건")
    for stage in ["caption", "tts"]:
        values = [row['duration_s'] for row in rows if row['event'] == 'inference_wait' and row.get('stage') == stage]
        if values:
            lines.append(f"추론 대기 {stage} 초: 중앙 {statistics.median(values):.3f}, 최대 {max(values):.3f}")
    lines.append(f"기록 저장 실패: {sum(row['event'] == 'note_save' and not row.get('success') for row in rows)}건")
    lines.append("RSS는 공유 GPU 전체 사용량이 아니며, UI 전달·재생 제출은 실제 화면·소리 시작 시각이 아닙니다.")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", type=Path,
                        default=Path(__file__).resolve().parents[1] / "diagnostics")
    args = parser.parse_args()
    backups = [path for path in args.directory.glob("runtime.jsonl.*") if path.suffix[1:].isdigit()]
    backups.sort(key=lambda path: int(path.suffix[1:]), reverse=True)
    paths = backups + [args.directory / "runtime.jsonl"]
    rows = []
    malformed = 0
    for path in paths:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
                if isinstance(row, dict) and all(key in row for key in ["session", "time", "event"]):
                    rows.append(row)
                else:
                    malformed += 1
            except json.JSONDecodeError:
                malformed += 1
    print(summarize(rows))
    if malformed:
        print(f"읽지 못한 행 {malformed}개 (강제 종료·파일 손상 가능)")


if __name__ == "__main__":
    main()
