from django.shortcuts import render, HttpResponse, redirect, reverse
from django.contrib.auth import authenticate, login, logout
from django.views.generic import View 
from django.conf import settings
from django.core.mail import send_mail
from utils.mixin import LoginRequiredMixin
from .models import User, Address
from order.models import *
from goods.views import * 
import re
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer 
from itsdangerous import SignatureExpired
from celery_tasks.tasks import send_register_active_email

# Create your views here.

def index(request):
    return render(request, 'index.html')

def regist(request):
    if request.method=='GET':
        return render(request, 'register.html')
    
    elif request.method=='POST':
        username = request.POST.get('user_name', None)
        pwd = request.POST.get('pwd', None)
        cpwd = request.POST.get('cpwd', None)
        email = request.POST.get('email', None)
        allow = request.POST.get('allow', None)

        if not all([username, pwd, email]):
            return render(request, 'register.html', {'errmsg':'数据不完整'})
        
        if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$',email):
            return render(request, 'register.html', {'errmsg':'邮箱格式不正确'})
        
        if allow != 'on':
            return render(request, 'register.html', {'errmsg':'请同意协议'})
        
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            user = None 
        
        if user:
            return render(request, 'register.html', {'errmsg': '用户名已存在'})
        
        user = User.objects.create_user(username, email, pwd)  # database using password
        user.is_active = 0
        user.save()

        return redirect(reverse('user:login'))


def mylogin(request):
    if request.method == 'GET':
        return render(request, 'login.html')
    
    elif request.method=='POST':
        username = request.POST.get('username', None)
        pwd = request.POST.get('pwd', None)
        if not all([username, pwd]):
            return render(request, 'login.html', {'errmsg':'数据不完整'})
        
        user = authenticate(username=username, password=pwd)
        if user is not None:
            if user.is_active:
                login(request, user=user)

                next_url = request.GET.get('next', reverse('user:index'))
                response = redirect(next_url)

                remember = request.POST.get('remember')
                if remember == 'on':
                    response.set_cookie('username', username, max_age=10)
                else:
                    response.delete_cookie('username')
                return response 
            else:
                return render(request, 'login.html', {'errmsg':'账户未激活'})
        else:
            return render(request, 'login.html', {'errmsg':'用户名或密码错误'})


class RegistView(View):

    def get(self, request):
        return render(request, 'register.html')

    def post(self, request):
        username = request.POST.get('user_name', None)
        pwd = request.POST.get('pwd', None)
        cpwd = request.POST.get('cpwd', None)
        email = request.POST.get('email', None)
        allow = request.POST.get('allow', None)

        if not all([username, pwd, email]):
            return render(request, 'register.html', {'errmsg':'数据不完整'})
        
        if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$',email):
            return render(request, 'register.html', {'errmsg':'邮箱格式不正确'})
        
        if allow != 'on':
            return render(request, 'register.html', {'errmsg':'请同意协议'})
        
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            user = None 
        
        if user:
            return render(request, 'register.html', {'errmsg': '用户名已存在'})
        
        user = User.objects.create_user(username, email, pwd)  # database using password
        user.is_active = 0
        user.save()

        serializer = Serializer(settings.SECRET_KEY, 3600)
        info = {'confirm':user.id}
        token = serializer.dumps(info)
        token = token.decode()
        print('token:', token)

        def sendmail(to_email, username, token):
            subject = 'dailyfresh'
            message = 'regist message'
            sender = settings.EMAIL_FROM
            receiver = [to_email]
            html_message = '<h1>%s, 欢迎您成为天天生鲜注册会员</h1>请点击下面链接激活您的账户<br/><a href="http://127.0.0.1:8000/user/active/%s">http://127.0.0.1:8000/user/active/%s</a>' % (username, token, token)
            send_mail(subject, message, sender, receiver, html_message=html_message)
            # time.sleep(1)
        # sendmail(email, username, token)
        send_register_active_email(email, username, token)

        return redirect(reverse('user:login'))

class LoginView(View):
    def get(self, request):
        return render(request, 'login.html')
    
    def post(self, request):
        username = request.POST.get('username', None)
        pwd = request.POST.get('pwd', None)
        if not all([username, pwd]):
            return render(request, 'login.html', {'errmsg':'数据不完整'})
        
        user = authenticate(username=username, password=pwd)
        if user is not None:
            if user.is_active:
                login(request, user=user)

                next_url = request.GET.get('next', reverse('user:user'))
                response = redirect(next_url)

                remember = request.POST.get('remember')
                if remember == 'on':
                    response.set_cookie('username', username, max_age=10)
                else:
                    response.delete_cookie('username')
                return response 
            else:
                return render(request, 'login.html', {'errmsg':'账户未激活'})
        else:
            return render(request, 'login.html', {'errmsg':'用户名或密码错误'})

class LogoutView(View):
    def get(self, request):
        logout(request)
        return redirect(reverse('goods:index'))

class ActiveView(View):
    def get(self, request, token):
        serializer = Serializer(settings.SECRET_KEY, 3600)
        try:
            info = serializer.loads(token)
            print('info;;;;', info)
            user_id = info['confirm']

            user = User.objects.get(id=user_id)
            user.is_active = 1
            user.save()
            return redirect(reverse('user:login'))
        except Exception as e:
            return HttpResponse('激活链接已过期')



class UserInfoView(LoginRequiredMixin, View):
    def get(self, request):
        user = request.user
        address = Address.objects.get_default_address(user)

        conn = get_redis_connection('default')
        history_key = 'history_%d'%user.id

        sku_ids = conn.lrange(history_key, 0, 4)


        # goods_li = GoodsSKU.objects.all()

        goods_li = []
        for id in sku_ids:
            goods = GoodsSKU.objects.get(id=id)
            goods_li.append(goods)
        
        context = {
            'page':'user',
            'address':address,
            'goods_li':goods_li
        }
        return render(request, 'user_center_info.html', context)
    

# /user/order
class UserOrderView(LoginRequiredMixin, View):
    def get(self, request, page):
        user = request.user 
        orders = OrderInfo.objects.filter(user=user).order_by('-create_time')
        for order in orders:
            order_skus = OrderGoods.objects.filter(order_id=order.order_id)
            for order_sku in order_skus:
                amount = order_sku.count * order_sku.price 
                order_sku.amount = amount 
            order.status_name = OrderInfo.ORDER_STATUS[order.order_status]
            order.order_skus = order_skus
        
        paginator = Paginator(orders, 2)

        try:
            page = int(page)
        except Exception as e:
            page = 1
        
        if page > paginator.num_pages:
            page = 1
        
        order_page = paginator.page(page)

        num_pages = paginator.num_pages
        if num_pages < 5:
            pages = range(1, num_pages+1)
        elif page <= 3:
            pages = range(1, 6)
        elif num_pages - page <=2:
            pages = range(num_pages-4, num_pages+1)
        else:
            pages = range(page-2, page+3)
        
        context = {
                'order_page':order_page,
                'pages':pages,
                'page': 'order'
        }

        return render(request, 'user_center_order.html', context)


# /user/address
class AddressView(LoginRequiredMixin, View):
    def get(self, request):
        user = request.user 
        try:
            address = Address.objects.get(user=user, is_default=True)
        except Address.DoesNotExist:
            address = None
        return render(request, 'user_center_site.html', {'page':'address', 'address':address})

    def post(self, request):
        receiver = request.POST.get('receiver')
        addr = request.POST.get('addr')
        zip_code = request.POST.get('zip_code')
        phone = request.POST.get('phone')

        if not all([receiver, addr, phone, type]):
            return render(request, 'user_center_site.html', {'errmsg':'数据不完整'})
        
        if not re.match(r'^1[3|4|5|6|7|8|9][0-9]{9}$', phone):
            return render(request, 'user_center_site.html', {'errmsg':'手机格式不正确'})
        
        user = request.user 
        address = Address.objects.get_default_address(user)

        if address:
            is_default = False 
        else:
            is_default = True

        Address.objects.create(
            user=user,
            receiver=receiver,
            addr=addr,
            zip_code=zip_code,
            phone=phone,
            is_default=is_default
        ) 

        return redirect(reverse('user:address')) 