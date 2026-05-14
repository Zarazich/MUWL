import os
import base64
import struct
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
import hashlib
from cryptography.fernet import Fernet


def _derive_key(
    password: str, salt: bytes, length: int = 32, iterations: int = 100000
) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=length,
        salt=salt,
        iterations=iterations,
        backend=default_backend(),
    )
    return kdf.derive(password.encode("utf-8"))


def _encrypt_part(plaintext: str, password: str) -> bytes:
    salt = os.urandom(16)
    nonce = os.urandom(12)
    key = _derive_key(password, salt)
    cipher = Cipher(algorithms.AES(key), modes.GCM(nonce), backend=default_backend())
    encryptor = cipher.encryptor()
    plain_bytes = plaintext.encode("utf-8")
    ciphertext = encryptor.update(plain_bytes) + encryptor.finalize()
    tag = encryptor.tag
    return salt + nonce + tag + ciphertext


def _decrypt_part(encrypted_data: bytes, password: str) -> str:
    if len(encrypted_data) < 44:
        raise ValueError("Invalid encrypted data")

    salt = encrypted_data[:16]
    nonce = encrypted_data[16:28]
    tag = encrypted_data[28:44]
    ciphertext = encrypted_data[44:]
    key = _derive_key(password, salt)
    cipher = Cipher(
        algorithms.AES(key), modes.GCM(nonce, tag), backend=default_backend()
    )
    decryptor = cipher.decryptor()
    plain_bytes = decryptor.update(ciphertext) + decryptor.finalize()
    return plain_bytes.decode("utf-8")


def encrypt_message(
    message_key: str, route_key: str, chat_id: str, message: str
) -> str:
    encrypted_route = _encrypt_part(chat_id, route_key)
    encrypted_message = _encrypt_part(message, message_key)
    route_len = len(encrypted_route)
    packet = struct.pack(
        f"!I{route_len}s{len(encrypted_message)}s",
        route_len,
        encrypted_route,
        encrypted_message,
    )
    return base64.b64encode(packet).decode("utf-8")


def validate_route(
    route_key: str, expected_chat_id: str, encrypted_packet_b64: str
) -> bool:
    try:
        packet = base64.b64decode(encrypted_packet_b64)

        if len(packet) < 4:
            return False

        route_len = struct.unpack("!I", packet[:4])[0]

        if len(packet) < 4 + route_len:
            return False

        encrypted_route = packet[4 : 4 + route_len]
        chat_id = _decrypt_part(encrypted_route, route_key)
        return chat_id == expected_chat_id
    except Exception:
        return False


def decrypt_message(route_key: str, message_key: str, encrypted_packet_b64: str) -> str:
    packet = base64.b64decode(encrypted_packet_b64)

    if len(packet) < 4:
        raise ValueError("Packet too short")

    route_len = struct.unpack("!I", packet[:4])[0]

    if len(packet) < 4 + route_len:
        raise ValueError("Packet corrupted")

    encrypted_route = packet[4 : 4 + route_len]
    encrypted_message = packet[4 + route_len :]
    _decrypt_part(encrypted_route, route_key)
    message = _decrypt_part(encrypted_message, message_key)
    return message


def hash_password(password: str) -> str:
    algorithm = hashes.SHA256()
    digest = hashes.Hash(algorithm, backend=default_backend())
    digest.update(password.encode("utf-8"))
    return str(digest.finalize().hex())


def encrypt(password: str, data: bytes) -> bytes:
    key = hashlib.sha256(password.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(key)
    cipher = Fernet(fernet_key)
    return cipher.encrypt(data)


def decrypt(password: str, encrypted: bytes) -> bytes:
    key = hashlib.sha256(password.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(key)
    cipher = Fernet(fernet_key)
    return cipher.decrypt(encrypted)
