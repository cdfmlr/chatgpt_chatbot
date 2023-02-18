from datetime import datetime
from chatgpt import ChatGPT
import aiohttp
from aiohttp.web import Request, Response


class ChatGPTHTTPServer:
    def __init__(self, chatgpt: ChatGPT, host: str = "localhost", port: int = 9006):
        self.chatgpt = chatgpt
        self.host = host
        self.port = port

    async def handleAsk(self, request: Request):
        """ POST /ask
        {"prompt": "your prompt"}

        Response in code + text:

            200: "response"
            400 | 500: "error"
        """
        body = await request.json()


        prompt = body.get("prompt", None)
        if prompt == None:
            return aiohttp.web.Response(text="prompt is required", status=400)

        print(f'{datetime.now()} [POST /ask] asking ChatGPT: {prompt}') 

        try:
            response = self.chatgpt.ask(prompt)
            if response == None:
                return aiohttp.web.Response(text="error", status=500)
        except Exception as e:
            return aiohttp.web.Response(text=f"error: {e}", status=500)

        return aiohttp.web.Response(text=response)

    async def handleRenew(self, request):
        """ POST /renew
        {"access_token": "your access token"}
        """
        body = await request.json()

        access_token = body.get("access_token", None)
        if access_token == None:
            return aiohttp.web.Response(text="access_token is required", status=400)

        print(f'{datetime.now()} [POST /renew] renewing access token: {access_token[:5] + "***" + access_token[-5:]}')  

        self.chatgpt.renew(access_token)
        return aiohttp.web.Response(text="ok")

    def run(self):
        app = aiohttp.web.Application()

        app.add_routes([aiohttp.web.post("/ask", self.handleAsk)])
        app.add_routes([aiohttp.web.post("/renew", self.handleRenew)])

        aiohttp.web.run_app(app, host=self.host, port=self.port)


if __name__ == "__main__":
    chatgpt = ChatGPT()
    server = ChatGPTHTTPServer(chatgpt)
    server.run()
