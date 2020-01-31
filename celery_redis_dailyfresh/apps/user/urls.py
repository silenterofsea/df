from django.urls import path
# from django.contrib.auth.decorators import login_required
# from . import views
from .views import RegisterView, LoginView, ActiveView, UserInfoView, UserOrderView, AddressView, LogoutView

app_name = 'user'

urlpatterns = [
    # path('register', views.register, name='register'),  # 注册
    # path('register_handle', views.register_handle, name='register_handle')  # 注册处理
    path('register', RegisterView.as_view(), name='register'),  # 注册和处理注册业务
    path('active/<token>', ActiveView.as_view(), name='active'),  # 激活业务
    path('login', LoginView.as_view(), name='login'),  # 登录业务
    # path('order', login_required(UserOrderView.as_view()), name='order'),  # 用户订单信息
    # path('address', login_required(AddressView.as_view()), name='address'),  # 用户地址信息
    # path('', login_required(UserInfoView.as_view()), name='user')  # 用户中心
    path('order', UserOrderView.as_view(), name='order'),  # 用户订单信息
    path('address', AddressView.as_view(), name='address'),  # 用户地址信息
    path('', UserInfoView.as_view(), name='user'),  # 用户中心
    path('logout', LogoutView.as_view(), name='logout')
]
