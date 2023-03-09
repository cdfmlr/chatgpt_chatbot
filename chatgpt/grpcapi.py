import json
import logging
import os
from chatbot import MultiChatGPT, ChatGPTConfig, ChatGPTError, TooManySessions, SessionNotFound, APIVersion
from cooldown import CooldownException
from protos import chatbot_pb2, chatbot_pb2_grpc

import grpc
from concurrent import futures


class ChatGPTgRPCServer(chatbot_pb2_grpc.ChatbotServiceServicer):
    def __init__(self):
        self.multiChatGPT = MultiChatGPT()

    def NewSession(self, request, context):
        """NewSession creates a new session with ChatGPT.
        Input: access_token (string) and initial_prompt (string).
        Output: session_id (string).
        """
        try:
            c = request.config
            c = json.loads(c)
        except Exception as e:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(str(e))
            logging.warning('ChatGPTgRPCServer.NewSession: bad config')
            return chatbot_pb2.NewSessionResponse()

        config = ChatGPTConfig(
            version=APIVersion(c.get('version', None)),
            access_token=c.get('access_token', False) or c.get('api_key', False) or '',
            initial_prompt=request.initial_prompt)

        session_id = None
        try:
            session_id = self.multiChatGPT.new(config)
        except TooManySessions as e:
            context.set_code(grpc.StatusCode.RESOURCE_EXHAUSTED)
            context.set_details(str(e))
        except ChatGPTError as e:
            context.set_code(grpc.StatusCode.UNAVAILABLE)
            context.set_details(str(e))

        if context.code() != grpc.StatusCode.OK and context.code() != None:
            logging.warn(
                f'ChatGPTgRPCServer.NewSession: {context.code()}: {context.details()}')
        else:
            logging.info(
                f'ChatGPTgRPCServer.NewSession: (OK) session_id={session_id}')

        # TODO: 这个 initial_response 太恶心了，还是逐层传比较好吧
        return chatbot_pb2.NewSessionResponse(session_id=session_id, initial_response=self.multiChatGPT.chatgpt[session_id].initial_response)

    def Chat(self, request, context):
        """Chat sends a prompt to ChatGPT and receives a response.
        Input: session_id (string) and prompt (string).
        Output: response (string).
        """
        if not request.session_id:
            # raise ValueError('session_id is required')
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details('session_id is required')
            logging.warn('ChatGPTgRPCServer.Chat: session_id is required')
            return chatbot_pb2.ChatResponse()
        if not request.prompt:
            # raise ValueError('prompt is required')
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details('prompt is required')
            logging.warn('ChatGPTgRPCServer.Chat: prompt is required')
            return chatbot_pb2.ChatResponse()

        response = None
        try:
            response = self.multiChatGPT.ask(
                request.session_id, request.prompt)
        except SessionNotFound as e:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(str(e))
        except ChatGPTError as e:
            context.set_code(grpc.StatusCode.UNAVAILABLE)
            context.set_details(str(e))
        except CooldownException as e:
            context.set_code(grpc.StatusCode.RESOURCE_EXHAUSTED)
            context.set_details(str(e))

        if context.code() != grpc.StatusCode.OK and context.code() != None:
            logging.warn(
                f'ChatGPTgRPCServer.Chat: ({context.code()}) {context.details()}')
        else:
            logging.info(
                f'ChatGPTgRPCServer.Chat: (OK) {response}')

        return chatbot_pb2.ChatResponse(response=response)

    def DeleteSession(self, request, context):
        """DeleteSession deletes a session with ChatGPT.
        Input: session_id (string).
        Output: session_id (string).
        """
        if not request.session_id:
            # raise ValueError('session_id is required')
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details('session_id is required')
            logging.warn(
                'ChatGPTgRPCServer.DeleteSession: session_id is required')
            return chatbot_pb2.DeleteSessionResponse()

        try:
            self.multiChatGPT.delete(request.session_id)
        except SessionNotFound as e:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(str(e))

        if context.code() != grpc.StatusCode.OK and context.code() != None:
            logging.warn(
                f'ChatGPTgRPCServer.DeleteSession: ({context.code()}) {context.details()}')
        else:
            logging.info(
                f'ChatGPTgRPCServer.DeleteSession: (OK) {request.session_id}')

        return chatbot_pb2.DeleteSessionResponse(session_id=request.session_id)


def serveGRPC(address: str = 'localhost:50052'):
    """Starts a gRPC server at the specified address 'host:port'."""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    chatbot_pb2_grpc.add_ChatbotServiceServicer_to_server(
        ChatGPTgRPCServer(), server)

    SERVICE_NAMES = [
        chatbot_pb2.DESCRIPTOR.services_by_name['ChatbotService'].full_name]

    # the reflection service
    if os.getenv('GRPC_REFLECTION', False):
        from grpc_reflection.v1alpha import reflection
        SERVICE_NAMES.append(reflection.SERVICE_NAME)
        reflection.enable_server_reflection(SERVICE_NAMES, server)

        logging.info(f'gRPC reflection enabled.')

    server.add_insecure_port(address)
    server.start()
    print(f'ChatGPT gRPC server started at {address}.')
    print(f'Services: {SERVICE_NAMES}')
    server.wait_for_termination()
