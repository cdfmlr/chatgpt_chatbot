# chatgpt

A interface to chat with ChatGPT based on [acheong08/ChatGPT](https://github.com/acheong08/ChatGPT).

## Installation

```sh
poetry shell
poetry install
```

## gRPC Usage

### 运行

```sh
$ cd <本项目的根目录，即本 README 文件所在目录>
$ ls
README.md      chatgpt        poetry.lock    pyproject.toml tests
$ poetry run python chatgpt [--grpc localhost:50052]  # --help 查看帮助
```

### 参数

```sh
usage: chatgpt [-h] [--grpc GRPC] [--http HTTP] [--debug]

ChatGPTChatbot server: gRPC or HTTP. 
Default is gRPC. If --http is specified, gRPC will be ignored.

Environment variables:

GRPC_REFLECTION:  if set to True, gRPC server will enable server reflection.
                  --debug will set this to True automatically.
                  (default: False)
CHATGPT_COOLDOWN: the cooldown time (in seconds) between two consecutive 
                  requests to a ChatGPT instance (access_token)
                  (default: 75)

options:
  -h, --help   show this help message and exit
  --grpc GRPC  gRPC server address: host:port (default localhost:50052)
  --http HTTP  HTTP server address: e.g. localhost:9006. If specified, gRPC will be ignored. (default is not to start the HTTP server)
  --debug      Enable debug mode: logging level = DEBUG; gRPC += server_reflection (default is False)
```

### 请求

```sh
$ grpcurl -d '{"config": "{\"version\": 3, \"api_key\": \"sk-xxxx\"}", "initial_prompt": "你好"}' -plaintext localhost:50052 muvtuber.chatbot.v2.ChatbotService.NewSession
{
  "sessionId": "2617613c-9f20-4d6c-b47e-1622392a134e",
  "initialResponse": "你好！我很高兴能和你交流。有什么我可以帮助你的吗？"
}

$ grpcurl -d '{"session_id": "2617613c-9f20-4d6c-b47e-1622392a134e", "prompt": "hello!!"}' -plaintext localhost:50052 muvtuber.chatbot.v2.ChatbotService.Chat
{
  "response": "Hello! How can I assist you today?"
}

$ grpcurl -d '{"session_id": "2617613c-9f20-4d6c-b47e-1622392a134e"}' -plaintext localhost:50052 muvtuber.chatbot.v2.ChatbotService.DeleteSession
{
  "sessionId": "2617613c-9f20-4d6c-b47e-1622392a134e"
}
```

### errors

```md
- NewSession
    - INVALID_ARGUMENT: version & access_token|api_key is required
    - RESOURCE_EXHAUSTED: TooManySessions (该系统内 MultiChatGPT 的最大会话数限制)
    - UNAVAILABLE: ChatGPTError (向 ChatGPT 请求 initial_prompt 时出错)
- Chat
    - INVALID_ARGUMENT: session_id / prompt is required
    - NOT_FOUND: SessionNotFound (会话不存在)
    - UNAVAILABLE: ChatGPTError (向 ChatGPT 请求 prompt 时出错)
    - RESOURCE_EXHAUSTED: CooldownException (该系统内 ChatGPT 频繁请求限制)
- DeleteSession
    - INVALID_ARGUMENT: session_id is required
    - NOT_FOUND: SessionNotFound (会话不存在)
```

我不会 Python 自动文档生成啊。。。很烦。

## HTTP Usage

```sh
poetry run python chatgpt/httpapi.py
# or
poetry run python chatgpt --http localhost:9006
```

```sh
$ curl -X POST localhost:9006/renew -d '{"access_token": "eyJhb***99A"}' -i
HTTP/1.1 200 OK
Content-Type: text/plain; charset=utf-8
Content-Length: 2
Date: Sat, 18 Feb 2023 07:03:26 GMT
Server: Python/3.11 aiohttp/3.8.4

ok
$ curl -X POST localhost:9006/ask -d '{"prompt": "你好"}'
HTTP/1.1 200 OK
Content-Type: text/plain; charset=utf-8
Content-Length: 45
Date: Sat, 18 Feb 2023 07:03:39 GMT
Server: Python/3.11 aiohttp/3.8.4

你好！有什么我可以帮助你的吗？
```

## TODO

- [x] Add multi access tokens support, to avoid the 'Too many requests in 1 hour. Try again later.'
- [ ] Add tests
