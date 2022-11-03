from django.urls import path
from . import views

app_name = 'inviter'
urlpatterns = [
    path('', views.MainView.as_view(), name='main'),
    path('register', views.RegisterView.as_view(), name='register'),
    path('pull', views.PullView.as_view(), name = 'pull'),
    path('push', views.PushView.as_view(), name = 'push'),
    path('2f-auth', views.Telegram2FAuthView.as_view(), name='2f-auth')
    ]