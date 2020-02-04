from django.shortcuts import render, redirect
from django.urls import reverse
from django.views import View
from django.core.cache import cache
from apps.goods.models import GoodsType, GoodsSKU, IndexTypeGoodsBanner, IndexPromotionBanner, IndexGoodsBanner
from django_redis import get_redis_connection
from apps.order.models import OrderGoods
# Create your views here.


def index(request):
    return render(request, 'index.html')


class IndexView(View):
    '''首页'''
    def get(self, request):
        '''显示首页'''
        # 尝试获取缓存
        context = cache.get('index_page_data')
        # context = None
        if context is None:
            print("没有缓存")
            # 没有缓存，在数据库中去获取数据
            # 获取商品种类信息
            types = GoodsType.objects.all()

            # 获取首页轮播图商品信息
            goods_banner = IndexGoodsBanner.objects.all().order_by('index')

            # 获取首页促销活动信息
            promotion_banner = IndexPromotionBanner.objects.all().order_by('index')

            # 获取首页分类商品展示信息
            for type in types:  # GoodsTypes
                # 获取type种类首页分类商品的图片展示信息
                image_banner = IndexTypeGoodsBanner.objects.filter(type=type, display_type=1).order_by('index')
                # 获取type种类首页分类商品的文字展示信息
                title_banner = IndexTypeGoodsBanner.objects.filter(type=type, display_type=0).order_by('index')

                # 动态给type增加属性，分别保存首页分类商品的图片展示信息和文字展示信息
                type.image_banner = image_banner
                type.title_banner = title_banner
            context = {
                'types': types,
                'goods_banner': goods_banner,
                'promotion_banner': promotion_banner
            }
            cache.set('index_page_data', context, 3600)
        # print("有缓存")
        # 获取用户购物车中商品的数目
        user = request.user
        cart_count = 0
        if user.is_authenticated:
            # 用户已经登录
            conn = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id
            cart_count = conn.hlen(cart_key)
            # 如果用户登录，那么在缓存中加入用户信息

        context.update(cart_count=cart_count)

        # 组织模板上下文
        # context = {
        #     'types': types,
        #     'goods_banner': goods_banner,
        #     'promotion_banner': promotion_banner,
        #     'cart_count': cart_count
        # }

        # 使用模板
        return render(request, 'index.html', context)


class DetailView(View):
    def get(self, request, goods_id):
        try:
            sku = GoodsSKU.objects.get(id=goods_id)
        except GoodsSKU.DoesNotExist:
            return redirect(reverse('goods:index'))

        # 获取商品分类信息
        types = GoodsType.objects.all()
        # 获取商品的评论
        sku_orders = OrderGoods.objects.filter(sku=sku).exclude(comment='')
        # 获取新品信息
        new_skus = GoodsSKU.objects.all().order_by('-create_time')[:2]

        # 获取同一个SPU下的其他规格的商品
        same_spu_skus = GoodsSKU.objects.filter(goods=sku.goods).exclude(id=goods_id)
        # 获取购物车信息
        # 获取用户购物车中商品的数目
        user = request.user
        cart_count = 0
        if user.is_authenticated:
            # 用户已经登录
            conn = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id
            cart_count = conn.hlen(cart_key)

            # 添加用户的历史浏览记录
            conn = get_redis_connection('default')
            history_key = 'history_%d' % user.id
            # 移除列表中的goods_id
            conn.lrem(history_key, 0, goods_id)
            # 把goods_id插入到列表的左侧
            conn.lpush(history_key, goods_id)
            # 只保存用户最新浏览的5条信息
            conn.ltrim(history_key, 0, 4)

        context = {
            'types': types,
            'sku': sku,
            'sku_orders': sku_orders,
            'new_skus': new_skus,
            'same_spu_skus': same_spu_skus,
            'cart_count': cart_count
        }
        return render(request, 'detail.html', context)


class ListView(View):
    def get(self, request):
        return render(request, 'index.html')





