import imaplib
import email
from email.header import decode_header


def decode_header_value(header):
    if header is None:
        return ""
    decoded_parts = decode_header(header)
    result = ""
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            charset = charset or "utf-8"
            try:
                result += part.decode(charset, errors="ignore")
            except LookupError:
                result += part.decode("utf-8", errors="ignore")
        else:
            result += part
    return result


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


def receive(email, password, url="imap.yandex.com", port=993, latest=None):
    mail = imaplib.IMAP4_SSL(url, port)
    mail.login(email, password)
    mail.select("INBOX")
    status, message_ids_bytes = mail.search(None, "ALL")
    if status != "OK":
        mail.logout()
        return []
    
    id_list = message_ids_bytes[0].split()

    if latest is not None:
        latest_bytes = str(latest).encode()
        try:
            indx = id_list.index(latest_bytes)
            id_list = id_list[indx + 1:]
        except ValueError:
            pass

    emails = []
    for i in id_list:
        status, msg_data = mail.fetch(i, "(RFC822)")
        if status != "OK":
            continue
        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)
        from_ = decode_header_value(msg.get("From"))
        subject = decode_header_value(msg.get("Subject"))
        date = msg.get("Date", "")
        body = get_text_from_email(msg)
        emails.append({"id": i.decode(),
                       "from": from_,
                       "subject": subject,
                       "date": date,
                       "body": body})
    mail.close()
    mail.logout()
    return emails