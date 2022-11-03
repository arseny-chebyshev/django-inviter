import sys
import asyncio
from multiprocessing import Process, Queue
import traceback
from functools import wraps
from telethon.errors.rpcerrorlist import FloodWaitError, PeerFloodError
from tl_client import get_client

def get_user_or_free_client(session_data: dict):
    if session_data.get('phone', False):
        client = get_client(f"app{session_data['phone']}", session_data['api_id'], session_data['api_hash'])
    else:
        client = get_client()
        print(f"Got client {client.session.filename} in get_user_or_free_client")
    return client
