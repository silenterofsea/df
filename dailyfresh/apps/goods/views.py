from django.shortcuts import render
from django.views import View
from apps.goods.models import GoodsType, IndexTypeGoodsBanner, IndexPromotionBanner, IndexGoodsBanner
from django_redis import get_redis_connection
# Create your views here.


def index(request):
    return render(request, 'index.html')


class IndexView(View):
    '''首页'''
    def get(self, request):
        '''显示首页'''
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

        # 获取用户购物车中商品的数目
        user = request.user
        cart_count = 0
        if user.is_authenticated:
            # 用户已经登录
            conn = get_redis_connection('default')
            cart_key = 'cart_%d'%user.id
            cart_count = conn.hlen(cart_key)

        # 组织模板上下文
        context = {
            'types': types,
            'goods_banner': goods_banner,
            'promotion_banner': promotion_banner,
            'cart_count': cart_count
        }

        # 使用模板
        return render(request, 'index.html', context)


class DetailView(View):
    def get(self, request):
        return render(request, 'index.html')
    pass


class ListView(View):
    def get(self, request):
        return render(request, 'index.html')
    pass




