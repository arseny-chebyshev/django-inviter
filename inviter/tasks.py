import sys
import time
import asyncio
import traceback
import json
import time
from telethon.tl.functions.channels import InviteToChannelRequest, JoinChannelRequest
from telethon.errors.rpcerrorlist import FloodWaitError, PeerFloodError, ApiIdInvalidError, SessionPasswordNeededError, ChatAdminRequiredError
from django.contrib.sessions.models import Session
from django.contrib.sessions.backends.db import SessionStore
from django.shortcuts import render, redirect
from django.views import View
from django.urls import reverse
from celery import shared_task
from celery.contrib import rdb
from celery.result import AsyncResult
from celery.utils.log import get_task_logger
from tl_client import get_client
from .models import User, Group, Invitation
from .forms import PullForm, PushForm, RegisterForm, PasswordForm
from .parsing_utils import get_user_or_free_client

logger = get_task_logger(__name__)

@shared_task(bind=True)
def pull_users(self, session_key, chats, use_celery_logger=False):
    session = SessionStore(session_key=session_key)
    client = get_user_or_free_client(session)
    client.connect()
    session['users'] = {}
    session['successful_groups'] = []
    for chat in chats:
        print(f"Getting chat {chat}..")
        try:
            entity = client.get_input_entity(chat)
            raw_group = json.loads((entity.to_json()))
            id_key = [key for key in raw_group.keys() if key.endswith('id')][0]
            group = Group.objects.filter(id=raw_group[id_key]).first()
            if not group:
                group = Group.objects.create(id=raw_group[id_key], link=chat, 
                                             access_hash=raw_group['access_hash'])
            print(f"Got entity {entity}, fetching users..")
            participants = [participant for participant in client.get_participants(entity) if not participant.bot]
            print(f"Returning {len(participants)} participants from {entity}")
            session['users'][chat] = len(participants)
            user_infos = [{"id": user.id, "first_name": user.first_name, 
                           "last_name": user.last_name, "access_hash": user.access_hash}
                           for user in participants]
            members = list(User.objects.bulk_update_or_create([User(**user_info) 
                           for user_info in user_infos], 
                           [field.name for field in User._meta.fields if not (field.primary_key or field.name == 'dt')],
                           match_field = 'id', yield_objects = True))[0][1]
            group.user.add(*list(members))
            group.save()
            session['successful_groups'].append(group.id)
            session.save()
        except (FloodWaitError, PeerFloodError):
            print(f"FloodWait error, switch bot")
            client.disconnect()
            session.pop('phone', None)
            session.save()
            pull_users(self, session, chats)
        except:
            traceback.print_exc()
            exc_tuple = sys.exc_info()
            session['users'][chat] = f"{exc_tuple[0]}: {exc_tuple[1]}" # ошибки при фетче юзеров заменяют описания количества
            session.save()
            continue   
    session.save()
    client.session.close()
    client.disconnect()


@shared_task(bind=True)
def push_users(self, session_key, donor_groups, target_link, max_users_total, max_users_per_group):
    session = SessionStore(session_key=session_key)
    print("Fetching client from push_users()..")
    client = get_user_or_free_client(session)
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
                client = get_user_or_free_client(dict(session))
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
