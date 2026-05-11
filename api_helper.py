import imaplib
import email
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


def receive(email_addr, password, url="imap.yandex.com", port=993, latest_uid=None):
    mail = imaplib.IMAP4_SSL(url, port)
    mail.login(email_addr, password)
    mail.select("INBOX")
    if latest_uid is not None:
        search_criteria = f'(UID {latest_uid + 1}:*) SUBJECT "MESSAGE"'
    else:
        search_criteria = 'SUBJECT "MESSAGE"'
    status, message_ids = mail.uid('search', None, search_criteria)
    if status != 'OK':
        mail.logout()
        return [], latest_uid or 0
    uid_list = message_ids[0].split()
    if not uid_list:
        mail.logout()
        return [], latest_uid or 0
    bodies = []
    max_uid = latest_uid or 0
    for uid in uid_list:
        status, msg_data = mail.uid('fetch', uid, "(RFC822)")
        if status != 'OK':
            continue
        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)
        body = get_text_from_email(msg)
        bodies.append(body)
        uid_int = int(uid)
        if uid_int > max_uid:
            max_uid = uid_int
    mail.close()
    mail.logout()
    return bodies, max_uid