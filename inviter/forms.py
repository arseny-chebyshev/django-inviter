from django import forms

class RegisterForm(forms.Form):
    phone = forms.CharField(required=False, label="Phone number")
    api_id = forms.IntegerField(required=False, label="API ID")
    api_hash = forms.CharField(required=False, label="API HASH")    

class PullForm(forms.Form):
    donor_groups = forms.CharField(widget=forms.Textarea, required=True, max_length=255, label="Donor chats (one per line)")

class PushForm(forms.Form):
    donor_groups = forms.CharField(widget=forms.Textarea, required=True, max_length=255, label="Donor chats (one per line)")
    target_group = forms.CharField(required=True, max_length=255, label="Target chat")
    max_users_per_group = forms.IntegerField(min_value=1, label="Max users to add from 1 chat")
    max_users_total = forms.IntegerField(min_value=1, label="Total users to add")
    
class PasswordForm(forms.Form):
    verification_code = forms.CharField(required=True, label="Code from Telegram App")
    password = forms.CharField(widget=forms.PasswordInput, required=False, label="2-Factor Authentication might be enabled. Insert your Telegram Password")