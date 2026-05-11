import json
import os
import random
import base64
from typing import List, Tuple, Dict

from api_helper import receive as imap_receive
from cryptohelper import (
    encrypt_message, decrypt_message, validate_route,
    hash_password, verify_password,
    encrypt, decrypt
)


class ManagerError(Exception):
    pass


class NotSetupError(ManagerError):
    pass


class InvalidPasswordError(ManagerError):
    pass


class Manager:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> dict:
        default_config = {
            "hash": None,
            "emails": [],
            "last_uids": {},
            "chats": []
        }
        if not os.path.exists(self.config_path):
            return default_config
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            for key, value in default_config.items():
                if key not in config:
                    config[key] = value
            return config
        except (json.JSONDecodeError, IOError):
            backup_path = self.config_path + ".backup"
            try:
                os.rename(self.config_path, backup_path)
            except Exception:
                pass
            return default_config

    def _save_config(self):
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)

    def setup(self, password: str):
        if self.config["hash"] is not None:
            raise ManagerError("Master password already set")
        self.config["hash"] = hash_password(password)
        self._save_config()

    def valid_passwd(self, password: str) -> bool:
        if self.config["hash"] is None:
            return False
        return verify_password(password, self.config["hash"])

    def create_key(self) -> str:
        chars = "qwertyuiopaasdfghjklzxcvbnm1234567890"
        return ''.join(random.choice(chars) for _ in range(16))

    def create_chat(self, master_password: str) -> Tuple[str, str]:
        if self.config["hash"] is None:
            raise NotSetupError("Manager not set up. Call setup() first.")
        if not self.valid_passwd(master_password):
            raise InvalidPasswordError("Wrong master password")
        indx = self.create_key()
        indxkey = self.create_key()
        message_key = self.create_key()
        encrypted_key = encrypt(master_password, message_key.encode('utf-8'))
        key_enc = base64.b64encode(encrypted_key).decode('utf-8')
        new_chat = {
            "indx": indx,
            "indxkey": indxkey,
            "key_enc": key_enc,
            "messages": [],
            "new": False
        }
        self.config["chats"].append(new_chat)
        self._save_config()
        return indxkey, indx

    def receive(self, master_password: str) -> None:
        if self.config["hash"] is None:
            raise NotSetupError("Manager not set up")
        if not self.valid_passwd(master_password):
            raise InvalidPasswordError("Wrong master password")
        chat_keys = []
        for chat in self.config["chats"]:
            indx = chat["indx"]
            indxkey = chat["indxkey"]
            enc_key = base64.b64decode(chat["key_enc"])
            msg_key = decrypt(master_password, enc_key).decode('utf-8')
            chat_keys.append((indx, indxkey, msg_key))
        for email, apikey in self.config["emails"]:
            last_uid = self.config["last_uids"].get(email, 0)
            bodies, new_uid = imap_receive(email, apikey, latest_uid=last_uid)
            self.config["last_uids"][email] = new_uid
            for packet_b64 in bodies:
                for indx, indxkey, msg_key in chat_keys:
                    if validate_route(indxkey, indx, packet_b64):
                        plaintext = decrypt_message(indxkey, msg_key, packet_b64)
                        enc_for_storage = encrypt(master_password, plaintext.encode('utf-8'))
                        enc_for_storage_b64 = base64.b64encode(enc_for_storage).decode('utf-8')
                        for chat in self.config["chats"]:
                            if chat["indx"] == indx:
                                chat["messages"].append(enc_for_storage_b64)
                                chat["new"] = True
                                break
                        break
        self._save_config()