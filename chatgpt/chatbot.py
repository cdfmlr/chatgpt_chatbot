import logging
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
import os
from enum import Enum
from typing import Dict
import uuid
from warnings import warn
from revChatGPT.V1 import Chatbot as ChatbotV1
from revChatGPT.V3 import Chatbot as ChatbotV3
import threading
from datetime import datetime

from cooldown import cooldown

# Proxy server Rate limit: 25 requests per 10 seconds (per IP)
# OpenAI rate limit: 50 requests per hour on free accounts. You can get around it with multi-account cycling
# Plus accounts has around 150 requests per hour rate limit
#
# 所以大概最多也就 3 个号轮询 => 每 30 秒一次请求

# Cooldown: a decorator to limit the frequency of function calls


class ChatGPT(metaclass=ABCMeta):
    @abstractmethod
    def ask(self, session_id, prompt):
        """Ask ChatGPT with prompt, return response text

        Raises:
            ChatGPTError: ChatGPT error
        """
        pass


# V1 Standard ChatGPT
# Update 2023/03/09 9:50AM - No longer functional
class ChatGPTv1(ChatGPT):
    def __init__(self, config={'access_token': 'your access token', 'initial_prompt': 'your initial prompt'}):
        """ChatGPT with config: {access_token, initial_prompt}"""
        self.chatbot = ChatbotV1(config=config)
        self.lock = threading.Lock()  # for self.chatbot

        q = config.get('initial_prompt', None)
        if q:
            a = self.ask('', q)
            print(f'{datetime.now()} ChatGPT initial ask: {q} -> {a}')
            self.initial_response = a
        else:
            self.initial_response = None

    @cooldown(os.getenv("CHATGPT_COOLDOWN", 75))
    def ask(self, session_id, prompt) -> str:  # raises Exception
        """Ask ChatGPT with prompt, return response text

        - session_id: unused

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
            self.chatbot = ChatbotV1(config={"access_token": access_token})


# V3 Official Chat API
# Paid
class ChatGPTv3(ChatGPT):
    def __init__(self, config={'api_key': 'your api key', 'initial_prompt': 'your initial prompt'}):
        self.chatbot = ChatbotV3(api_key=config.get('api_key', ''))
        self.lock = threading.Lock()  # for self.chatbot

        q = config.get('initial_prompt', None)
        if q:
            a = self.ask('', q)
            logging.info(f'ChatGPT initial ask: {q} -> {a}')
            self.initial_response = a
        else:
            self.initial_response = None


    # Rate Limits: 20 RPM / 40,000 TPM
    # https://platform.openai.com/docs/guides/rate-limits/overview
    # 主要是价格w
    # gpt-3.5-turbo: $0.002 / 1K tokens
    @cooldown(os.getenv("CHATGPT_V3_COOLDOWN", 30))
    def ask(self, session_id, prompt) -> str:  # raises Exception
        """Ask ChatGPT with prompt, return response text

        - session_id: unused

        Raises:
            ChatGPTError: ChatGPT error
        """
        response: str | None = None

        try:
            with self.lock:
                response = self.chatbot.ask(prompt)
        except Exception as e:
            logging.warning(f"ChatGPT ask error: {e}")
            raise ChatGPTError(str(e))

        if not response:
            raise ChatGPTError("ChatGPT response is None")

        return response


class APIVersion(Enum):
    V1 = 1
    V3 = 3

    def get_ChatGPT_class(self):
        if self == self.V1:
            return ChatGPTv1
        elif self == self.V3:
            return ChatGPTv3


# ChatGPTConfig: {access_token, initial_prompt}
@dataclass
class ChatGPTConfig:
    version: APIVersion
    access_token: str
    initial_prompt: str


MAX_SESSIONS = 10


# MultiChatGPT: {session_id: ChatGPT}:
#  - new(config) -> session_id
#  - ask(session_id, prompt) -> response
#  - delete(session_id)
class MultiChatGPT(ChatGPT):
    """MultiChatGPT: {session_id: ChatGPT}"""

    def __init__(self):
        self.chatgpt: Dict[str, ChatGPT] = {}  # XXX: 话说这东西线程安全嘛

    def new(self, config: ChatGPTConfig) -> str:  # raises TooManySessions, ChatGPTError
        """Create new ChatGPT session, return session_id

        session_id is an uuid4 string

        Raises:
            TooManySessions: Too many sessions
            ChatGPTError: ChatGPT error when asking initial prompt
        """
        if len(self.chatgpt) >= MAX_SESSIONS:
            raise TooManySessions(MAX_SESSIONS)

        session_id = str(uuid.uuid4())

        if config.version == APIVersion.V3:
            self.chatgpt[session_id] = ChatGPTv3(config={
                "api_key": config.access_token,
                "initial_prompt": config.initial_prompt
            })
        else:
            self.chatgpt[session_id] = ChatGPTv1(config={
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

        resp = self.chatgpt[session_id].ask(session_id, prompt)

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
