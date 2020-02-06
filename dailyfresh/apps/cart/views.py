from django.shortcuts import render
from django.views import View
from django.http import JsonResponse
from apps.goods.models import GoodsSKU
from django_redis import get_redis_connection
from utils.mixin import LoginRequiredMixin


# Create your views here.
# /cart/add
# 添加商品到购物车
# 1) 请求方式，采用ajax post
#    如果涉及到数据的修改(新增，更新，删除),采用post
#    如果涉及到数据的获取, 采用get
# 2) 传递参数：商品id 商品数量
# ajax发起的请求都在后台, 在浏览器中看不到效果
class CartAddView(View):
    def post(self, request):
        user = request.user
        if not user.is_authenticated:
            return JsonResponse({
                'res': 1,
                'errmsg': '请先登录后，才能加入购物车'
            })
        # 接受数据
        sku_id = request.POST.get('sku_id')
        count = request.POST.get('count')
        # 校验数据
        if not all([sku_id, count]):
            return JsonResponse({
                'res': 2,
                'errmsg': '数据不完整'
            })

        # 校验添加的商品数量
        try:
            count = int(count)
        except Exception as e:
            # 数目出错
            return JsonResponse({
                'res': 3,
                'errmsg': '数目错误'
            })
        # 校验商品是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except Exception as e:
            return JsonResponse({
                'res': 4,
                'errmsg': '商品ID有误，没有该商品'
            })
        # 业务处理
        # 添加购物车记录
        conn = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id
        # 先尝试获取sku_id的值-->hget cart_key 的属性
        # 这里没有用try,因为如果sku_id在hash中不存在，则会返回None
        cart_count = conn.hget(cart_key, sku_id)
        if cart_count:
            # 原本购物车中就有这个商品，那么累加！
            count += int(cart_count)
        # 校验商品的库存
        if count > sku.stock:
            return JsonResponse({
                'res': 5,
                'errmsg': '该商品的库存不足'
            })
        # 设置hash中sku_id对应的值-->hset
        # hset():如果redis中存在sku_id,则更新数据
        # hset():如果redis中不存在sku_id,则添加数据
        # 总结起来就是直接用hset()就可以了
        conn.hset(cart_key, sku_id, count)
        # 返回结果
        # 返回应答
        new_count = conn.hlen(cart_key)
        return JsonResponse({
            'res': 0,
            'new_count': new_count,
            'errmsg': '添加成功'
        })

    def get(self, request):
        pass


class CartInfoView(LoginRequiredMixin, View):
    def get(self, request):
        # 接受数据:获取登录的用户
        user = request.user
        # if not user.is_authenticated:
        #     return redirect(reverse('goods:index'))
        # 为什么不需要上面的判断？因为这个类继承了LoginRequiredMixin
        # 校验数据
        # 处理业务
        conn = get_redis_connection('default')
        user_key = 'cart_%d' % user.id
        # print(user_key)
        # 获取redis中该用户的所有信息:hgetall(用户id)
        cart_dict = conn.hgetall(user_key)
        # print(cart_dict)

        skus = []
        # 保存用户购物车中商品的总数目和总价格
        total_count = 0
        total_price = 0
        # 遍历获取商品的信息
        for sku_id, count in cart_dict.items():
            # 根据商品的ID获取商品的信息
            sku = GoodsSKU.objects.get(id=sku_id)
            # 计算商品的小计
            amount = sku.price * int(count)
            # 动态给sku对象增加一个属性amount,保存商品的小计
            sku.amount = amount
            # 动态给sku对象增加一个属性count,保存商品的数量
            sku.count = int(count)
            # print(sku.count)
            # 添加进入列表
            skus.append(sku)

            # 累加计算商品的总数目和总价格
            total_count += int(count)
            total_price += amount
        # 响应请求
        # 组织模板上下文
        context = {
            'skus': skus,
            'total_count': total_count,
            'total_price': total_price
        }
        return render(request, 'cart.html', context)
