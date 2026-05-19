import cryptography
import json
from cryptohelper import encrypt_message, encrypt
from cryptohelper import decrypt_message, decrypt
from cryptohelper import validate_route
from cryptohelper import hash_password
from api_helper import receive, send
import random
from random import choice


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
                         "emails": [],
                         "name": "USER"}

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
        return (enckey, data["routekey"], data["route"], self.data["name"], choice(self.data["emails"]))

    def create_key(self) -> str:
        str0 = "qwertyuiopaasdfghjklzxcvbnm1234567890"
        str0 = list(str0)
        return "".join([str0[random.randint(0, len(str0) - 1)] for i in range(10)])
    
    def setup(self, password, name):
        if not self.data["hash"] is None:
            return
        self.data["hash"] = hash_password(password)
        self.data["name"] = name
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
    
    def send_message(self, name_of_chat, message, email_to, email_from, password):
        if self.data["hash"] == hash_password(password) and not self.data["hash"] is None:
            chat = [(x, i) for x, i in enumerate(self.data["chats"]) if i["name"] == name_of_chat]
            if len(chat) == 0:
                return None
            email = [i for i in self.data["emails"] if i["email"] == email_from]
            if len(email) == 0:
                return None
            email = email[0]
            chat = chat[0]
            indx = chat[0]
            chat = chat[1]
            enc_key = decrypt(password, chat["enckey"]).decode()
            try:
                encmessage = encrypt_message(enc_key, chat["routekey"], chat["route"], message)
                send(email["email"], email_to, email["apikey"], encmessage)
                print("ОТПРАВЛЕН", message, email_from, email_to)
                self.data["chats"][indx]["messages"].append((encmessage, 1))
                self.save_config()
            except Exception:
                pass
    
    def add_chat_from(self, password, data, from_file=False, file=None):
        if (hash_password(password) == self.data["hash"] or not data["hash"] is None):
            return False
        try:
            if from_file:
                with open(file, "r") as f:
                    data = json.load(f)
        except Exception as e:
            print(e)
            return False
        if not ("enckey" in data.keys() and 
                "routekey" in data.keys() and
                "route" in data.keys() and
                "email" in data.keys() and
                "name" in data.keys()):
            return False
        enckey = data["enckey"]
        routekey = data["routekey"]
        route = data["route"]
        email = [data["email"]]
        name = data["name"]
        data = {}
        data["name"] = name
        data["routekey"] = routekey
        data["enckey"] = encrypt(password, enckey.encode()).decode()
        data["route"] = route
        data["emails"] = [email]
        data["messages"] = []
        data["unreaden"] = False
        self.data["chats"].append(data)
        return True

    def valid_passwd(self, password):
        hashed = hash_password(password)
        stored = self.data["hash"]
        return hashed == stored

    def decrypt_chat_key(self, name_of_chat, password):
        if self.data.get("hash") is None:
            return None
        if hash_password(password) != self.data["hash"]:
            return None
        chat = None
        for c in self.data.get("chats", []):
            if c.get("name") == name_of_chat:
                chat = c
                break
        if not chat:
            return None
        try:
            enc_key = decrypt(password, chat["enckey"]).decode()
            return enc_key
        except Exception as e:
            print(f"decrypt_chat_key error: {e}")
            return None

    def get_messages_from_chat(self, name_of_chat, password):
            if (
                self.data["hash"] == hash_password(password)
                and not self.data["hash"] is None
            ):
                chat = [
                    (x, i)
                    for x, i in enumerate(self.data["chats"])
                    if i["name"] == name_of_chat
                ]

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
                        messages = list(
                            map(
                                lambda x: (
                                    decrypt_message(chat["routekey"], enc_key, x[0]),
                                    x[1],
                                ),
                                messages,
                            )
                        )
                        self.save_config()
                        return (messages, name_of_chat)
                    except Exception as e:
                        print(e)

            return None