from django.shortcuts import render, redirect
from django.views import View
from django.http import JsonResponse
from django.urls import reverse
from django_redis import get_redis_connection
from django.db import transaction
from apps.goods.models import GoodsSKU
from apps.user.models import Address
from apps.order.models import OrderInfo, OrderGoods
from datetime import datetime
from alipay import AliPay
from django.conf import settings
from utils.mixin import LoginRequiredMixin


# Create your views here.
# order/pay
class OrderPlaceView(LoginRequiredMixin, View):
    """提交订单页面"""
    def post(self, request):
        '''提交订单页面显示'''
        # 获取登录的用户
        user = request.user
        if not user.is_authenticated:
            return redirect(reverse('user:login'))
        # 获取参数sku_ids
        sku_ids = request.POST.getlist('sku_ids')

        # 校验参数
        if not sku_ids:
            # 跳转到购物车页面
            return redirect(reverse('cart:show'))

        conn = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id

        skus = []
        total_count = 0
        total_price = 0
        # 遍历sku_ids获取用户要购买的商品的信息
        for sku_id in sku_ids:
            # 根据商品的id获取商品的信息
            try:
                sku = GoodsSKU.objects.get(id=sku_id)
            except GoodsSKU.DoesNotExist:
                return redirect(reverse('cart:show'))
            # 获取用户所要够爱的商品的数量
            count = conn.hget(cart_key, sku_id)
            if count is None:
                return redirect(reverse('cart:show'))
            # 计算商品的小计
            amount = sku.price * int(count)
            # 动态给sku增加属性count, 保存购买商品的数量
            sku.count = int(count)
            # 动态给sku增加属性amount,保存购买商品的小计
            sku.amount = amount
            # 添加信息进skus中
            skus.append(sku)
            total_count += int(count)
            total_price += amount

        # 运费：实际开发的时候，运费属于一个子系统，可以考虑对接其他快递公司的运费模板
        transit_price = 0
        if total_price < 50:
            transit_price = 10
        # 实付款
        total_pay = transit_price + total_price
        # 获取用户的收货地址
        addrs = Address.objects.filter(user=user)
        sku_ids = ','.join(sku_ids)
        # 组织上下文
        context = {
            'skus': skus,
            'total_count': total_count,
            'total_price': total_price,
            'transit_price': transit_price,
            'total_pay': total_pay,
            'addrs': addrs,
            'sku_ids': sku_ids
        }
        # 使用模板
        return render(request, 'place_order.html', context)


# 前端采用ajax post请求，请求路径　/order/commit
# 前端传递参数：　addr_id: 地址id; pay_method:付款方式; sku_ids:购买商品的ID
# 加悲观锁，乐观锁使用开销比较大，或者改动数据比较多的情况下使用悲观锁，todo:一般使用乐观锁
class OrderCommitViewCommit(View):
    @transaction.atomic
    def post(self, request):
        user = request.user
        if not user.is_authenticated:
            # 用户未登录
            return JsonResponse({
                'res': 1,
                'msg': '用户未登录，请先登录'
            })
        # 接受数据
        addr_id = request.POST.get('addr_id')
        pay_method = request.POST.get('pay_method')
        sku_ids = request.POST.get('sku_ids')

        # 校验数据
        if not all([addr_id, pay_method, sku_ids]):
            return JsonResponse({
                'res': 2,
                'msg': '参数有缺'
            })

        if pay_method not in OrderInfo.PAY_METHODS.keys():
            # 支付方式错误
            return JsonResponse({
                'res': 3,
                'msg': '支付方式错误'
            })

        try:
            addr = Address.objects.get(id=addr_id)
        except Address.DoesNotExist:
            return JsonResponse({
                'res': 4,
                'msg': '地址非法'
            })

        # todo:创建订单核心业务
        # 组织参数
        # 订单id: 20171122181630+用户id:当前时间的年月日时分秒＋用户id
        order_id = datetime.now().strftime('%Y%m%d%H%M%S') + str(user.id)
        # 运费
        transit_price = 10
        # 总数目和总金额
        total_count = 0
        total_price = 0

        # savepoint()　创建保存点
        # savepoint_commit() 提交该保存点之前的操作
        # savepoint_rollback() 回滚到该保存点
        # clean_savepoint() 删除该保存点
        # 在这个地方设置一个保存点

        save_point_id = transaction.savepoint()
        try:
            # todo：向df_order_info表中添加一条记录
            order = OrderInfo.objects.create(
                order_id=order_id,
                user=user,
                addr=addr,
                pay_method=pay_method,
                total_count=total_count,
                total_price=total_price,
                transit_price=transit_price
            )

            # todo:用户订单中有几个商品，需要向df_order_goods表中加入几条记录
            conn = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id

            sku_ids = sku_ids.split(',')  # 把字符串通过逗号分割，形成一个字典
            for sku_id in sku_ids:
                # 获取商品的信息，在这个位置尝试一下注入
                try:
                    # sku = GoodsSKU.objects.get(id=sku_id)
                    sku = GoodsSKU.objects.select_for_update().get(id=sku_id)
                    # 上面这行就是悲观锁
                    # select_for_update() 相当获得了锁, sql: select * from df_goods_sku where id=sku_id for update;
                except GoodsSKU.DoesNotExist:
                    # 商品不存在，回滚到没有操作的保存点
                    transaction.savepoint_rollback(save_point_id)
                    return JsonResponse({
                        'res': 5,
                        'msg': '商品不存在'
                    })

                # 从redis中获取用户所要购买的商品的数量
                count = conn.hget(cart_key, sku_id)

                # 检测需要购买数量是否超过库存
                if sku.stock < int(count):
                    transaction.savepoint_rollback(save_point_id)
                    return JsonResponse({
                        'res': 6,
                        'msg': '商品库存不足'
                    })

                # todo: 向df_order_goods表中添加一条记录
                OrderGoods.objects.create(
                    order=order,
                    sku=sku,
                    count=count,
                    price=sku.price
                )
                # todo: 更新商品的库存和销量（这边判断应该在前面需要修改）
                sku.stock -= int(count)
                sku.sales += int(count)
                sku.save()
                # todo:　累加计算订单商品的总数量和总价格
                total_count += int(count)
                amount = int(count) * sku.price
                total_price += amount
            # todo: 更新订单信息表中的商品总数量和总价格
            order.total_count = total_count
            order.total_price = total_price
            order.save()
        except Exception as e:
            transaction.savepoint_rollback(save_point_id)
            return JsonResponse({
                'res': 7,
                'msg': '下单失败，数据库事务出错'
            })
        transaction.savepoint_commit(save_point_id)
        # todo: 清除用户购物车中对应的记录　[1,3]
        # 在列表的前面加一个*，相当于自动给你执行多次，每次传入一个数字
        conn.hdel(cart_key, *sku_ids)

        # 返回应答
        return JsonResponse({
            'res': 0,
            'msg': '订单创建成功'
        })


# 前端采用ajax post请求，请求路径　/order/commit
# 前端传递参数：　addr_id: 地址id; pay_method:付款方式; sku_ids:购买商品的ID
# 加乐观锁，乐观锁使用开销比较大，或者改动数据比较多的情况下使用悲观锁，todo:一般使用乐观锁
class OrderCommitView(View):
    @transaction.atomic
    def post(self, request):
        user = request.user
        if not user.is_authenticated:
            # 用户未登录
            return JsonResponse({
                'res': 1,
                'msg': '用户未登录，请先登录'
            })
        # 接受数据
        addr_id = request.POST.get('addr_id')
        pay_method = request.POST.get('pay_method')
        sku_ids = request.POST.get('sku_ids')

        # 校验数据
        if not all([addr_id, pay_method, sku_ids]):
            return JsonResponse({
                'res': 2,
                'msg': '参数有缺'
            })

        if pay_method not in OrderInfo.PAY_METHODS.keys():
            # 支付方式错误
            return JsonResponse({
                'res': 3,
                'msg': '支付方式错误'
            })

        try:
            addr = Address.objects.get(id=addr_id)
        except Address.DoesNotExist:
            return JsonResponse({
                'res': 4,
                'msg': '地址非法'
            })

        # todo:创建订单核心业务
        # 组织参数
        # 订单id: 20171122181630+用户id:当前时间的年月日时分秒＋用户id
        order_id = datetime.now().strftime('%Y%m%d%H%M%S') + str(user.id)
        # 运费
        transit_price = 10
        # 总数目和总金额
        total_count = 0
        total_price = 0

        # savepoint()　创建保存点
        # savepoint_commit() 提交该保存点之前的操作
        # savepoint_rollback() 回滚到该保存点
        # clean_savepoint() 删除该保存点
        # 在这个地方设置一个保存点

        save_point_id = transaction.savepoint()
        try:
            # todo：向df_order_info表中添加一条记录
            order = OrderInfo.objects.create(
                order_id=order_id,
                user=user,
                addr=addr,
                pay_method=pay_method,
                total_count=total_count,
                total_price=total_price,
                transit_price=transit_price
            )

            # todo:用户订单中有几个商品，需要向df_order_goods表中加入几条记录
            conn = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id

            sku_ids = sku_ids.split(',')  # 把字符串通过逗号分割，形成一个字典
            for sku_id in sku_ids:
                for i in range(3):
                    # 获取商品的信息，在这个位置尝试一下注入
                    try:
                        sku = GoodsSKU.objects.get(id=sku_id)
                        # sku = GoodsSKU.objects.select_for_update().get(id=sku_id)
                        # 上面这行就是悲观锁
                        # select_for_update() 相当获得了锁, sql: select * from df_goods_sku where id=sku_id for update;
                    except GoodsSKU.DoesNotExist:
                        # 商品不存在，回滚到没有操作的保存点
                        transaction.savepoint_rollback(save_point_id)
                        return JsonResponse({
                            'res': 5,
                            'msg': '商品不存在'
                        })

                    # 从redis中获取用户所要购买的商品的数量
                    count = conn.hget(cart_key, sku_id)

                    # 检测需要购买数量是否超过库存
                    if sku.stock < int(count):
                        transaction.savepoint_rollback(save_point_id)
                        return JsonResponse({
                            'res': 6,
                            'msg': '商品库存不足'
                        })
                    # 修改商品表中的数据（更新库存和销量）
                    orgin_stock = sku.stock
                    new_stock = orgin_stock - int(count)
                    new_sales = sku.sales - int(count)
                    # todo:
                    # update df_goods_sku set stock=new_stock, sales=new_sales
                    # where id=sku_id and stock = orgin_stock
                    # 返回受影响的行数res, 0为失败
                    res = GoodsSKU.objects.filter(id=sku_id, stock=orgin_stock).update(
                        stock=new_stock,
                        sales=new_sales
                    )  # 乐观锁
                    if res == 0:  # 返回为0,表示更新失败
                        if i == 2:
                            transaction.savepoint_rollback(save_point_id)
                            return JsonResponse({
                                'res': 8,
                                'msg': '下单失败m2'
                            })
                        continue

                    # todo: 向df_order_goods表中添加一条记录
                    OrderGoods.objects.create(
                        order=order,
                        sku=sku,
                        count=count,
                        price=sku.price
                    )
                    # todo: 更新商品的库存和销量
                    sku.stock -= int(count)
                    sku.sales += int(count)
                    sku.save()
                    # todo:　累加计算订单商品的总数量和总价格
                    total_count += int(count)
                    amount = int(count) * sku.price
                    total_price += amount

                    break

            # todo: 更新订单信息表中的商品总数量和总价格
            order.total_count = total_count
            order.total_price = total_price
            order.save()
        except Exception as e:
            transaction.savepoint_rollback(save_point_id)
            return JsonResponse({
                'res': 7,
                'msg': '下单失败，数据库事务出错'
            })
        transaction.savepoint_commit(save_point_id)
        # todo: 清除用户购物车中对应的记录　[1,3]
        # 在列表的前面加一个*，相当于自动给你执行多次，每次传入一个数字
        conn.hdel(cart_key, *sku_ids)

        # 返回应答
        return JsonResponse({
            'res': 0,
            'msg': '订单创建成功'
        })


# 前端采用ajax post请求, 参数：order_id
class OrderPayView(View):
    def post(self, request):
        # 验证用户是否登录
        user = request.user
        if not user.is_authenticated:
            return JsonResponse({
                'res': 1,
                'msg': '请先登录才能支付'
            })
        # 接受参数
        order_id = request.POST.get('order_id')
        # 校验参数
        if not all([order_id]):
            return JsonResponse({
                'res': 2,
                'msg': '参数错误'
            })
        # 获取该订单
        try:
            order = OrderInfo.objects.get(order_id=order_id, user=user, order_status=1)
        except OrderInfo.DoesNotExist:
            return JsonResponse({
                'res': 3,
                'msg': '参数错误'
            })

        # 确认支付方式
        if order.pay_method == 1:
            return JsonResponse({'res': 4, 'msg': '该支付方式还未开通'})
        elif order.pay_method == 2:
            return JsonResponse({'res': 4, 'msg': '该支付方式还未开通'})
        elif order.pay_method == 3:  # 支付宝支付
            # print(settings.ALIPAY_APP_ID)
            # print(settings.APP_PRIVATE_KEY)
            # print(open(settings.APP_PRIVATE_KEY).read())
            # print(settings.ALIPAY_PUBLIC_KEY)
            # print(open(settings.ALIPAY_PUBLIC_KEY).read())
            # 业务处理：用python　sdk调用支付宝接口支付
            alipay = AliPay(
                appid=settings.ALIPAY_APP_ID,
                app_notify_url=None,  # 默认回调url
                app_private_key_string=open(settings.APP_PRIVATE_KEY).read(),
                # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
                alipay_public_key_string=open(settings.ALIPAY_PUBLIC_KEY).read(),
                sign_type="RSA2",  # RSA 或者 RSA2
                debug=True  # 默认False
            )

            # 电脑网站支付，需要跳转到https://openapi.alipaydev.com/gateway.do? + order_string
            order_string = alipay.api_alipay_trade_page_pay(
                out_trade_no=order.order_id,
                total_amount=str(order.total_price),
                subject="JPC_test_%d" % user.id,
                return_url=None,
                notify_url=None  # 可选, 不填则使用默认notify url
            )

            pay_url = 'https://openapi.alipaydev.com/gateway.do?' + order_string
            # 返回应答
            return JsonResponse({
                'res': 0,
                'pay_url': pay_url
            })
            # return JsonResponse({'res': 4, 'msg': '支付宝支付'})
        elif order.pay_method == 4:
            return JsonResponse({'res': 4, 'msg': '该支付方式还未开通'})
        else:
            return JsonResponse({
                'res': 4,
                'msg': '未知支付方式错误'
            })

        # 业务处理：用python　sdk调用支付宝接口支付
        alipay = AliPay(
            appid=settings.ALIPAY_APP_ID,
            app_notify_url=None,  # 默认回调url
            app_private_key_string=settings.APP_PRIVATE_KEY,
            # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
            alipay_public_key_string=settings.ALIPAY_PUBLIC_KEY,
            sign_type="RSA",  # RSA 或者 RSA2
            debug=True  # 默认False
        )

        # 电脑网站支付，需要跳转到https://openapi.alipaydev.com/gateway.do? + order_string
        order_string = alipay.api_alipay_trade_page_pay(
            out_trade_no=order.order_id,
            total_amount=str(order.order_price),
            subject="JPC_test_%d" % order_id,
            return_url=None,
            notify_url=None  # 可选, 不填则使用默认notify url
        )

        pay_url = 'https://openapi.alipaydev.com/gateway.do?' + order_string
        # 返回应答
        return JsonResponse({
            'res': 0,
            'pay_url': pay_url
        })

