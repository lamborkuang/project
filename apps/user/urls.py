from django.urls import path
from .views import *


app_name ='[user]'
urlpatterns = [

    # path('login', mylogin, name='login'),
    # path('regist', regist, name='regist'),
    path('regist', RegistView.as_view(), name='regist'),
    path('login', LoginView.as_view(), name='login'),
    path('logout', LogoutView.as_view(), name='logout'),
    path('active/<token>', ActiveView.as_view(), name='active'),

    path('', UserInfoView.as_view(), name='user'),
    path('address', AddressView.as_view(), name='address'),
    path('order/?P<page>\d+', UserOrderView.as_view(), name='order'),


]