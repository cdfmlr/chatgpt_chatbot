from dataclasses import dataclass
import logging
import os
from typing import Dict
import uuid
from warnings import warn
from revChatGPT.V1 import Chatbot
import threading
from datetime import datetime

from cooldown import cooldown

# Proxy server Rate limit: 25 requests per 10 seconds (per IP)
# OpenAI rate limit: 50 requests per hour on free accounts. You can get around it with multi-account cycling
# Plus accounts has around 150 requests per hour rate limit
#
# 所以大概最多也就 3 个号轮询 => 每 30 秒一次请求

# Cooldown: a decorator to limit the frequency of function calls


class ChatGPT:
    def __init__(self, config={'access_token': 'your access token', 'initial_prompt': 'your initial prompt'}):
        """ChatGPT with config: {access_token, initial_prompt}"""
        self.chatbot = Chatbot(config=config)
        self.lock = threading.Lock()  # for self.chatbot

        q = config.get('initial_prompt', None)
        if q:
            a = self.ask(q)
            print(f'{datetime.now()} ChatGPT initial ask: {q} -> {a}')
            self.initial_response = a
        else:
            self.initial_response = None

    @cooldown(os.getenv("CHATGPT_COOLDOWN", 75))
    def ask(self, prompt) -> str:  # raises Exception
        """Ask ChatGPT with prompt, return response text

        Raises:
            ChatGPTError: ChatGPT error
        """
        response = None

        with self.lock:
            for data in self.chatbot.ask(prompt):
                response = data

        if response == None:
            raise ChatGPTError("ChatGPT response is None")

        if response.get("detail", None) != None:  # error
            print(f'{datetime.now()} ChatGPT ask error: {response}')
            raise ChatGPTError(str(response))

        resp = response.get("message", None)
        if resp == None:
            raise ChatGPTError("ChatGPT response is None")
        return resp

    def renew(self, access_token: str):
        """Deprecated"""
        warn("ChatGPT.renew is deprecated", DeprecationWarning)

        with self.lock:
            self.chatbot = Chatbot(config={"access_token": access_token})


# ChatGPTConfig: {access_token, initial_prompt}
@dataclass
class ChatGPTConfig:
    access_token: str
    initial_prompt: str


MAX_SESSIONS = 10

# MultiChatGPT: {session_id: ChatGPT}:
#  - new(config) -> session_id
#  - ask(session_id, prompt) -> response
#  - delete(session_id)


class MultiChatGPT:
    """MultiChatGPT: {session_id: ChatGPT}"""

    def __init__(self):
        self.chatgpt: Dict[str, ChatGPT] = {}  # XXX: 话说这东西线程安全嘛

    def new(self, config: ChatGPTConfig) -> str:  # raises TooManySessions, ChatGPTError
        """Create new ChatGPT session, return session_id

        session_id is a uuid4 string

        Raises:
            TooManySessions: Too many sessions
            ChatGPTError: ChatGPT error when asking initial prompt
        """
        if len(self.chatgpt) >= MAX_SESSIONS:
            raise TooManySessions(MAX_SESSIONS)

        session_id = str(uuid.uuid4())
        self.chatgpt[session_id] = ChatGPT(config={
            "access_token": config.access_token,
            "initial_prompt": config.initial_prompt
        })
        return session_id

    def ask(self, session_id: str, prompt: str) -> str:  # raises ChatGPTError
        """Ask ChatGPT with session_id and prompt, return response text

        Raises:
            SessionNotFound: Session not found
            ChatGPTError: ChatGPT error when asking
        """
        if session_id not in self.chatgpt:
            raise SessionNotFound(session_id)

        resp = self.chatgpt[session_id].ask(prompt)

        return resp

    def delete(self, session_id: str):  # raises SessionNotFound
        """Delete ChatGPT session

        Raises:
            SessionNotFound: Session not found
        """
        if session_id not in self.chatgpt:
            raise SessionNotFound(session_id)

        del self.chatgpt[session_id]


# Exceptions: TooManySessions, SessionNotFound, ChatGPTError

class TooManySessions(Exception):
    def __init__(self, max_sessions: int):
        self.max_sessions = max_sessions
        self.message = f"Too many sessions, max {max_sessions}"
        super().__init__(self.message)


class SessionNotFound(Exception):
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.message = f"Session {session_id} not found"
        super().__init__(self.message)


class ChatGPTError(Exception):
    def __init__(self, message=""):
        self.message = message
        super().__init__(self.message)
