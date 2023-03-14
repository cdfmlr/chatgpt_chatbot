import logging
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
import os
from enum import Enum
import time
from typing import Dict
import uuid
from warnings import warn
from revChatGPT.V1 import Chatbot as ChatbotV1
from revChatGPT.V3 import Chatbot as ChatbotV3
import threading
from datetime import datetime
from threading import Timer
from cooldown import cooldown

# Proxy server Rate limit: 25 requests per 10 seconds (per IP)
# OpenAI rate limit: 50 requests per hour on free accounts. You can get around it with multi-account cycling
# Plus accounts has around 150 requests per hour rate limit
#
# 所以大概最多也就 3 个号轮询 => 每 30 秒一次请求

# Cooldown: a decorator to limit the frequency of function calls


class ChatGPT(metaclass=ABCMeta):
    @abstractmethod
    def ask(self, session_id, prompt, **kwargs):
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
            a = self.ask('', q, no_cooldown=True)
            print(f'{datetime.now()} ChatGPT initial ask: {q} -> {a}')
            self.initial_response = a
        else:
            self.initial_response = None

    @cooldown(int(os.getenv("CHATGPT_COOLDOWN", 75)))
    def ask(self, session_id, prompt, **kwargs) -> str:  # raises Exception
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
            a = self.ask('', q, no_cooldown=True)
            logging.info(f'ChatGPT initial ask: {q} -> {a}')
            self.initial_response = a
        else:
            self.initial_response = None

    # Rate Limits: 20 RPM / 40,000 TPM
    # https://platform.openai.com/docs/guides/rate-limits/overview
    # 主要是价格w
    # gpt-3.5-turbo: $0.002 / 1K tokens

    @cooldown(int(os.getenv("CHATGPT_V3_COOLDOWN", 30)))
    def ask(self, session_id, prompt, **kwargs) -> str:  # raises Exception
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


class ChatGPTProxy(ChatGPT):
    """ChatGPTProxy is a ChatGPT used by MultiChatGPT."""

    def __init__(self, session_id: str, config: ChatGPTConfig, create_now=True):
        """A ChatGPTProxy is represent to a session of MultiChatGPT.
        (Maybe I should rename it ChatGPTSession.)


        ChatGPTProxy saves the config and use it to create a new 
        underlying ChatGTP instance.

        The ask() call will be proxy to the underlying ChatGPT.

        renew() drops the underlying ChatGPT and create a new one
        using the saved config. This is designed to kill a ChatGPT
        session (to the openai's api), but keeps the session (w.r.t. 
        the MultiChatGPT & the ChatbotServer).
        It avoids loooong conversations (which holding tons of history context)
        accumulates and costs tokens ($0.002 / 1K tokens) over and over again.
        """
        self.session_id = session_id
        self.config = config

        self.initial_response = ""

        self.create_at = 0
        self.touch_at = 0

        if create_now:
            self.renew()

    def renew(self):
        """re-create the underlying (real) ChatGPT instance"""
        self.chatgpt = self._new_chatgpt(self.config)
        self.create_at = time.time()

    def is_timeout(self, timeout=900):
        """timeout: to be renew()"""
        return time.time() - self.create_at > timeout

    def is_zombie(self, timeout=1800):
        """zombie: do not renew()"""
        return time.time() - self.touch_at > timeout

    def _new_chatgpt(self, config: ChatGPTConfig) -> ChatGPT:
        """ChatGPT factory"""
        if config.version == APIVersion.V3:
            new_chatgpt = ChatGPTv3(config={
                "api_key": config.access_token,
                "initial_prompt": config.initial_prompt
            })
        else:
            new_chatgpt = ChatGPTv1(config={
                "access_token": config.access_token,
                "initial_prompt": config.initial_prompt
            })

        try:
            self.initial_response = new_chatgpt.initial_response or ""
        except Exception as e:
            logging.error(
                f"ChatGPTProxy._new_chatgpt failed to get initial_response: {e}")
        return new_chatgpt

    def ask(self, session_id, prompt, **kwargs):
        """ask the underlying (real) ChatGPT"""
        self.touch_at = time.time()
        return self.chatgpt.ask(session_id, prompt, **kwargs)


# MultiChatGPT: {session_id: ChatGPT}:
#  - new(config) -> session_id
#  - ask(session_id, prompt) -> response
#  - delete(session_id)
class MultiChatGPT(ChatGPT):
    """MultiChatGPT: {session_id: ChatGPT}"""

    def __init__(self):
        self.chatgpts: Dict[str, ChatGPTProxy] = {}  # XXX: 话说这东西线程安全嘛

        self.timeout = 900  # timeout in seconds: 15 min
        self.check_timeout_interval = 60  # interval time to check timeout session in sec

        Timer(self.check_timeout_interval, self.renew_timeout_sessions).start()

    def renew_timeout_sessions(self):
        now = time.time()
        for chatgpt in self.chatgpts.values():
            if chatgpt.is_zombie(timeout=self.timeout*2):
                logging.debug(f"MultiChatGPT: zombie chatgpt: {chatgpt.session_id}, skip renew.")
                continue
            if chatgpt.is_timeout(timeout=self.timeout):
                logging.info(f"MultiChatGPT: renew a timeout ChatGPT session {chatgpt.session_id}")
                chatgpt.renew()
        Timer(self.check_timeout_interval, self.renew_timeout_sessions).start()

    def clean_zombie_sessions(self):
        session_ids_to_del = []
        for chatgpt in self.chatgpts.values():
            if chatgpt.is_zombie(timeout=self.timeout*2):
                session_ids_to_del.append(chatgpt.session_id)
        logging.info(f"MultiChatGPT: delete zombie chatgpts: {session_ids_to_del}")
        for s in session_ids_to_del:
            self.delete(s)

    # raises TooManySessions, ChatGPTError
    def new_session(self, config: ChatGPTConfig) -> str:
        """Create new ChatGPT session, return session_id

        session_id is an uuid4 string

        Raises:
            TooManySessions: Too many sessions
            ChatGPTError: ChatGPT error when asking initial prompt
        """
        if len(self.chatgpts) >= MAX_SESSIONS:
            self.clean_zombie_sessions()
        if len(self.chatgpts) >= MAX_SESSIONS:
            raise TooManySessions(MAX_SESSIONS)

        session_id = str(uuid.uuid4())

        self.chatgpts[session_id] = ChatGPTProxy(
            session_id, config, create_now=True)

        return session_id

    def ask(self, session_id: str, prompt: str, **kwargs) -> str:  # raises ChatGPTError
        """Ask ChatGPT with session_id and prompt, return response text

        Raises:
            SessionNotFound: Session not found
            ChatGPTError: ChatGPT error when asking
        """
        if session_id not in self.chatgpts:
            raise SessionNotFound(session_id)

        resp = self.chatgpts[session_id].ask(session_id, prompt)

        return resp

    def delete(self, session_id: str):  # raises SessionNotFound
        """Delete ChatGPT session

        Raises:
            SessionNotFound: Session not found
        """
        if session_id not in self.chatgpts:
            raise SessionNotFound(session_id)

        del self.chatgpts[session_id]


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
