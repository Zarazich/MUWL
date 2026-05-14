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
            try:
                maybeMessage, lastuid = receive(i["email"], i["apikey"], latest_uid=i["lastuid"])
                self.data["emails"][y]["unreaden"] = True
                self.data["emails"][y]["lastuid"] = lastuid
                print(lastuid)
                for x, j in enumerate(self.data["chats"]):
                    for message in maybeMessage:
                        if validate_route(j["routekey"], j["route"], message[0]):
                            if (message[0], 0) not in self.data["chats"][x]["messages"]:
                                self.data["chats"][x]["messages"].append((message[0], 0))
                                if message[1] not in self.data["chats"][x]["emails"]:
                                    self.data["chats"][x]["emails"].append((message[1]))
                                else:
                                    print("email in email list")
                                self.data["chats"][x]["unreaden"] = True
                                print(f"receive new to { self.data['chats'][x]['name']}, FROM {message[1]}")
                            else:
                                print("receive copy")
                        else:
                            print("refused")
                            print(j["routekey"], j["route"])
            except Exception as e:
                print(e)
        self.save_config()
    
    def update(self):
        data = []
        for i in self.data["chats"]:
            if i["unreaden"]:
                data.append(i["name"])
        return data
    
    def get_messages_from_chat(self, name_of_chat, password):
        if self.data["hash"] == hash_password(password) and not self.data["hash"] is None:
            chat = [(x, i) for x, i in enumerate(self.data["chats"]) if i["name"] == name_of_chat]
            if len(chat) == 0:
                return None
            else:
                chat = chat[0]
                index = chat[0]
                chat = chat[1]
                self.data["chats"][index]["unreaden"] = False
                messages = chat["messages"]
                try:
                    enc_key = decrypt(password, chat["enckey"]).decode()
                    messages = list(map(lambda x: (decrypt_message(chat["routekey"], enc_key, x[0]), x[1]), messages))
                    self.save_config()
                    return (messages, name_of_chat)
                except Exception as e:
                    print(e)
        return None
    
    def send_message(self, name_of_chat, message, password):
        pass


