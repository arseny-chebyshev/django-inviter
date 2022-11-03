"""Авторег аккаунт телеграм"""
import traceback
import requests
import socks
import random
import os
import telethon
import json
import names
from telethon.sync import TelegramClient
from configparser import ConfigParser
from time import sleep

config = ConfigParser()
my_apps = []

#убогий конфиг
try:
    with open('config.ini', 'r') as f:
        config.read('config.ini')
except:
    with open('config.ini', 'w') as f:
        config.add_section('5 SIM')
        config.set('5 SIM', 'TOKEN_5sim', 'value0')
        config.set('5 SIM', 'country', 'indonesia')
        config.set('5 SIM', 'operator', 'any')
        config.set('TL CLIENT', 'api_id', 'value0')
        config.set('TL CLIENT', 'api_hash', 'value1')
        config.set('5 SIM', 'ip', 'value2')
        config.set('5 SIM', 'port', 'value3')
        config.write(f)
        print('Заполните settings.ini')
        exit()

token = config.get('5 SIM', 'TOKEN_5sim')
api_id = config.get('TL CLIENT', 'api_id')
api_hash = config.get('TL CLIENT', 'api_hash')
ip = config.get('5 SIM', 'ip')
port = config.get('5 SIM', 'port')
#proxy = (socks.SOCKS5, ip, int(port)) #прокси )
country_list = ['afghanistan', 'albania', 'algeria', 'angola', 'anguilla', 'antiguaandbarbuda', 'argentina', 'armenia', 'aruba', 'australia', 
'austria', 'azerbaijan', 'bahamas', 'bahrain', 'bangladesh', 'barbados', 'belarus', 'belgium', 'belize', 'benin', 'bhutane', 'bih', 'bolivia', 
'botswana', 'brazil', 'bulgaria', 'burkinafaso', 'burundi', 'cambodia', 'cameroon', 'canada', 'capeverde', 'caymanislands', 'chad', 'chile', 'china', 'colombia', 
'comoros', 'congo', 'costarica', 'croatia', 'cyprus', 'czech', 'djibouti', 'dominica', 'dominicana', 'easttimor', 'ecuador', 'egypt', 
'england', 'equatorialguinea', 'eritrea', 'estonia', 'ethiopia', 'finland', 'france', 'frenchguiana', 'gabon', 'gambia', 'georgia', 'germany', 'ghana', 'greece', 
'grenada', 'guadeloupe', 'guatemala', 'guinea', 'guineabissau', 'guyana', 'haiti', 'honduras', 'hongkong', 'hungary', 'india', 'indonesia', 'ireland', 
'israel', 'italy', 'ivorycoast', 'jamaica', 'japan', 'jordan', 'kazakhstan', 'kenya', 'kuwait', 'kyrgyzstan', 'laos', 'latvia', 'lesotho', 'liberia', 'lithuania', 
'luxembourg', 'macau', 'madagascar', 'malawi', 'malaysia', 'maldives', 'mauritania', 'mauritius', 'mexico', 'moldova', 
'mongolia', 'montenegro', 'montserrat', 'morocco', 'mozambique', 'myanmar', 'namibia', 'nepal', 'netherlands', 'newcaledonia', 'newzealand', 'nicaragua', 'niger', 'nigeria', 
'northmacedonia', 'norway', 'oman', 'pakistan', 'panama', 'papuanewguinea', 'paraguay', 'peru', 'philippines', 'poland', 'portugal', 'puertorico', 
'reunion', 'romania', 'rwanda', 'saintkittsandnevis', 'saintlucia', 'saintvincentandgrenadines', 'salvador', 'samoa', 'saotomeandprincipe', 'saudiarabia', 'senegal', 'serbia', 
'seychelles', 'sierraleone', 'singapore', 'slovakia', 'slovenia', 'solomonislands', 'southafrica',
'spain', 'srilanka', 'suriname', 'swaziland', 'sweden', 'switzerland', 'taiwan', 'tajikistan', 'tanzania', 'thailand', 'tit', 'togo', 'tonga', 'tunisia', 'turkey', 'turkmenistan', 
'turksandcaicos', 'uganda', 'ukraine', 'uruguay', 'usa', 'uzbekistan', 'venezuela', 'vietnam', 'virginislands', 'zambia', 'zimbabwe']
#headers для запроса
headers = {
    'Authorization': 'Bearer ' + token,
    'Accept': 'application/json',
}
def get_number():
    """Получаем номера"""
    global id, phone, client
    #country = config.get('5 SIM', 'country')
    operator = config.get('5 SIM', 'operator')
    
    while True:
        country = random.choice(country_list)
        response = requests.get('https://5sim.net/v1/user/buy/activation/' + country + '/' + operator + '/' + 'telegram', headers=headers)
        resp = response.text
        
        if resp == "no free phones":
            print(f"Нет свободных номеров в стране {country}!")
            country_list.remove(country)
            continue
        else:
            try:
                r = json.loads(resp)
                id = r.get("id")
                phone = r.get("phone")
                try:
                    client = TelegramClient(f'app{phone}', api_id, api_hash, connection_retries=2) # для соединения с docker уберём параметр proxy
                except ConnectionError:
                    print(f"{phone} - proxy error!")
                    cancel_oreder()
                    os.remove(f"app{phone}.session")
                print(f'Phone - {phone} / Id - {id}')
                break
            except:
                print('Error!')
                print(resp)
                exit()
    
def cancel_oreder():
    """Отменяем в случаи ошибки"""
    response = requests.get('https://5sim.net/v1/user/ban/' + str(id), headers=headers)
    response = requests.get('https://5sim.net/v1/user/ban/' + str(id), headers=headers)
    
def get_sms():
    """Получаем смс запросом на сайт"""
    sleep(30)
    response = requests.get('https://5sim.net/v1/user/check/' + str(id), headers=headers)
    resp = response.text
    try:
        r = json.loads(resp)
        print(f"SMS: {r.get('sms')}")
        sms = r.get("sms")[0]
        code = sms.get("code")
    except:
        print('Сообщение не пришло')
        client.disconnect()
        os.remove(f"app{phone}.session")
        register_account()
    return code

def register_account():
    """Регестрируем аккаунт, обновляем username"""
    while True:
        get_number()
        try:
            client.connect()
        except ConnectionError:
            traceback.print_exc()
            print(f"{phone} - proxy error!")
            client.disconnect()
            cancel_oreder()
            os.remove(f"app{phone}.session")

        first_name = names.get_first_name() #random first name и last name
        last_name = names.get_last_name()
        try:
            client.send_code_request(phone) 
            client.sign_up(get_sms(), first_name=first_name, last_name=last_name) #регестрируем аккаунт исходя из данных
            print("[+] SignUp Done!")
            client.disconnect()
            return client
        except telethon.errors.rpcerrorlist.PhoneNumberBannedError:
            print(f"{phone} - banned") #Проверяем на бан
            sleep(3)
            cancel_oreder()
            client.disconnect()
            os.remove(f"app{phone}.session")
        except telethon.errors.rpcerrorlist.FloodWaitError:
            print(f"{phone} - flood error!")
            sleep(3)
            cancel_oreder()
            client.disconnect()
            os.remove(f"app{phone}.session")
        except telethon.errors.rpcerrorlist.SessionPasswordNeededError:
            print(f"{phone} - SessionPasswordNeededError!")
            sleep(3)
            cancel_oreder()
            client.disconnect()
            os.remove(f"app{phone}.session")
        except AttributeError:
            print(f'{phone} - incorrect number') #Проверяем коректность номера
            sleep(3)
            cancel_oreder()
            client.disconnect()
            os.remove(f"app{phone}.session")
        except ValueError:
            if client.is_user_authorized():
                return client
            else:
                pass
        except:
            traceback.print_exc()
                #client.disconnect()
                #traceback.print_exc()
                #os.remove(f"app{phone}.session")
