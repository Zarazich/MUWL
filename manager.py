import cryptography
import json 


class manager:
    def __init__(self, path_to_conf : str):
        with open(path_to_conf, "r") as f:
            self.inp = json.load(f)
            self.hash_passwd = int(inp["hash"])
            self.chats = inp["chats"]