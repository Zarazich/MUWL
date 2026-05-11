import cryptography
import json
from cryptohelper import encrypt_message, encrypt
from cryptohelper import decrypt_message, decrypt
from cryptohelper import validate_route
from cryptohelper import hash_password
from random import randint, choice


class manager:
    def __init__(self, path_to_conf : str):
        self.waiting = []
        try:
            with open(path_to_conf, "r") as f:
                self.inp = json.load(f)
                self.hash_passwd = int(inp["hash"])
                self.chats = inp["chats"]
                self.emails = inp["emails"]
                for i in self.chats:
                    if not (i["indx"] is None):
                        self.waiting.append((i["indxkey"], i["indx"]))

    def create_chat(self, passwd):
        data = {}
        data["indxkey"] = self.create_key()
        data["indx"] = self.create_key()
        data["messages"] = []
        data["messageskey"] = encrypt(passwd, self.create_key.encode()).decode()
        data["email"] = choice(self.emails)["email"]
        self.chats.append(data)
        return data

    def create_key(self) -> str;
        str0 = "qwertyuiopaasdfghjklzxcvbnm1234567890"
        str0 = list(str0)
        return "".join([str0[random.randint(0, len(str0) - 1)] for i in range(10)])
    
