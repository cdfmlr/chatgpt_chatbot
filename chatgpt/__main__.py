"""
ChatGPTChatbot server: gRPC or HTTP. 
Default is gRPC. If --http is specified, gRPC will be ignored.

Environment variables:

GRPC_REFLECTION:  if set to True, gRPC server will enable server reflection.
                  --debug will set this to True automatically.
                  (default: False)
CHATGPT_COOLDOWN: the cooldown time (in seconds) between two consecutive 
                  requests to a ChatGPT instance (access_token)
                  (default: 75)

"""


import argparse
import logging
import os

# from os import path
# from pathlib import Path
# import sys
# sys.path.append(path.dirname(path.abspath(__file__)))
# # sys.path.append(path.dirname(Path(path.abspath(__file__)).parent.absolute()))
# print(sys.path)

import httpapi
import grpcapi

# 🤬艹尼玛，导入永远写不对！！！！
#
# 对于 `PYTHONPATH=$PYTHONPATH:. python chatgpt`:
#
# from chatgpt import httpapi, grpcapi
#   ImportError: cannot import name 'httpapi' from 'chatgpt'
#
# from . import httpapi, grpcapi
#   ImportError: attempted relative import with no known parent package
#
# import httpapi, grpcapi
#   ModuleNotFoundError: No module named 'chatgpt.chatgpt'; 'chatgpt' is not a package
#
# 用 python -m chatgpt:
#
# from chatgpt import httpapi, grpcapi
#    ImportError: cannot import name 'ChatGPT' from 'chatgpt'
#
# 666 要怎么写嘛，那破文档是人读的吗？？


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    # --grpc localhost:50052 --http localhost:9006
    parser.add_argument("--grpc", type=str, default="localhost:50052",
                        help="gRPC server address: host:port (default localhost:50052)")
    parser.add_argument("--http", type=str, default="",
                        help="HTTP server address: e.g. localhost:9006. If specified, gRPC will be ignored. (default is not to start the HTTP server)")
    parser.add_argument("--debug", action="store_true",
                        help="Enable debug mode: logging level = DEBUG; gRPC += server_reflection (default is False)")
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        os.environ["GRPC_REFLECTION"] = "True"

    if args.http != "":
        httpapi.serveHTTP(args.http)
    elif args.grpc != "":
        grpcapi.serveGRPC(args.grpc)
    else:
        print("No server is specified, exiting. Use --grpc or --http to specify a server.")
        exit(1)


if __name__ == "__main__":
    logging.basicConfig()
    main()
