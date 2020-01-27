from django.urls import path
# from . import views
from .views import RegisterView, LoginView, ActiveView

app_name = 'user'

urlpatterns = [
    # path('register', views.register, name='register'),  # 注册
    # path('register_handle', views.register_handle, name='register_handle')  # 注册处理
    path('register', RegisterView.as_view(), name='register'),  # 注册和处理注册业务
    path('active/<token>', ActiveView.as_view(), name='active'),  # 激活业务
    path('login', LoginView.as_view(), name='login')  # 登录业务
]
