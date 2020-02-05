from django.shortcuts import render, redirect
from django.urls import reverse
from django.views import View
from django.core.cache import cache
from django.core.paginator import Paginator
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


# 种类id 页码 排序方式
# restful api -> 请求一种资源
# /list?type_id=种类id&page=页码&sort=排序方式
# /list/种类id/页码/排序方式
# /list/种类id/页码?sort=排序方式
class ListView(View):
    def get(self, request, type_id, page):
        # 获取商品种类信息
        try:
            type = GoodsType.objects.get(id=type_id)
        except GoodsType.DoesNotExist:
            return redirect(reverse('goods:index'))

        # 获取商品分类信息
        types = GoodsType.objects.all()

        # 获取商品排序方式
        sort = request.GET.get('sort')
        if sort == 'price':
            skus = GoodsSKU.objects.filter(type=type).order_by('-price')
        elif sort == 'hot':
            skus = GoodsSKU.objects.filter(type=type).order_by('-sales')
        else:
            sort = "default"
            skus = GoodsSKU.objects.filter(type=type).order_by('id')

        # 对数据进行分页
        paginator = Paginator(skus, 10)

        # 获取第page页的内容
        try:
            page = int(page)
        except Exception as e:
            page = 1

        if page > paginator.num_pages or page <= 0:
            page = 1

        # 获取第page页的page实例对象
        skus_page = paginator.page(page)

        # todo: 进行页码的控制，页面上最多显示5个页码
        # 1.总页数小于5页，那么分页处则显示所有页面
        # 2.如果需要显示的页面是最前三页中的一页,则显示前5页，一共5个页面
        # 3.如果需要显示的页面是最后三页中的一页,则显示后5页，一共5个页面
        # 4.其他情况：显示当前页的前2页，当前页面，当前页的后2页，一共5个页面

        num_pages = paginator.num_pages
        if num_pages < 5:
            pages = range(1, num_pages+1)
        elif page <= 3:
            pages = range(1, 6)
        elif num_pages - page <= 2:
            pages = range(num_pages-4, num_pages+1)
        else:
            pages = range(page-2, page+3)

        # 获取新品信息
        new_skus = GoodsSKU.objects.filter(type=type).order_by('-create_time')[:2]

        # 获取购物车中的数量
        user = request.user
        cart_count = 0
        if user.is_authenticated:
            # 用户已经登录
            conn = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id
            cart_count = conn.hlen(cart_key)

        # 组织模板上下文
        context = {
            'type': type,
            'types': types,
            'skus': skus,
            'pages': pages,
            'sort': sort,
            'skus_page': skus_page,
            'new_skus': new_skus,
            'cart_count': cart_count
        }
        return render(request, 'list.html', context)





