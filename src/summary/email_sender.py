"""사용자가 선택한 수업 기록만 Gmail SMTP로 보낸다. 추가 패키지는 필요 없다."""
import configparser
import re
import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path


CONFIG_PATH = Path(__file__).resolve().parents[2] / ".email.local.ini"
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465
SMTP_TIMEOUT = 15


class NoteEmailError(Exception):
    """화면에 그대로 보여도 비밀번호나 서버 응답을 노출하지 않는 오류."""


def validate_recipient(address: str) -> str:
    """표시 이름·여러 수신자·줄바꿈 없이 이메일 주소 하나만 받는다."""
    if "\r" in address or "\n" in address:
        raise NoteEmailError("받는 이메일 주소 하나만 입력해주세요.")
    address = address.strip()
    pattern = r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~.-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,}"
    if len(address) > 254 or not re.fullmatch(pattern, address):
        raise NoteEmailError("받는 이메일 주소를 확인해주세요. 예: student@gmail.com")
    local, domain = address.rsplit("@", 1)
    if len(local) > 64 or local.startswith(".") or local.endswith(".") or ".." in address:
        raise NoteEmailError("받는 이메일 주소를 확인해주세요.")
    if any(part.startswith("-") or part.endswith("-") for part in domain.split(".")):
        raise NoteEmailError("받는 이메일 주소를 확인해주세요.")
    return address


def load_account(path: Path = CONFIG_PATH) -> tuple:
    """비밀번호는 커밋하지 않는 로컬 설정에서 발송할 때만 읽는다."""
    try:
        if path.stat().st_mode & 0o077:
            raise NoteEmailError("메일 설정 파일 권한을 확인해주세요. chmod 600 .email.local.ini")
        config = configparser.ConfigParser(interpolation=None)
        with path.open(encoding="utf-8") as f:
            config.read_file(f)
        sender = config.get("gmail", "address").strip()
        password = config.get("gmail", "app_password").replace(" ", "").strip()
    except FileNotFoundError:
        raise NoteEmailError("발송 계정이 설정되지 않았습니다. 터미널에서 .venv/bin/python scripts/setup_note_email.py를 실행해주세요.") from None
    except (OSError, configparser.Error, UnicodeError):
        raise NoteEmailError("메일 설정 파일을 읽을 수 없습니다. 계정 설정 도구를 다시 실행해주세요.") from None
    try:
        validate_recipient(sender)
    except NoteEmailError:
        raise NoteEmailError("발송 계정 주소를 확인해주세요. 계정 설정 도구를 다시 실행해주세요.") from None
    if not sender.lower().endswith("@gmail.com"):
        raise NoteEmailError("발송 계정은 @gmail.com으로 끝나는 Gmail 주소를 입력해주세요.")
    if not re.fullmatch(r"[A-Za-z0-9]{16}", password):
        raise NoteEmailError("앱 비밀번호 형식이 맞지 않습니다. Google 계정에서 발급한 16자리 앱 비밀번호를 입력해주세요. 일반 Gmail 로그인 비밀번호는 사용하지 않습니다.")
    return sender, password


def build_message(sender: str, recipient: str, transcript: str, now=None) -> EmailMessage:
    now = now or datetime.now()
    message = EmailMessage()
    message["From"] = f"소리봄 <{sender}>"
    message["To"] = recipient
    message["Subject"] = f"소리봄 수업 기록 · {now:%Y-%m-%d %H:%M}"
    content = transcript.rstrip("\n") + "\n"
    message.set_content(content, charset="utf-8")
    message.add_attachment(
        content, subtype="plain", charset="utf-8",
        filename=f"소리봄_수업기록_{now:%Y-%m-%d_%H%M%S}.txt",
    )
    return message


def send_note(recipient: str, transcript: str, config_path: Path = CONFIG_PATH) -> None:
    recipient = validate_recipient(recipient)
    if not transcript.strip():
        raise NoteEmailError("아직 보낼 수업 기록이 없습니다.")
    sender, password = load_account(config_path)
    message = build_message(sender, recipient, transcript)
    smtp = None
    submitting = False
    try:
        smtp = smtplib.SMTP_SSL(
            SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT,
            context=ssl.create_default_context(),
        )
        smtp.login(sender, password)
        submitting = True
        refused = smtp.send_message(message, from_addr=sender, to_addrs=[recipient])
        if refused:
            raise NoteEmailError("받는 주소가 메일 서버에서 거부되었습니다. 주소를 확인해주세요.")
    except smtplib.SMTPAuthenticationError:
        raise NoteEmailError("발송 계정 인증에 실패했습니다. Gmail 앱 비밀번호를 확인해주세요.") from None
    except smtplib.SMTPRecipientsRefused:
        raise NoteEmailError("받는 주소가 메일 서버에서 거부되었습니다. 주소를 확인해주세요.") from None
    except (smtplib.SMTPDataError, smtplib.SMTPSenderRefused):
        raise NoteEmailError("메일 서버가 전송을 거부했습니다. 발송 계정과 메일 크기를 확인해주세요.") from None
    except ssl.SSLError:
        if submitting:
            raise NoteEmailError("발송 여부를 확인할 수 없습니다. 메일함을 확인한 뒤 다시 시도하세요.") from None
        raise NoteEmailError("보안 연결에 실패했습니다. 컴퓨터의 날짜·시간과 네트워크를 확인해주세요.") from None
    except (OSError, smtplib.SMTPException):
        if submitting:
            raise NoteEmailError("발송 여부를 확인할 수 없습니다. 메일함을 확인한 뒤 다시 시도하세요.") from None
        raise NoteEmailError("메일 서버에 연결할 수 없습니다. 인터넷 연결을 확인한 뒤 다시 시도해주세요.") from None
    finally:
        # 서버가 수락한 뒤 연결 종료 오류가 나도 실패로 표시해 중복 발송하지 않는다.
        if smtp is not None:
            try:
                smtp.close()
            except OSError:
                pass
