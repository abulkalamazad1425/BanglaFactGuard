from email import message_from_string
from email.header import decode_header

import pytest

from app.core.config import EmailSettings
from app.core.exceptions import EmailDeliveryError
from app.shared import email_service as module
from app.shared.email_service import EmailService


class FakeSMTP:
    sent: list = []
    fail = False

    def __init__(self, host, port, timeout):
        self.calls = [("connect", host, port)]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        FakeSMTP.sent.append(self.calls)

    def starttls(self):
        self.calls.append(("starttls",))

    def login(self, user, password):
        self.calls.append(("login", user, password))

    def sendmail(self, sender, to, raw):
        if FakeSMTP.fail:
            raise OSError("smtp down")
        self.calls.append(("sendmail", sender, to, message_from_string(raw)))


@pytest.fixture
def smtp(monkeypatch):
    FakeSMTP.sent, FakeSMTP.fail = [], False
    monkeypatch.setattr(module.smtplib, "SMTP", FakeSMTP)
    return FakeSMTP


def service(**email) -> EmailService:
    svc = EmailService()
    svc._settings = EmailSettings(**email)
    return svc


CONFIGURED = dict(smtp_host="smtp.test", smtp_user=" user@test ", smtp_password="abcd efgh", website_url="https://bfg.test/")


async def test_unconfigured_otp_is_logged_not_sent_but_result_email_is_refused(smtp):
    svc = service(smtp_host="")
    await svc.send_otp_email(to_email="a@example.com", otp="123456")
    assert smtp.sent == []
    with pytest.raises(EmailDeliveryError):
        await svc.send_result_email(to_email="a@example.com", submission_id="s1", headline="h", verdict="Real")


async def test_otp_is_sent_over_tls_with_a_cleaned_credential(smtp):
    await service(**CONFIGURED).send_otp_email(to_email="a@example.com", otp="123456")
    [calls] = smtp.sent
    assert calls[1] == ("starttls",) and calls[2] == ("login", "user@test", "abcdefgh")
    message = calls[3][3]
    assert calls[3][2] == ["a@example.com"] and "123456" in message.get_payload(decode=True).decode()


async def test_smtp_failure_is_a_typed_delivery_error(smtp):
    smtp.fail = True
    with pytest.raises(EmailDeliveryError):
        await service(**CONFIGURED).send_otp_email(to_email="a@example.com", otp="1")


async def test_result_email_links_to_the_decision_with_a_headline_preview(smtp):
    await service(**CONFIGURED).send_result_email(
        to_email="a@example.com", submission_id="s1", headline="এক দুই তিন চার পাঁচ ছয়", verdict="Fake"
    )
    message = smtp.sent[0][-1][3]
    subject = "".join(
        part.decode(enc or "ascii") if isinstance(part, bytes) else part
        for part, enc in decode_header(message["Subject"])
    )
    body = message.get_payload(decode=True).decode()
    assert subject == "Final decision ready: এক দুই তিন চার পাঁচ..."
    assert "Final decision: Fake" in body and "https://bfg.test/verify/s1" in body
