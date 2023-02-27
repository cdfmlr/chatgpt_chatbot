# chatgpt

A interface to chat with ChatGPT based on [acheong08/ChatGPT](https://github.com/acheong08/ChatGPT).

## Installation

```sh
poetry shell
poetry install
```

## Run

```sh
python chatgpt/httpapi.py
```

## Usage

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

- [ ] Add multi access tokens support, to avoid the 'Too many requests in 1 hour. Try again later.'
- [ ] Add tests
