import imaplib
import email
import smtplib
from email.mime.text import MIMEText
from email import encoders
from email.header import decode_header


def get_text_from_email(msg):
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()

            if content_type == "text/plain":
                payload = part.get_payload(decode=True)
                charset = part.get_content_charset() or "utf-8"
                return payload.decode(charset, errors="ignore")

        return ""
    else:
        payload = msg.get_payload(decode=True)
        charset = msg.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="ignore")


def send(
    email_from,
    email_to,
    apikey,
    encrypted_message,
    smtp_server="smtp.yandex.com",
    smtp_port=465,
):
    msg = MIMEText(encrypted_message, "plain", "utf-8")
    msg["Subject"] = "MESSAGE"
    msg["From"] = email_from
    msg["To"] = email_to
    encoders.encode_base64(msg)

    with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
        server.login(email_from, apikey)
        server.send_message(msg)

    return True


def receive(email_addr, password, url="imap.yandex.com", port=993, latest_uid=None):
    mail = imaplib.IMAP4_SSL(url, port)
    mail.login(email_addr, password)
    mail.select("INBOX")

    if latest_uid is not None:
        search_criteria = f'(UID {latest_uid + 1}:*) SUBJECT "MESSAGE"'
    else:
        search_criteria = 'SUBJECT "MESSAGE"'

    status, message_ids = mail.uid("search", None, search_criteria)

    if status != "OK":
        mail.logout()
        return [], latest_uid or 0

    uid_list = message_ids[0].split()

    if not uid_list:
        mail.logout()
        return [], latest_uid or 0

    messages = []  # список кортежей (body, from_email)
    max_uid = latest_uid or 0

    for uid in uid_list:
        status, msg_data = mail.uid("fetch", uid, "(RFC822)")

        if status != "OK":
            continue

        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)
        body = get_text_from_email(msg)
        from_addr = msg.get("From")  # или email.utils.parseaddr(msg['From'])[1]
        messages.append((body, from_addr))
        uid_int = int(uid)

        if uid_int > max_uid:
            max_uid = uid_int
    mail.close()
    mail.logout()
    return messages, max_uid
