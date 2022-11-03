import telethon
import socks
import os, fnmatch
from telethon.sync import TelegramClient
from configparser import ConfigParser
from time import sleep

myapps = []
config = ConfigParser()

with open('config.ini', 'r') as f:
    config.read('config.ini')

api_id = config.get('main', 'api_id')
api_hash = config.get('main', 'api_hash')
ip = config.get('main', 'ip')
port = config.get('main', 'port')


listOfFiles = os.listdir('.')
pattern = "*.session"
for entry in listOfFiles:
    if fnmatch.fnmatch(entry, pattern):
        myapps.append(entry)

proxy = (socks.SOCKS5, ip, port)

for app in myapps:
    print(app)
    try:
        client = TelegramClient(app, api_id, api_hash, proxy=proxy)
        client.connect()
        input(f"Press enter when the code is sent APP( {app}): ")
        for message in client.get_messages(777000, limit=1):
            print(message.message)

    except telethon.errors.rpcerrorlist.PhoneNumberBannedError:
        print(f"Аккаунт - {app} в бане! удаляем...")
        client.disconnect()
        sleep(2)
        os.remove(app)
    except ConnectionError:
        client.disconnect()
        sleep(2)
        os.remove(app)
    except telethon.errors.rpcerrorlist.UserDeactivatedBanError:
        client.disconnect()
        sleep(2)
        os.remove(app)