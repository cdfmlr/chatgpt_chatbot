from revChatGPT.V1 import Chatbot
import threading
from datetime import datetime


class ChatGPT:
    def __init__(self, config={'access_token': 'your access token'}):
        self.chatbot = Chatbot(config=config)
        self.lock = threading.Lock()  # for self.chatbot

    def ask(self, prompt) -> str | None:  # raises Exception
        response = None

        with self.lock:
            for data in self.chatbot.ask(prompt):
                response = data

        try:
            if response.get("detail", None) != None:  # error
                print(f'{datetime.now()} ChatGPT ask error: {response}')
                raise Exception(str(response))
            return response.get("message", None)
        except AttributeError:
            return None

    def renew(self, access_token: str):
        with self.lock:
            self.chatbot = Chatbot(config={"access_token": access_token})
