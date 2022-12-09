import os
import sys
import time
import asyncio
import queue
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor
from configparser import ConfigParser
from django.db.models import QuerySet, Q
from telethon.sync import TelegramClient
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.errors.rpcerrorlist import FloodWaitError, AuthKeyUnregisteredError, PeerFloodError
from autoreg import register_account
from inviter.models import TelethonSession
config = ConfigParser()


try:
    with open('config.ini', 'r') as f:
        config.read('config.ini')
except:
    with open('config.ini', 'w') as f:
        config.add_section('TL CLIENT')
        config.set('TL CLIENT', 'TOKEN_5sim', 'value0')
        config.set('TL CLIENT', 'country', 'indonesia')
        config.set('TL CLIENT', 'operator', 'any')
        config.set('TL CLIENT', 'api_id', 'value0')
        config.set('TL CLIENT', 'api_hash', 'value1')
        config.set('TL CLIENT', 'ip', 'value2')
        config.set('TL CLIENT', 'port', 'value3')
        config.write(f)
        print('Заполните config.ini')
        exit()

def get_config_credentials():
    api_id = config['TL CLIENT']['api_id']
    api_hash = config['TL CLIENT']['api_hash']
    return api_id, api_hash


class TelethonValidator:

    def __init__(self, sessions: list, threads: int):
        self.q = queue.Queue(maxsize=1)
        self.sessions = TelethonSession.objects.filter(
            Q(is_active=True) & 
            Q(in_use=False)     
        )
        self.found = False 
        self.executor = ThreadPoolExecutor(max_workers=threads)

    async def parse_sessions(self, sessions: list): # TODO: async
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop) 
        while sessions:
            if not self.found:
                print(f"Sessions: {len(sessions)}")
                session = sessions[0]
                print(f"Found session {session}")
                print(f"Checking session {session.session_string}")
                api_id, api_hash = get_config_credentials()
                try:
                    client = TelegramClient(session.session_string, api_id, api_hash)
                    print(f"Created client {client}")
                    await client.connect()
                    if not await client.is_user_authorized():
                        print(f"Client not authorized, skipping")
                        await client.disconnect()
                        session.delete()
                        session.save()
                        sessions.pop(0)
                        continue
                    else:
                        session.in_use = True
                        session.save()
                        it_za_rubezhom = client.get_input_entity(1637643104)
                        me = await client.get_input_entity('https://t.me/arseny_chebyshev')
                        client(InviteToChannelRequest(it_za_rubezhom, [me])) # проверка на FloodWait ограничение на приглашение в канал
                        self.q.put(client)
                        self.found = True
                        print(f"Successfully sent InviteToChannelRequest with client: {client._phone}")
                        return None
                except (FloodWaitError, PeerFloodError):
                    print(f"Client {client} is flooded")
                    client.disconnect()
                    session.send_to_rehab()
                    sessions.pop(0)
                    continue
                except AuthKeyUnregisteredError:
                    print(f"Client {client} is not authorized")
                    client.disconnect()
                    session.send_to_rehab()
                    sessions.pop(0)
                    continue
                except:
                    print(f"Unexpected Error: {traceback.print_exc()}")
                    sessions.pop(0)
                    continue
            else:
                return None
        if not self.found:
            client = register_account()
            self.q.put(client)
            self.found = True
        else:
            return None

    def get_client(self):
        chunks = [self.sessions[i::4] for i in range(4)]
        with self.executor as e:
            for chunk in chunks:
                future = e.submit(asyncio.run, self.parse_sessions(chunk))
            result = self.q.get()
            e.shutdown(wait=False)
        return result

# В будущем этот метод ответственнен за подбор экземпляра Telethon - не заблокированного, не в "отлёжке" и т.д.
def get_client(session_data:dict={}) -> TelegramClient:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    # Если пользователь указал данные для клиента
    if session_data.get("phone", None):
        client = TelegramClient(f"app{session_data['phone']}", session_data['api_id'], session_data['api_hash'])
        client.connect()
    # Если не указал
    else:
        dir_files = os.listdir()
        sessions = sorted([file for file in dir_files if file.endswith('.session')], reverse=True)

        #многопоточка, пока не работает корректно из-за async loop
        #validator = TelethonValidator(sessions=sessions, threads=2)
        #client = validator.get_client()

        while sessions:
            print(f"Sessions: {len(sessions)}")
            session = sessions[0]
            print(f"Found session {session}")
            session_name = session[:session.find('.session')]
            print(f"Checking session {session_name}")
            api_id, api_hash = get_config_credentials()
            try:
                client = TelegramClient(session_name, api_id, api_hash)
                print(f"Created client {client}")
                client.connect()
                if not client.is_user_authorized():
                    print(f"Client not authorized, skipping")
                    client.disconnect()
                    sessions.pop(0)
                    continue
                else:
                    it_za_rubezhom = client.get_input_entity(1637643104)
                    me = client.get_input_entity('https://t.me/arseny_chebyshev')
                    client(InviteToChannelRequest(it_za_rubezhom, [me])) # проверка на FloodWait ограничение на приглашение в канал
                    print(f"Successfully sent InviteToChannelRequest with client: {client.session.filename}")
                    return client
            except (FloodWaitError, PeerFloodError):
                print(f"Client {client} is flooded")
                client.disconnect()
                sessions.pop(0)
                continue
            except AuthKeyUnregisteredError:
                print(f"Client {client} is not authorized")
                client.disconnect()
                sessions.pop(0)
                continue
            except:
                print(f"Unexpected Error: {traceback.print_exc()}")
                sessions.pop(0)
                continue
        client = register_account()
    return client
