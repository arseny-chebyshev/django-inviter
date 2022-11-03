import sys
import asyncio
import traceback
import json
import time
from telethon.tl.functions.channels import InviteToChannelRequest, JoinChannelRequest
from telethon.errors.rpcerrorlist import FloodWaitError, PeerFloodError, ApiIdInvalidError, SessionPasswordNeededError, ChatAdminRequiredError
from django.shortcuts import render, redirect
from django.views import View
from django.urls import reverse
from tl_client import get_client
from .models import User, Group, Invitation
from .forms import PullForm, PushForm, RegisterForm, PasswordForm
from .parsing_utils import get_user_or_free_client
from .tasks import pull_users, push_users
# Create your views here.

class MainView(View):
    def get(self, request):
        return redirect(reverse('inviter:pull'))

class RegisterView(View):
    
    def get(self, request):
        request.session.clear()
        intial_form = RegisterForm()
        return render(request, 'inviter/register.html', context={"register_form": intial_form})

    def post(self, request):
        request.session.clear()
        for key, val in request.POST.items():
            request.session[key] = val.strip(' ')
        try:  
            client = get_client(f"app{request.POST['phone']}", request.POST['api_id'], request.POST['api_hash'])
            code = client.send_code_request(request.POST['phone'])
            request.session['code_hash'] = code.phone_code_hash
            client.disconnect()
        except ApiIdInvalidError:
                request.session['failed_client'] = True
                return redirect(reverse('inviter:pull'))
        return redirect(reverse('inviter:2f-auth'))


class Telegram2FAuthView(View):

    def get(self, request):
        password_form = PasswordForm()
        return render(request, 'inviter/auth2f.html', context={"password_form": password_form})

    def post(self, request):
        request.session['verification_code'] = request.POST['verification_code']
        try:
            client = get_client(f"app{request.session['phone']}", 
                                request.session['api_id'], 
                                request.session['api_hash']) 
            client.sign_in(request.session['phone'], 
                           request.session['verification_code'], 
                           phone_code_hash=request.session['code_hash'])
            client.disconnect()
        except SessionPasswordNeededError:
            try:
                request.session['password'] = request.POST['password']
                client.sign_in(password=request.session['password'])
                client.disconnect()
            except KeyError:
                request.session['failed_client'] = True
                return redirect(reverse('inviter:pull'))
        return redirect(reverse('inviter:pull'))


class PullView(View):

    def get(self, request):
        pull_form = PullForm()
        context = {"pull_form": pull_form,
                    "failed_client": request.session.get('failed_client', None),
                    "phone": request.session.get('phone', None),
                    "api_id": request.session.get('api_id', None),
                    "api_hash": request.session.get('api_hash', None),
                    "users": request.session.get('users', None),
                    "successful_groups": request.session.get('successful_groups', None)}
        return render(request, 'inviter/pull.html', context=context)
    
    def post(self, request):
        if not request.session.session_key:
            request.session.save()
        pull_data = request.POST['donor_groups']
        chats = [chat.rstrip('\r') for chat in pull_data.split('\n')]
        pull_users.delay(request.session.session_key, chats)
        return redirect(reverse('inviter:pull'))


class PushView(View):
    
    def get(self, request):
        push_form = PushForm()
        context = {"push_form": push_form,
                   "invitations": request.session.get('invitations', None),
                   "failed_pull_groups": request.session.get('failed_pull_groups', None)}
        return render(request, 'inviter/push.html', context=context)

    def post(self, request):
        if not request.session.session_key:
            request.session.save()
        donor_groups = [chat.rstrip('\r') for chat in request.POST['donor_groups'].split('\n') if chat != '']
        target_link = request.POST['target_group']
        max_users_total = int(request.POST['max_users_total'])
        max_users_per_group = int(request.POST['max_users_per_group'])
        push_users.delay(request.session.session_key, donor_groups, target_link, max_users_total, max_users_per_group)
        #failed_pull_groups = []
        #sub_batch_size = 7
        #index = int(request.session.pop('index', 0))
        #invitations = request.session.pop('invitations', {})
        #total_users = []
        ## try to join target group
        #try:
        #    entity = client.get_input_entity(target_link)
        #    raw_group = json.loads((entity.to_json()))
        #    id_key = [key for key in raw_group.keys() if key.endswith('id')][0]
        #    target_group = Group.objects.filter(id=raw_group[id_key]).first()
        #    if not target_group:
        #        target_group = Group.objects.create(id=raw_group[id_key], link=target_link, 
        #                                            access_hash=raw_group['access_hash'])
        #    print(f"Joining chat {target_group}..")
        #    client(JoinChannelRequest(entity))
        #except (FloodWaitError, PeerFloodError):
        #    print("FloodWaitError, switch bot")
        #    client.disconnect()
        #    request.session.pop('phone', None)
        #    self.post(request)
        #except:
        #    traceback.print_exc()
        #    client.disconnect()
        #    invitations[target_link] = {'error': 'Could not join the group to add users to'}
        #    request.session['invitations'] = invitations
        #    request.session['failed_pull_groups'] = failed_pull_groups
        #    return redirect(reverse('inviter:push'))
        ## clean donor groups (refactor from views.py to forms.py later)
        #for donor_group in donor_groups:
        #    group_in_db = Group.objects.filter(link=donor_group).first()
        #    if not group_in_db:
        #        failed_pull_groups.append(donor_groups.pop(donor_groups.index(donor_group)))
        #    else:
        #        group_batch = group_in_db.user.all().exclude(id__in=[inv.user.id for inv 
        #                                                     in Invitation.objects.filter(group=target_group, 
        #                                                                                  is_added=True)])
        #        max_users_per_group = len(group_batch) if len(group_batch) < max_users_per_group else max_users_per_group
        #        total_users += group_batch[:max_users_per_group]
        #        print(f"total_users: {len(total_users)}")
        #
        ## calculate the real total of users
        #max_users_total = len(total_users) if len(total_users) < max_users_total else max_users_total
        ## push users from donor groups
        #for donor_group in donor_groups:
        #    invitations[donor_group] = {"success": 0, "already_in": 0}
        #    group_batch = group_in_db.user.all().exclude(id__in=[inv.user.id for inv 
        #                                                 in Invitation.objects.filter(group=target_group, 
        #                                                                              is_added=True)])
        #    max_users_per_group = len(group_batch) if len(group_batch) < max_users_per_group else max_users_per_group
        #    for user in group_batch[:max_users_per_group]:
        #        try:
        #            invited_before = Invitation.objects.filter(user=user, group=target_group).first()
        #            if invited_before:
        #                print(f"User {user} has already been invited")
        #                if not invited_before.is_added:
        #                    print(f"But was not added, adding again..")
        #                    client(InviteToChannelRequest(raw_group[id_key], [user.id]))
        #                    invitation = Invitation.objects.update_or_create(user=user, 
        #                                                                     group=target_group, 
        #                                                                     is_added=True)[0]             
        #                    invitations[donor_group]['success'] += 1           
        #                    index += 1
        #                else:
        #                    
        #                    invitations[donor_group]['already_in'] += 1                      
        #            else:
        #                print(f"Adding user {user}..")
        #                client(InviteToChannelRequest(raw_group[id_key], [user.id]))
        #                time.sleep(0.25)
        #                invitation = Invitation.objects.update_or_create(user=user, 
        #                                                                 group=target_group, 
        #                                                                 is_added=True)[0]             
        #                invitations[donor_group]['success'] += 1     
        #                index += 1
        #        except (FloodWaitError, PeerFloodError):
        #            print(f"FloodWaitError, switch_bot")
        #            client.disconnect()
        #            request.session.pop('phone', None)
        #            request.session['index'] = index
        #            request.session['invitations'] = invitations
        #            client = get_user_or_free_client(dict(request.session))
        #            continue
        #        except:
        #            traceback.print_exc()
        #            exc_tuple = sys.exc_info()
        #            invitation = Invitation.objects.update_or_create(user=user, group=target_group, 
        #                                                             error_message=f"{exc_tuple[0]}: {exc_tuple[1]}")[0]
        #            try:      
        #                invitations[donor_group][invitation.error_message] += 1
        #            except KeyError:
        #                invitations[donor_group][invitation.error_message] = 1
        #            continue
        #        if index >= max_users_total:
        #            client.disconnect()
        #            request.session['invitations'] = invitations
        #            request.session['failed_pull_groups'] = failed_pull_groups
        #            return redirect(reverse('inviter:push'))
        #        if index % sub_batch_size == 0:
        #            seconds = 30
        #            print(f"Cooldown for {seconds} seconds")
        #            time.sleep(seconds)    
        #client.disconnect()
        #request.session['invitations'] = invitations
        #request.session['failed_pull_groups'] = failed_pull_groups
        return redirect(reverse('inviter:push'))
