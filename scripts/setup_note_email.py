"""전용 Gmail 계정을 로컬에 설정한다. 비밀번호는 터미널에 표시하지 않는다."""
import configparser
import getpass
import os
from pathlib import Path
import sys
import tempfile

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from summary.email_sender import CONFIG_PATH, NoteEmailError, load_account, validate_recipient


def main() -> None:
    print("소리봄 발송용 Gmail 설정 — 메일은 보내지 않습니다.")
    print("2단계 인증을 켜고 Gmail 앱 비밀번호를 준비하세요. 일반 로그인 비밀번호는 사용하지 않습니다.")
    print("안내: https://support.google.com/accounts/answer/185833?hl=ko")
    if CONFIG_PATH.exists():
        answer = input("기존 발송 계정 설정을 교체할까요? (y/N): ").strip().lower()
        if answer != "y":
            print("설정을 유지했습니다.")
            return
    address = validate_recipient(input("발송용 Gmail 주소: "))
    password = getpass.getpass("Gmail 앱 비밀번호 (화면에 표시되지 않음): ").replace(" ", "").strip()
    config = configparser.ConfigParser(interpolation=None)
    config["gmail"] = {"address": address, "app_password": password}
    temporary = None
    try:
        # 새 파일도 생성 순간부터 600 권한이다. 검사 후 교체해 기존 설정을 보호한다.
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=REPO, prefix=".email.local.", suffix=".tmp", delete=False) as f:
            temporary = Path(f.name)
            os.fchmod(f.fileno(), 0o600)
            config.write(f)
        load_account(temporary)
        temporary.replace(CONFIG_PATH)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    print("설정 완료. 소리봄의 '노트 보내기'에서 실제 발송을 확인하세요.")


def run() -> int:
    try:
        main()
    except NoteEmailError as error:
        print(f"설정 실패: {error}", file=sys.stderr)
        return 1
    except PermissionError:
        print("설정 파일을 저장할 권한이 없습니다. 프로젝트 폴더의 쓰기 권한을 Codex와 확인해주세요.", file=sys.stderr)
        return 1
    except OSError:
        print("설정 파일을 저장하지 못했습니다. 디스크 여유 공간과 저장 위치를 Codex와 확인해주세요.", file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print("\n설정을 취소했습니다.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(run())
