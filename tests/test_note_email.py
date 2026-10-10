"""실제 네트워크·메일 발송 없이 기록 내보내기를 검증한다."""
import configparser
from datetime import datetime
from email import policy
from email.parser import BytesParser
from pathlib import Path
import smtplib
import sys
import tempfile
import unittest
import importlib.util
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from summary.email_sender import (
    NoteEmailError, build_message, load_account, send_note, validate_recipient,
)
from summary.notes import NoteBuilder


class NoteEmailTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.config = Path(self.directory.name) / "account.ini"
        cfg = configparser.ConfigParser()
        cfg["gmail"] = {"address": "soundsight.test@gmail.com", "app_password": "abcdefghijklmnop"}
        with self.config.open("w", encoding="utf-8") as f:
            cfg.write(f)
        self.config.chmod(0o600)
        self.transcript = "수업 기록 · 2026-10-10 15:00\n\n• 광합성에 대해 배웁니다."

    def test_single_address_validation(self):
        self.assertEqual(validate_recipient(" student+note@example.com "), "student+note@example.com")
        for value in ["", "student", "a@b", "a@b.com,c@d.com", "학생@example.com", "Name <a@b.com>", "a@b.com\n", ".a@b.com", "a..b@c.com", "a@-b.com"]:
            with self.subTest(value=value), self.assertRaises(NoteEmailError):
                validate_recipient(value)

    def test_utf8_body_and_attachment_match_after_serializing(self):
        msg = build_message("sender@gmail.com", "student@example.com", self.transcript, datetime(2026, 10, 10, 15, 0, 1))
        parsed = BytesParser(policy=policy.default).parsebytes(msg.as_bytes())
        self.assertEqual(parsed["To"], "student@example.com")
        self.assertEqual(parsed["Subject"], "소리봄 수업 기록 · 2026-10-10 15:00")
        body = parsed.get_body(preferencelist=("plain",)).get_content()
        attachments = list(parsed.iter_attachments())
        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0].get_filename(), "소리봄_수업기록_2026-10-10_150001.txt")
        self.assertEqual(body, attachments[0].get_content())
        self.assertEqual(body, self.transcript + "\n")

    def test_snapshot_does_not_change_when_new_speech_arrives(self):
        notes = NoteBuilder({"output_dir": self.directory.name})
        self.assertEqual(notes.build_email_transcript(), "")
        notes.add("첫 문장", 0)
        snapshot = notes.build_email_transcript()
        notes.add("다음 문장", 90)
        self.assertNotIn("다음 문장", snapshot)
        self.assertIn("다음 문장", notes.build_summary())

    def test_settings_permissions_missing_and_invalid(self):
        self.assertEqual(load_account(self.config)[0], "soundsight.test@gmail.com")
        with self.assertRaises(NoteEmailError):
            load_account(self.config.with_name("missing.ini"))
        self.config.chmod(0o644)
        with self.assertRaises(NoteEmailError):
            load_account(self.config)
        self.config.chmod(0o600)
        self.config.write_text("[gmail]\naddress=sender@gmail.com\napp_password=wrong\n")
        with self.assertRaises(NoteEmailError):
            load_account(self.config)

    @patch("summary.email_sender.smtplib.SMTP_SSL")
    def test_preflight_never_connects_for_empty_or_invalid_input(self, smtp):
        for address, text in [("bad", self.transcript), ("a@b.com", " ")]:
            with self.assertRaises(NoteEmailError):
                send_note(address, text, self.config)
        with self.assertRaises(NoteEmailError):
            send_note("student@example.com", self.transcript, self.config.with_name("missing.ini"))
        smtp.assert_not_called()

    @patch("summary.email_sender.smtplib.SMTP_SSL")
    def test_send_uses_verified_tls_and_closes_connection(self, smtp):
        connection = smtp.return_value
        connection.send_message.return_value = {}
        send_note("student@example.com", self.transcript, self.config)
        self.assertEqual(smtp.call_args.args, ("smtp.gmail.com", 465))
        self.assertEqual(smtp.call_args.kwargs["timeout"], 15)
        self.assertTrue(smtp.call_args.kwargs["context"].check_hostname)
        connection.login.assert_called_once()
        connection.send_message.assert_called_once()
        connection.close.assert_called_once()

    @patch("summary.email_sender.smtplib.SMTP_SSL")
    def test_errors_are_safe_and_uncertain_submission_is_distinguished(self, smtp):
        smtp.side_effect = TimeoutError("sensitive server detail")
        with self.assertRaisesRegex(NoteEmailError, "인터넷 연결"):
            send_note("student@example.com", self.transcript, self.config)
        smtp.side_effect = None
        connection = smtp.return_value
        connection.login.side_effect = smtplib.SMTPAuthenticationError(535, b"secret detail")
        with self.assertRaisesRegex(NoteEmailError, "인증에 실패"):
            send_note("student@example.com", self.transcript, self.config)
        connection.login.side_effect = None
        for error, expected in [
            (smtplib.SMTPRecipientsRefused({"student@example.com": (550, b"no")}), "주소가"),
            (smtplib.SMTPDataError(552, b"secret"), "전송을 거부"),
            (TimeoutError("secret"), "발송 여부를 확인할 수 없습니다"),
        ]:
            connection.send_message.side_effect = error
            with self.subTest(error=type(error)), self.assertRaisesRegex(NoteEmailError, expected):
                send_note("student@example.com", self.transcript, self.config)

    def setup_tool(self):
        script = Path(__file__).resolve().parents[1] / "scripts" / "setup_note_email.py"
        spec = importlib.util.spec_from_file_location("setup_note_email", script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.REPO = Path(self.directory.name)
        module.CONFIG_PATH = self.config
        return module

    @patch("builtins.print")
    def test_setup_tool_saves_with_private_permissions_without_sending(self, output):
        tool = self.setup_tool()
        with patch("builtins.input", side_effect=["y", "new.sender@gmail.com"]), patch.object(tool.getpass, "getpass", return_value="aaaa bbbb cccc dddd"), patch("summary.email_sender.smtplib.SMTP_SSL") as smtp:
            tool.main()
        self.assertEqual(load_account(self.config), ("new.sender@gmail.com", "aaaabbbbccccdddd"))
        self.assertEqual(self.config.stat().st_mode & 0o777, 0o600)
        self.assertEqual(list(Path(self.directory.name).glob(".email.local.*.tmp")), [])
        self.assertNotIn("aaaabbbbccccdddd", str(output.call_args_list))
        smtp.assert_not_called()

    @patch("builtins.print")
    def test_failed_setup_keeps_previous_account_and_removes_temporary_file(self, output):
        tool = self.setup_tool()
        previous = self.config.read_bytes()
        with patch("builtins.input", side_effect=["y", "new.sender@gmail.com"]), patch.object(tool.getpass, "getpass", return_value="wrong"), self.assertRaises(NoteEmailError):
            tool.main()
        self.assertEqual(self.config.read_bytes(), previous)
        self.assertEqual(list(Path(self.directory.name).glob(".email.local.*.tmp")), [])

    @patch("builtins.print")
    def test_setup_distinguishes_password_and_permission_errors(self, output):
        tool = self.setup_tool()
        with patch("builtins.input", side_effect=["y", "new.sender@gmail.com"]), patch.object(tool.getpass, "getpass", return_value="wrong"):
            self.assertEqual(tool.run(), 1)
        self.assertIn("16자리 앱 비밀번호", str(output.call_args_list))
        output.reset_mock()
        with patch.object(tool, "main", side_effect=PermissionError("sensitive detail")):
            self.assertEqual(tool.run(), 1)
        self.assertIn("저장할 권한", str(output.call_args_list))
        self.assertNotIn("sensitive detail", str(output.call_args_list))


if __name__ == "__main__":
    unittest.main()
