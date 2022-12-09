from telethon.errors.rpcerrorlist import ApiIdInvalidError, SessionPasswordNeededError
from django.shortcuts import render, redirect
from django.views import View
from django.urls import reverse
from tl_client import get_client
from .forms import PullForm, PushForm, RegisterForm, PasswordForm
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
            client = get_client(request.session)
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
            client = get_client(request.session) 
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
        push_users.delay(request.session.session_key, donor_groups, target_link, 
                         max_users_total, max_users_per_group)
        return redirect(reverse('inviter:push'))
