from django.shortcuts import render, HttpResponse, redirect
from django.http import JsonResponse
from django.views.generic import View 
from django.core.cache import cache 
from order.models import *
from utils.mixin import LoginRequiredMixin
from django_redis import get_redis_connection
from goods.models import * 
from user.models import * 
from django.db import transaction 
from datetime  import datetime 
from alipay import AliPay
import os,sys 
from django.conf import settings

# Create your views here.



class OrderPlaceView(LoginRequiredMixin, View):
    def post(self, request):
        user = request.user 
        sku_ids = request.POST.getlist('sku_ids')
        if not sku_ids:
            return redirect(reverse('cart:show'))

        conn = get_redis_connection('default')
        cart_key = 'cart_%d'%user.id 
        skus = []
        total_count = 0
        total_price = 0
        for sku_id in sku_ids:
            sku = GoodsSKU.objects.get(id=sku_id)
            count = conn.hget(cart_key, sku_id)
            amount = sku.price*int(count)
            sku.count = int(count )
            sku.amount = amount
            skus.append(sku)
            total_count+=int(count)
            total_price += amount 
        transit_price = 10 

        total_pay = total_price + transit_price 

        addrs = Address.objects.filter(user=user)

        sku_ids = ','.join(sku_ids) # [1,25]->1,25
        context = {'skus':skus,
                    'total_count':total_count,
                    'total_price':total_price,
                    'transit_price':transit_price,
                    'total_pay':total_pay,
                    'addrs':addrs,
                    'sku_ids':sku_ids}

        return render(request, 'place_order.html', context)

class OrderCommitView(View):
    @transaction.atomic
    def post(self, request):
        user = request.user 
        if not user.is_authenticated:
            return JsonResponse({'res':0, 'errmsg':'用户未登录'})
        
        addr_id = request.POST.get('addr_id')
        pay_method = request.POST.get('pay_method')
        sku_ids = request.POST.get('sku_ids')

        if not all([addr_id, pay_method, sku_ids]):
            return JsonResponse({'res':1, 'errmsg':'参数不完整'})

        if pay_method not in OrderInfo.PAY_METHODS.keys():
            return JsonResponse({'res':2, 'errmsg':'非法的支付方式'})
        
        try:
            addr = Address.objects.get(id=addr_id)
        except Address.DoesNotExist:
            return JsonResponse({'res':3, 'errmsg':'地址非法'})

        order_id = datetime.now().strftime('%Y%m%d%H%M%S')+str(user.id)
        transit_price = 10 
        total_count = 0
        total_price = 0

        save_id = transaction.savepoint()
        try:
            order = OrderInfo.objects.create(
                order_id=order_id,
                user=user,
                pay_method=pay_method,
                addr=addr,
                total_count=total_count,
                total_price=total_price,
                transit_price=transit_price
            )

            conn = get_redis_connection('default')
            cart_key = 'cart_%d'%user.id

            sku_ids = sku_ids.split(',')
            for sku_id in sku_ids:
                for i in range(3):
                    try:
                        sku = GoodsSKU.objects.get(id=sku_id)
                    except :
                        transaction.savepoint_rollback(save_id)
                        return JsonResponse({'res':4, 'errmsg':'商品不存在'})
                    count = conn.hget(cart_key, sku_id)

                    if int(count) > sku.stock:
                        transaction.savepoint_rollback(save_id)
                        return JsonResponse({'res':6, 'errmsg':'商品库存不足'})
                    
                    origin_stock = sku.stock 
                    new_stock = origin_stock - int(count)
                    new_sales = sku.sales + int(count)

                    res = GoodsSKU.objects.filter(id=sku_id, stock=origin_stock).update(stock=new_stock, sales=new_sales)
                    if res == 0:
                        if i ==2:
                            transaction.savepoint_rollback(save_id)
                            return JsonResponse({'res': 7, 'errmsg': '下单失败2'})
                        continue 
                    OrderGoods.objects.create(
                        order=order,
                        sku=sku,
                        count=count,
                        price=sku.price
                    )
                    amount = sku.price*int(count)
                    total_price += int(count)
                    total_price += amount 
                    break 
            
            order.total_count = total_count
            order.total_price = total_price
            order.save()
        except Exception as e:
            transaction.savepoint_rollback(save_id)
            return JsonResponse({'res':7, 'errmsg':e})
        
        transaction.savepoint_commit(save_id)

        conn.hdel(cart_key, *sku_ids)

        return JsonResponse({'res':5, 'message':'创建成功'})

# order/pay
class OrderPayView(View):
    def post(self, request):
        user = request.user 
        if not user.is_authenticated:
            return JsonResponse({'res':0, 'errmsg':'用户未登录'})

        order_id = request.POST.get('order_id')

        if not order_id:
            return JsonResponse({'res':1, 'errmsg':'无效的订单id'})
        print('--------------------------', order_id, user)
        try:
            order = OrderInfo.objects.get(
                order_id=order_id,
                user=user,
                pay_method=3,
                order_status=1)
        except OrderInfo.DoesNotExist:
            return JsonResponse({'res':2, 'errmsg':'订单错误'})
        
        alipay = AliPay(
            appid="2016092000555418", # 应用id
            app_notify_url=None,  # 默认回调url
            app_private_key_string=open(os.path.join(settings.BASE_DIR, 'apps/order/app_private_key.pem')).read(),
            alipay_public_key_string=open(os.path.join(settings.BASE_DIR, 'apps/order/alipay_public_key.pem')).read(), # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
            sign_type="RSA2",  # RSA 或者 RSA2
            debug=True  # 默认False
        )
        # https://blog.csdn.net/appleyuchi/article/details/104615154
        
        total_pay = order.total_price+order.transit_price # Decimal
        order_string = alipay.api_alipay_trade_page_pay(
            out_trade_no=order_id, # 订单id
            total_amount=str(total_pay), # 支付总金额
            subject='天天生鲜%s'%order_id,
            return_url=None,
            notify_url=None  # 可选, 不填则使用默认notify url
        )

        pay_url = 'https://openapi.alipaydev.com/gateway.do?' + order_string
        return JsonResponse({'res':3, 'pay_url':pay_url})
