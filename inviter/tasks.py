import sys
import time
import traceback
import json
import time
from typing import Union, List
from telethon.tl.functions.channels import InviteToChannelRequest, JoinChannelRequest
from telethon.errors.rpcerrorlist import FloodWaitError, PeerFloodError
from telethon.types import Channel, Chat
from django.contrib.sessions.backends.db import SessionStore
from celery import shared_task
from celery.utils.log import get_task_logger
from tl_client import get_client
from .models import User, Group, Invitation

logger = get_task_logger(__name__)

class PullTask:

    def __init__(self, chat: str, session: SessionStore): # Всё же лучше обрабатывать по одной, т.к. self.group

        self.chat_url = chat
        self.session = session

        self.client = get_client(session)
        self.client.connect()
        self.group = self.client.get_entity(self.chat_url)

    def add_group_to_db(self):
        raw_group = json.loads((self.group.to_json()))
        id_key = [key for key in raw_group.keys() 
                  if key.endswith('id')][0]  # id keys are different for Chats and Groups 
        self.db_group = Group.objects.filter(id=raw_group[id_key]).first()
        if not self.db_group:
            self.db_group = Group.objects.create(id=raw_group[id_key], link=self.chat_url, 
                                                 access_hash=raw_group['access_hash'])
    
    def add_users_to_db(self, user_infos: dict):
        self.db_users = list(User.objects.bulk_update_or_create([User(**user_info) 
                           for user_info in user_infos], 
                           [field.name for field 
                           in User._meta.fields if not (field.primary_key or field.name == 'dt')],
                           match_field = 'id', yield_objects=True))[0][1]
        self.db_group.add(*self.db_users)
        self.db_group.save()

    def pull_users(self):
        try:
            participants = [participant for participant in self.client.get_participants(self.group) 
                            if not participant.bot]
            self.session['users'][self.chat_url] = len(participants) # session update
            user_infos = [{"id": user.id, "first_name": user.first_name, 
                               "last_name": user.last_name, "access_hash": user.access_hash}
                               for user in participants]
            self.add_users_to_db(user_infos)
            self.session['successful_groups'].append(self.db_group.id) # session update
            self.session.save()                                        # session saving
        except (FloodWaitError, PeerFloodError):
            print(f"FloodWait error, switch bot")
            self.client.disconnect()
            self.session.pop('phone', None)                            # session update
            self.session.save()                                        # session saving
            self.pull_users()                                          # recursive pull
        except:
            traceback.print_exc()
            exc_tuple = sys.exc_info()
            self.session['users'][self.chat_url] = \
            f"{exc_tuple[0]}: {exc_tuple[1]}" # ошибки при фетче юзеров заменяют описания количества
            self.session.save()               # session saving                                                
        self.client.session.close()
        self.client.disconnect()


class PushTask:

    def __init__(self, chat: str, session: SessionStore):
        
        self.chat_url = chat
        self.session = session
        self.users = []

        self.client = get_client(session)
        self.client.connect()
        self.group = self.client.get_entity(self.chat_url)
        self.raw_group = json.loads((self.group.to_json()))
        self.chat_id_key = [key for key in self.raw_group.keys() 
                            if key.endswith('id')][0] # id keys are different for Chats and Groups 

    def add_group_to_db(self):
        self.db_group = Group.objects.filter(id=self.raw_group[self.chat_id_key]).first()
        if not self.db_group:
            self.db_group = Group.objects.create(id=self.raw_group[self.chat_id_key], link=self.chat_url, 
                                                 access_hash=self.raw_group['access_hash'])

    def join_chat(self):
        invitations = self.session.pop('invitations', {})
        try:
            self.client(JoinChannelRequest(self.group))
        except (FloodWaitError, PeerFloodError):
            print("FloodWaitError, switch bot")
            self.client.disconnect()
            self.session.pop('phone', None)
            self.session.save()
            self.client = get_client(session_data=self.session)
            self.join_chat()
        except:
            traceback.print_exc()
            self.client.disconnect()
            invitations[self.chat_url] = {'error': 'Could not join the group to add users to'}
            self.session['invitations'] = invitations
            self.session.save()

    def push_users(self, donor_groups: List(str), max_users_total: int, max_users_per_group: int):
        
        self.join_chat()

        failed_pull_groups = []
        sub_batch_size = 7
        index = int(self.session.pop('index', 0))
        invitations = self.session.pop('invitations', {})

        for donor_group in donor_groups:
            db_group = Group.objects.filter(link=donor_group).first()
            if not db_group:
                failed_pull_groups.append(donor_groups.pop(donor_groups.index(donor_group)))
            else:
                group_batch = db_group.user.all().exclude(id__in=[inv.user.id for inv 
                                                             in Invitation.objects.filter(group=self.db_group, 
                                                                                          is_added=True)])
                max_users_per_group = len(group_batch) if len(group_batch) < max_users_per_group else max_users_per_group
                self.users += group_batch[:max_users_per_group]

        max_users_total = len(self.users) if len(self.users) < max_users_total else max_users_total

        for donor_group in donor_groups:
            db_group = Group.objects.filter(link=donor_group).first()
            invitations[donor_group] = {"success": 0, "already_in": 0}
            group_batch = db_group.user.all().exclude(id__in=[inv.user.id for inv 
                                                         in Invitation.objects.filter(group=self.db_group, 
                                                                                      is_added=True)])
            max_users_per_group = len(group_batch) if len(group_batch) < max_users_per_group else max_users_per_group
            for user in group_batch[:max_users_per_group]:
                try:
                    invited_before = Invitation.objects.filter(user=user, group=self.db_group).first()
                    if invited_before:
                        continue                
                    else:
                        print(f"Adding user {user}..")
                        self.client(InviteToChannelRequest(self.raw_group[self.chat_id_key], [user.id]))
                        time.sleep(0.25)
                        invitation = Invitation.objects.update_or_create(user=user, 
                                                                         group=self.db_group, 
                                                                         is_added=True)[0]             
                        invitations[donor_group]['success'] += 1     
                        index += 1
                        self.session['invitations'] = invitations
                        self.session.save()
                except(FloodWaitError, PeerFloodError):
                    print(f"FloodWaitError, switch_bot")
                    self.client.disconnect()
                    self.session.pop('phone', None)
                    self.session['index'] = index
                    self.session['invitations'] = invitations
                    self.client = get_client(self.session)
                    self.session.save()
                    continue
                except:
                    traceback.print_exc()
                    exc_tuple = sys.exc_info()
                    invitation = Invitation.objects.update_or_create(user=user, group=self.db_group, 
                                                                     error_message=f"{exc_tuple[0]}: {exc_tuple[1]}")[0]
                    try:      
                        invitations[donor_group][invitation.error_message] += 1
                    except KeyError:
                        invitations[donor_group][invitation.error_message] = 1
                    self.session['invitations'] = invitations
                    self.session.save()
                    continue
                if index >= max_users_total:
                    self.client.disconnect()
                    self.session['invitations'] = invitations
                    self.session['failed_pull_groups'] = failed_pull_groups
                    self.session.save()
                    break
                if index % sub_batch_size == 0:
                    seconds = 30
                    print(f"Cooldown for {seconds} seconds")
                    time.sleep(seconds)    
        self.client.disconnect()
        self.session['invitations'] = invitations
        self.session['failed_pull_groups'] = failed_pull_groups
        self.session.save()



@shared_task(bind=True)
def pull_users(self, session_key, chats, use_celery_logger=False):
    session = SessionStore(session_key=session_key)
    client = get_client(session)
    client.connect()
    session['users'] = {}
    session['successful_groups'] = []
    for chat in chats:
        print(f"Getting chat {chat}..")
        task = PullTask(chat=chat, session=session)
        task.pull_users()


@shared_task(bind=True)
def push_users(self, session_key, donor_groups, target_link, max_users_total, max_users_per_group):
    session = SessionStore(session_key=session_key)
    print("Fetching client from push_users()..")
    client = get_client(session)
    print(f"Fetched client {client.session.filename} in task")
    client.connect()

    failed_pull_groups = []
    sub_batch_size = 7
    index = int(session.pop('index', 0))
    invitations = session.pop('invitations', {})
    total_users = []
    # try to join target group
    try:
        entity = client.get_input_entity(target_link)
        raw_group = json.loads((entity.to_json()))
        id_key = [key for key in raw_group.keys() if key.endswith('id')][0]
        target_group = Group.objects.filter(id=raw_group[id_key]).first()
        if not target_group:
            target_group = Group.objects.create(id=raw_group[id_key], link=target_link, 
                                                access_hash=raw_group['access_hash'])
        print(f"Joining chat {target_group}..")
        client(JoinChannelRequest(entity))
    except (FloodWaitError, PeerFloodError):
        print("FloodWaitError, switch bot")
        client.disconnect()
        session.pop('phone', None)
        session.save()
        push_users(self, session_key, donor_groups, target_link, max_users_total, max_users_per_group)
    except:
        traceback.print_exc()
        client.disconnect()
        invitations[target_link] = {'error': 'Could not join the group to add users to'}
        session['invitations'] = invitations
        session['failed_pull_groups'] = failed_pull_groups
        session.save()
        return None
    # clean donor groups (refactor to forms.py later)
    for donor_group in donor_groups:
        group_in_db = Group.objects.filter(link=donor_group).first()
        if not group_in_db:
            failed_pull_groups.append(donor_groups.pop(donor_groups.index(donor_group)))
        else:
            group_batch = group_in_db.user.all().exclude(id__in=[inv.user.id for inv 
                                                         in Invitation.objects.filter(group=target_group, 
                                                                                      is_added=True)])
            max_users_per_group = len(group_batch) if len(group_batch) < max_users_per_group else max_users_per_group
            total_users += group_batch[:max_users_per_group]
            print(f"total_users: {len(total_users)}")
    
    # calculate the real total of users
    max_users_total = len(total_users) if len(total_users) < max_users_total else max_users_total
    # push users from donor groups
    for donor_group in donor_groups:
        invitations[donor_group] = {"success": 0, "already_in": 0}
        group_batch = group_in_db.user.all().exclude(id__in=[inv.user.id for inv 
                                                     in Invitation.objects.filter(group=target_group, 
                                                                                  is_added=True)])
        max_users_per_group = len(group_batch) if len(group_batch) < max_users_per_group else max_users_per_group
        for user in group_batch[:max_users_per_group]:
            try:
                invited_before = Invitation.objects.filter(user=user, group=target_group).first()
                if invited_before:
                    print(f"User {user} has already been invited")
                    if not invited_before.is_added:
                        print(f"But was not added, adding again..")
                        client(InviteToChannelRequest(raw_group[id_key], [user.id]))
                        invitation = Invitation.objects.update_or_create(user=user, 
                                                                         group=target_group, 
                                                                         is_added=True)[0]             
                        invitations[donor_group]['success'] += 1           
                        index += 1
                        session['invitations'] = invitations
                        session.save()
                    else:
                        invitations[donor_group]['already_in'] += 1      
                        session['invitations'] = invitations
                        session.save()                
                else:
                    print(f"Adding user {user}..")
                    client(InviteToChannelRequest(raw_group[id_key], [user.id]))
                    time.sleep(0.25)
                    invitation = Invitation.objects.update_or_create(user=user, 
                                                                     group=target_group, 
                                                                     is_added=True)[0]             
                    invitations[donor_group]['success'] += 1     
                    index += 1
                    session['invitations'] = invitations
                    session.save()
            except (FloodWaitError, PeerFloodError):
                print(f"FloodWaitError, switch_bot")
                client.disconnect()
                session.pop('phone', None)
                session['index'] = index
                session['invitations'] = invitations
                client = get_client(dict(session))
                session.save()
                continue
            except:
                traceback.print_exc()
                exc_tuple = sys.exc_info()
                invitation = Invitation.objects.update_or_create(user=user, group=target_group, 
                                                                 error_message=f"{exc_tuple[0]}: {exc_tuple[1]}")[0]
                try:      
                    invitations[donor_group][invitation.error_message] += 1
                except KeyError:
                    invitations[donor_group][invitation.error_message] = 1
                session['invitations'] = invitations
                session.save()
                continue
            if index >= max_users_total:
                client.disconnect()
                session['invitations'] = invitations
                session['failed_pull_groups'] = failed_pull_groups
                session.save()
                break
            if index % sub_batch_size == 0:
                seconds = 30
                print(f"Cooldown for {seconds} seconds")
                time.sleep(seconds)    
    client.disconnect()
    session['invitations'] = invitations
    session['failed_pull_groups'] = failed_pull_groups
    session.save()
