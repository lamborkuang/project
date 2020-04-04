from django.urls import path
from .views import *

app_name ='[goods]'
urlpatterns = [
    path('', IndexView.as_view(), name='index'),
    path('index', IndexView.as_view(), name='index'),
    path('goods/<goods_id>\d+', DetailView.as_view(), name='detail'),
    path('list/<type_id>\d+/<page>\d+', ListView.as_view(), name='list'),
    
]