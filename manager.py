import cryptography
import json
from cryptohelper import encrypt_message, encrypt
from cryptohelper import decrypt_message, decrypt
from cryptohelper import validate_route
from cryptohelper import hash_password
from api_helper import receive
import random


class manager:
    def __init__(self, path_to_conf):
        self.pwd = path_to_conf 
        self.ready = False
        try:
            with open(path_to_conf, "r") as f:
                self.data = json.load(f)
            self.ready = True
        except Exception:
            self.data = {"hash": None,
                         "chats": [],
                         "emails": []}

    def create_chat(self, password, name):
        if hash_password(password) != self.data["hash"] and not (password is None):
            print(1, password, self.data["hash"] == hash_password(password))
            return
        if name == "" or name is None or name in [j["name"] for j in self.data["chats"]]:
            return
        data = {}
        data["name"] = name
        data["routekey"] = self.create_key()
        enckey = self.create_key()
        data["enckey"] = encrypt(password, enckey.encode()).decode()
        data["route"] = self.create_key()
        data["emails"] = []
        data["messages"] = []
        data["unreaden"] = False
        self.data["chats"].append(data.copy())
        self.save_config()
        return enckey, data["routekey"], data["route"]

    def create_key(self) -> str:
        str0 = "qwertyuiopaasdfghjklzxcvbnm1234567890"
        str0 = list(str0)
        return "".join([str0[random.randint(0, len(str0) - 1)] for i in range(10)])
    
    def setup(self, password):
        if not self.data["hash"] is None:
            return
        self.data["hash"] = hash_password(password)
        self.ready = True
        self.save_config()
    
    def setup_email(self, email, apikey):
        if email in [i["email"] for i in self.data["emails"]]:
            return False
        self.data["emails"].append({"email": email,
                                    "apikey": apikey,
                                    "lastuid": None})
        self.save_config()
        return True

    def save_config(self):
        if not self.ready:
            return
        with open(self.pwd, "w") as f:
            json.dump(self.data, f)
    
    def receive(self):
        for y, i in enumerate(self.data["emails"]):
            if 1:
                maybeMessage, lastuid = receive(i["email"], i["apikey"], latest_uid=i["lastuid"])
                self.data["emails"][y]["new"] = True
                self.data["emails"][y]["lastuid"] = lastuid
                for x, j in enumerate(self.data["chats"]):
                    for message in maybeMessage:
                        message = message.strip()
                        if validate_route(j["routekey"], j["route"], message):
                            print("RECEIVED FROM")
                            self.data["chats"][x]["messages"].append(message)
                            self.data["chats"][x]["new"] = True
                        else:
                            print([message])
        self.save_config()