"""시작할 때만 출력과 무선 절전을 점검한다. Wi-Fi와 Bluetooth 전체를 끊지 않는다."""
import json
import os
import re
import subprocess
import time


def _run(command, timeout=2):
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=timeout,
                              env={**os.environ, "LC_ALL": "C"})
    except (OSError, subprocess.TimeoutExpired):
        return None


def _listing(kind):
    result = _run(["pactl", "-f", "json", "list", kind])
    if result is None or result.returncode:
        return None
    try:
        data = json.loads(result.stdout)
        return data if isinstance(data, list) else None
    except ValueError:
        return None


def _wifi_check(cancelled):
    result = _run(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device"])
    interfaces = []
    if result is not None and result.returncode == 0:
        for line in result.stdout.splitlines():
            parts = line.split(":")
            if len(parts) == 3 and parts[1:] == ["wifi", "connected"]:
                interfaces.append(parts[0])
    all_off = bool(interfaces)
    for interface in interfaces:
        if cancelled():
            return bool(interfaces), False
        state = _run(["iw", "dev", interface, "get", "power_save"])
        if state is None or "power save: off" not in state.stdout.lower():
            # 현재 연결의 이 속성만 바꾼다. 접속을 내려 원격 작업을 끊지 않는다.
            _run(["nmcli", "device", "modify", interface, "802-11-wireless.powersave", "2"], 3)
            state = _run(["iw", "dev", interface, "get", "power_save"])
        all_off = all_off and state is not None and state.returncode == 0 and "power save: off" in state.stdout.lower()
    return bool(interfaces), bool(all_off)


def prepare_system_output(cfg, cancelled=lambda: False):
    result = {"wifi_checked": False, "wifi_power_save_off": False,
              "speaker_ready": False, "audio_profile_reset": False,
              "audio_recovery_skipped": False}
    if cancelled():
        return result
    result["wifi_checked"], result["wifi_power_save_off"] = _wifi_check(cancelled)
    address = cfg.get("bluetooth_address", "")
    sink = cfg.get("output_sink")
    if not re.fullmatch(r"[0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5}", address) or not sink or cancelled():
        return result
    card_name = "bluez_card." + address.upper().replace(":", "_")
    sinks = _listing("sinks")
    if sinks is None:
        return result
    target = next((item for item in sinks if item.get("name") == sink), None)
    saved_mute = target.get("mute") if target else None
    saved_volume = []
    restore_settings = False
    for channel in (target.get("volume", {}) if target else {}).values():
        value = channel.get("value")
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            saved_volume.append(str(value))
    if target is None:
        # 출력이 없을 때만 한 번 연결한다. 건강한 Bluetooth 링크는 끊지 않는다.
        _run(["bluetoothctl", "--timeout", "5", "connect", address], 6)
    cards = _listing("cards")
    card = next((item for item in cards or [] if item.get("name") == card_name), None)
    if card is not None and not cancelled():
        inputs = _listing("sink-inputs")
        sinks = _listing("sinks")
        target = next((item for item in sinks or [] if item.get("name") == sink), None)
        # 다른 앱의 소리나 확인할 수 없는 재생 상태는 강제로 중단하지 않는다.
        prefix = "bluez_output." + address.upper().replace(":", "_") + "."
        target_indices = {item.get("index") for item in sinks or []
                          if item.get("name", "").startswith(prefix)}
        busy = inputs is None or sinks is None or any(
            item.get("sink") in target_indices for item in inputs or [])
        profiles = card.get("profiles", {})
        profile = card.get("active_profile", "")
        if not profile.startswith("a2dp-sink"):
            profile = next((name for name in profiles if name.startswith("a2dp-sink")), "")
        if busy or not profile:
            result["audio_recovery_skipped"] = True
        else:
            # off 직후 취소되어도 반드시 A2DP 복원을 시도해 무음 상태를 남기지 않는다.
            restore_settings = True
            stopped = _run(["pactl", "set-card-profile", card_name, "off"])
            restored = _run(["pactl", "set-card-profile", card_name, profile])
            result["audio_profile_reset"] = bool(stopped is not None and stopped.returncode == 0
                                                  and restored is not None and restored.returncode == 0)
            if restored is None or restored.returncode:
                _run(["pactl", "set-card-profile", card_name, profile])
    deadline = time.monotonic() + 2
    while not cancelled():
        sinks = _listing("sinks")
        if any(item.get("name") == sink for item in sinks or []):
            result["speaker_ready"] = True
            # 출력 재생성으로 음량이 초기화되어 갑자기 커지는 일을 피한다.
            if restore_settings and saved_volume:
                _run(["pactl", "set-sink-volume", sink, *saved_volume])
            if restore_settings and isinstance(saved_mute, bool):
                _run(["pactl", "set-sink-mute", sink, "1" if saved_mute else "0"])
            _run(["pactl", "set-default-sink", sink])
            break
        if time.monotonic() >= deadline:
            break
        time.sleep(0.1)
    return result
